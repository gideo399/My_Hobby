"""Chase / hood / cinematic camera. All maths is engine-independent: update() returns a CameraPose
that the GameManager applies to Ursina's camera.

Chase camera behaviour
  * sits behind the *blend of car heading and direction of travel* (so drifts show the slide),
  * yaw is smoothed, position is an offset from the car (no speed-proportional lag),
  * distance/height/FOV grow with speed, distance breathes with acceleration/braking,
  * a 2-D ray from the car to the camera pulls the camera in front of walls (no clipping).
"""
import math
from dataclasses import dataclass

from utilities.helpers import clamp, damp, lerp_angle, wrap_angle


@dataclass
class CameraPose:
    x: float
    y: float
    z: float
    pitch_deg: float     # Ursina rotation_x (positive = looking down)
    yaw_deg: float
    roll_deg: float
    fov: float


def _look(pos, target, roll=0.0, fov=85.0):
    dx, dy, dz = target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]
    horiz = math.hypot(dx, dz)
    return CameraPose(pos[0], pos[1], pos[2], math.degrees(math.atan2(-dy, horiz)),
                      math.degrees(math.atan2(dx, dz)), roll, fov)


class CameraRig:
    MODES = ("chase", "hood", "cinematic")

    def __init__(self, world=None, base_fov=85.0):
        self.world = world
        self.base_fov = base_fov
        self.mode_index = 0
        self.yaw = 0.0
        self.dist = 6.5
        self.height = 2.2
        self.accel_offset = 0.0
        self.fov = base_fov
        self.clip = 1.0                 # fraction of the desired offset that is free of walls
        self.orbit = 0.6

    @property
    def mode(self):
        return self.MODES[self.mode_index]

    def cycle_mode(self):
        self.mode_index = (self.mode_index + 1) % len(self.MODES)
        return self.mode

    def snap(self, phys):
        self.yaw = phys.psi
        self.dist, self.height, self.accel_offset, self.clip = 6.5, 2.2, 0.0, 1.0
        self.fov = self.base_fov

    def update(self, dt, phys) -> CameraPose:
        if self.mode == "hood":
            return self._hood(phys)
        if self.mode == "cinematic":
            return self._cinematic(dt, phys)
        return self._chase(dt, phys)

    # ----------------------------------------------------------------- chase
    def _chase(self, dt, p):
        speed = p.speed
        wx, wz = p.world_velocity()
        desired = p.psi
        if p.vx > 3.0:
            vel_heading = math.atan2(wx, wz)
            w = clamp((speed - 3.0) / 12.0, 0.0, 1.0) * 0.8
            desired = lerp_angle(p.psi, vel_heading, w)
        self.yaw = wrap_angle(self.yaw + wrap_angle(desired - self.yaw) * damp(dt, 4.5))

        self.accel_offset += (clamp(p._ax_f * 0.10, -0.8, 1.2) - self.accel_offset) * damp(dt, 3.0)
        t_dist = 6.2 + min(speed * 0.05, 3.2) + self.accel_offset
        t_height = 2.0 + min(speed * 0.012, 0.7)
        self.dist += (t_dist - self.dist) * damp(dt, 5.0)
        self.height += (t_height - self.height) * damp(dt, 5.0)
        self.fov += ((self.base_fov + clamp(speed * 0.22, 0.0, 16.0)) - self.fov) * damp(dt, 3.0)

        sy, cy = math.sin(self.yaw), math.cos(self.yaw)
        ox, oz = -sy * self.dist, -cy * self.dist
        cx0, cz0 = p.x, p.z

        # keep the camera in front of walls
        frac = 1.0
        if self.world is not None:
            hit = self.world.raycast(cx0, cz0, cx0 + ox, cz0 + oz)
            if hit is not None:
                frac = clamp(hit[0] - 0.08, 0.12, 1.0)
        if frac < self.clip:
            self.clip = frac                               # snap in immediately
        else:
            self.clip += (frac - self.clip) * damp(dt, 2.5)  # ease back out

        pos = (cx0 + ox * self.clip, max(0.6, self.height), cz0 + oz * self.clip)
        target = (p.x + sy * 3.0, 1.15, p.z + cy * 3.0)
        return _look(pos, target, roll=0.0, fov=self.fov)

    # ------------------------------------------------------------------ hood
    def _hood(self, p):
        s = p.spec
        fx, fz = p.forward
        eye = 0.30
        pos = (p.x + fx * eye, s.height * 0.86, p.z + fz * eye)
        return CameraPose(pos[0], pos[1], pos[2], p.pitch_deg * 0.7, math.degrees(p.psi),
                          p.roll_deg * 0.6, 78.0)

    # ------------------------------------------------------------ cinematic
    def _cinematic(self, dt, p):
        self.orbit += dt * 0.10
        yaw = p.psi + math.pi + math.sin(self.orbit) * 1.1
        d = 8.5 + min(p.speed * 0.04, 3.0)
        pos = (p.x + math.sin(yaw) * d, 1.6 + 0.6 * math.sin(self.orbit * 1.7) + 0.5, p.z + math.cos(yaw) * d)
        return _look(pos, (p.x, 0.9, p.z), fov=62.0)
