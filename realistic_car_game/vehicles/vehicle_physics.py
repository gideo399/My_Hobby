"""Pure-Python vehicle dynamics (no engine imports -> unit-testable, engine independent).

Model: planar *dynamic bicycle model* with
  * separate front / rear axles, each with a simplified Pacejka lateral force curve,
  * friction-circle coupling between traction/braking and cornering (so power-oversteer,
    brake-lock understeer and handbrake drifts emerge instead of being scripted),
  * longitudinal load transfer (grip shifts front<->rear under accel/braking),
  * engine torque curve + auto gearbox + clutch slip at launch + rev limiter,
  * aerodynamic drag, downforce, rolling resistance, engine braking,
  * 2-DOF spring/damper body pitch & roll (visual suspension) driven by the real accelerations,
  * impulse-based collision response with yaw (resolve_contact).

State is expressed in the body frame: vx forward, vy to the right, r yaw rate (positive =
turning right, i.e. increasing heading psi).  World position uses the engine convention
(forward = (sin psi, cos psi)).
"""
import math
from dataclasses import dataclass

from utilities.helpers import clamp, damp, piecewise_linear, smooth_sign, wrap_angle

G = 9.81
RHO = 1.225
V_MIN = 1.5                # minimum speed used when computing slip angles
LOW_SPEED_BLEND = 4.0      # below this speed blend toward the kinematic bicycle model
REVERSE_THRESHOLD = 0.8
TC_LIMIT = 0.75           # traction control: max fraction of axle grip used for drive force
FIXED_DT = 1.0 / 120.0
MAX_SUBSTEPS = 8


@dataclass
class DriveInput:
    throttle: float = 0.0      # 0..1
    brake: float = 0.0         # 0..1 (also reverse when stopped)
    steer: float = 0.0         # -1 (left) .. +1 (right)
    handbrake: float = 0.0     # 0..1


class VehiclePhysics:
    def __init__(self, spec, x=0.0, z=0.0, heading=0.0, fixed_dt=FIXED_DT, max_substeps=MAX_SUBSTEPS):
        self.spec = spec
        self.grip_scale = 1.0               # surface: multiplies tyre friction (grass < asphalt)
        self.extra_rolling = 0.0            # surface: added rolling resistance coefficient
        self.traction_control = True        # driver aid: caps drive force so cornering grip is kept
        self.fixed_dt = fixed_dt
        self.max_substeps = max_substeps
        self.reset(x, z, heading)

    # ------------------------------------------------------------------ state
    def reset(self, x=None, z=None, heading=None):
        if x is not None:
            self.x = x
        if z is not None:
            self.z = z
        if heading is not None:
            self.psi = heading
        if not hasattr(self, "x"):
            self.x = self.z = self.psi = 0.0
        self.vx = self.vy = self.r = 0.0
        self.steer = 0.0
        self.gear = 1
        self.shift_timer = 0.0
        self.rpm = self.spec.idle_rpm
        self.drive_cmd = self.brake_cmd = self.hand = 0.0
        self._drive_force = 0.0
        self._ax_f = self._ay_f = 0.0
        self.ax = self.ay = 0.0
        self.pitch_deg = self.roll_deg = 0.0
        self._pitch_v = self._roll_v = 0.0
        self.wheel_angle_deg = [0.0, 0.0, 0.0, 0.0]      # FL, FR, RL, RR
        self.slide_front = self.slide_rear = 0.0
        self.alpha_front = self.alpha_rear = 0.0
        self.traction_loss_front = self.traction_loss_rear = False
        self._vlong_f = 0.0
        self._driven_saturated = False
        self.last_impact_speed = 0.0
        self.impact_events = []                            # (speed m/s, x, z) since last clear

    # --------------------------------------------------------------- readouts
    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    @property
    def speed_kmh(self):
        return self.speed * 3.6

    @property
    def forward(self):
        return math.sin(self.psi), math.cos(self.psi)

    @property
    def right(self):
        return math.cos(self.psi), -math.sin(self.psi)

    @property
    def display_gear(self):
        if self.gear == -1:
            return "R"
        if abs(self.vx) < 0.3 and abs(self.drive_cmd) < 0.02:
            return "N"
        return str(self.gear)

    @property
    def brake_lit(self):
        return self.brake_cmd > 0.05 or self.hand > 0.5

    @property
    def reversing(self):
        return self.gear == -1 and self.drive_cmd < -0.02

    def world_velocity(self):
        s, c = math.sin(self.psi), math.cos(self.psi)
        return self.vx * s + self.vy * c, self.vx * c - self.vy * s

    def _set_world_velocity(self, wx, wz):
        s, c = math.sin(self.psi), math.cos(self.psi)
        self.vx = wx * s + wz * c
        self.vy = wx * c - wz * s

    # ------------------------------------------------------------------- step
    def step(self, inp: DriveInput, dt, on_substep=None):
        if dt <= 0:
            return
        n = min(self.max_substeps, max(1, math.ceil(dt / self.fixed_dt)))
        h = dt / n
        self._update_steering(inp.steer, dt)
        self._update_drivetrain(inp, dt)
        for _ in range(n):
            self._substep(h)
            if on_substep is not None:
                on_substep(self)
        self._update_body_motion(dt)
        self._update_wheels(dt)
        if not all(map(math.isfinite, (self.x, self.z, self.psi, self.vx, self.vy, self.r))):
            self.reset()          # numerical safety net: never propagate NaNs into the renderer

    # --------------------------------------------------------------- steering
    def _update_steering(self, steer_in, dt):
        """Speed-sensitive steering. The usable lock is the harmonic blend of the mechanical lock
        and the angle that would demand ~1.25x the tyre grip limit (a_lat = v^2 * delta / L), so
        full keyboard deflection at 150 km/h asks for the grip limit instead of a spin."""
        s = self.spec
        v = max(self.speed, 1.0)
        mu = 0.5 * (s.mu_front + s.mu_rear)
        grip_delta = s.steer_grip_k * s.wheelbase * mu * G / (v * v)
        max_delta = 1.0 / (1.0 / s.max_steer + 1.0 / grip_delta)
        max_delta = max(max_delta, math.radians(0.3))
        target = clamp(steer_in, -1.0, 1.0) * max_delta
        self.steer += (target - self.steer) * min(1.0, s.steer_response * dt)

    # -------------------------------------------------------------- drivetrain
    def _ratio(self, gear):
        s = self.spec
        base = s.reverse_ratio if gear == -1 else s.gear_ratios[gear - 1]
        return base * s.final_drive

    def _geared_rpm(self, gear):
        s = self.spec
        return abs(self.vx) / s.wheel_radius * self._ratio(gear) * 60.0 / (2.0 * math.pi)

    def _update_drivetrain(self, inp, dt):
        s = self.spec
        vx = self.vx
        thr = clamp(inp.throttle, 0.0, 1.0)
        brk = clamp(inp.brake, 0.0, 1.0)
        drive_cmd = brake_cmd = 0.0
        if thr > 0.02:
            if vx < -REVERSE_THRESHOLD:        # rolling backwards, W = brake first
                brake_cmd = max(brk, thr)
            else:
                drive_cmd, brake_cmd = thr, brk
        elif brk > 0.02:
            if vx > REVERSE_THRESHOLD:         # rolling forwards, S = brake
                brake_cmd = brk
            else:                              # (almost) stopped: S = reverse
                drive_cmd = -brk
        self.drive_cmd, self.brake_cmd = drive_cmd, brake_cmd
        self.hand = clamp(inp.handbrake, 0.0, 1.0)

        # --- automatic gearbox
        if drive_cmd < -0.02:
            self.gear = -1
        elif drive_cmd > 0.02 and self.gear < 1:
            self.gear = 1
        self.shift_timer = max(0.0, self.shift_timer - dt)
        ngears = len(s.gear_ratios)
        if self.gear >= 1 and self.shift_timer <= 0.0:
            rpm_g = self._geared_rpm(self.gear)
            if drive_cmd > 0.05 and rpm_g > s.shift_up_rpm and self.gear < ngears:
                self.gear += 1
                self.shift_timer = s.shift_time
            elif self.gear > 1 and rpm_g < s.shift_down_rpm:
                if self._geared_rpm(self.gear - 1) < 0.92 * s.redline_rpm:
                    self.gear -= 1
                    self.shift_timer = 0.12

        # --- engine speed
        gear = self.gear if self.gear != 0 else 1
        geared = self._geared_rpm(gear)
        if abs(drive_cmd) > 0.02:
            target_rpm = max(geared, s.idle_rpm + abs(drive_cmd) * (s.clutch_rpm - s.idle_rpm))
        else:
            target_rpm = max(s.idle_rpm, geared)
        target_rpm = min(target_rpm, s.redline_rpm * 1.02)
        self.rpm += (target_rpm - self.rpm) * min(1.0, 18.0 * dt)

        # --- wheel force
        ratio = self._ratio(gear)
        torque = piecewise_linear(s.torque_curve, min(target_rpm, s.torque_curve[-1][0]))
        if target_rpm > 0.97 * s.redline_rpm:                  # soft rev limiter
            torque *= max(0.0, (s.redline_rpm - target_rpm) / (0.03 * s.redline_rpm))
        if self.shift_timer > 0.0:
            torque = 0.0                                        # torque cut while shifting
        force = torque * abs(drive_cmd) * ratio * s.drivetrain_eff / s.wheel_radius
        if self.gear == -1:
            force = -force * clamp(1.0 - abs(vx) / s.reverse_speed_limit, 0.0, 1.0)
        if abs(drive_cmd) < 0.02 and abs(vx) > 1.0:            # engine braking
            force -= smooth_sign(vx, 1.0) * s.engine_brake * s.mass * G * clamp(geared / s.redline_rpm, 0.0, 1.0)
        self._drive_force = force

    # --------------------------------------------------------------- substeps
    def _substep(self, h):
        s = self.spec
        m, a, b, L = s.mass, s.a, s.b, s.wheelbase
        vx, vy, r = self.vx, self.vy, self.r
        speed = math.hypot(vx, vy)

        # Axle normal loads: static + longitudinal transfer + downforce
        down = s.downforce * speed * speed
        fz_f0, fz_r0 = m * G * b / L, m * G * a / L
        dfz = m * self._ax_f * s.cg_height / L
        fz_f = max(0.15 * fz_f0, fz_f0 - dfz + 0.45 * down)
        fz_r = max(0.15 * fz_r0, fz_r0 + dfz + 0.55 * down)

        # Longitudinal force demand per axle (+ drive, - brake opposing motion)
        sgn = smooth_sign(vx, 0.4)
        fb = self.brake_cmd * s.brake_force
        fb_f = fb * s.brake_bias_front
        fb_r = fb * (1.0 - s.brake_bias_front) + self.hand * 0.5 * s.brake_force
        if s.drive == "FWD":
            df, dr = 1.0, 0.0
        elif s.drive == "AWD":
            df, dr = 0.4, 0.6
        else:
            df, dr = 0.0, 1.0
        mu_f = s.mu_front * self.grip_scale
        mu_r = s.mu_rear * self.grip_scale * (1.0 - 0.55 * self.hand)           # handbrake locks / unloads the rears
        fmax_f, fmax_r = mu_f * fz_f, mu_r * fz_r
        drv_f, drv_r = self._drive_force * df, self._drive_force * dr
        if self.traction_control:
            drv_f = clamp(drv_f, -TC_LIMIT * fmax_f, TC_LIMIT * fmax_f)
            drv_r = clamp(drv_r, -TC_LIMIT * fmax_r, TC_LIMIT * fmax_r)
        fx_f_dem = drv_f - sgn * fb_f
        fx_r_dem = drv_r - sgn * fb_r

        # Friction circle: traction uses part of the available grip, the rest is lateral.
        sat_f, sat_r = abs(fx_f_dem) > fmax_f, abs(fx_r_dem) > fmax_r
        fx_f = math.copysign(0.92 * fmax_f, fx_f_dem) if sat_f else fx_f_dem   # kinetic < static
        fx_r = math.copysign(0.92 * fmax_r, fx_r_dem) if sat_r else fx_r_dem
        fy_f_max = max(0.2 * fmax_f, math.sqrt(max(0.0, fmax_f ** 2 - fx_f ** 2)))
        fy_r_max = max(0.2 * fmax_r, math.sqrt(max(0.0, fmax_r ** 2 - fx_r ** 2)))

        # Slip angles (front wheels are steered)
        delta = self.steer
        cd, sd = math.cos(delta), math.sin(delta)
        vyf, vyr = vy + a * r, vy - b * r
        vlong_f = vx * cd + vyf * sd
        vlat_f = -vx * sd + vyf * cd
        alpha_f = math.atan2(vlat_f, max(abs(vlong_f), V_MIN))
        alpha_r = math.atan2(vyr, max(abs(vx), V_MIN))
        fy_f_w = -fy_f_max * math.sin(s.C * math.atan(s.B_front * alpha_f))
        fy_r = -fy_r_max * math.sin(s.C * math.atan(s.B_rear * alpha_r))

        # Resolve into body frame
        fx_b = fx_f * cd - fy_f_w * sd + fx_r
        fy_front_b = fx_f * sd + fy_f_w * cd
        fy_b = fy_front_b + fy_r
        kd = 0.5 * RHO * s.cd_a
        fx_b += -kd * speed * vx - (s.crr + self.extra_rolling) * m * G * smooth_sign(vx, 0.3)
        fy_b += -kd * speed * vy
        torque_z = a * fy_front_b - b * fy_r

        ax, ay = fx_b / m, fy_b / m
        k = min(1.0, 10.0 * h)
        self._ax_f += (ax - self._ax_f) * k
        self._ay_f += (ay - self._ay_f) * k
        self.ax, self.ay = ax, ay

        vx_n = vx + (ax + vy * r) * h
        vy_n = vy + (ay - vx * r) * h
        r_n = r + torque_z / s.inertia * h

        # Blend to the kinematic bicycle model at crawling speed (slip angles are ill-defined there)
        w = clamp(1.0 - math.hypot(vx_n, vy_n) / LOW_SPEED_BLEND, 0.0, 1.0)
        if w > 0.0:
            r_kin = vx_n * math.tan(delta) / L
            kk = min(1.0, 25.0 * h) * w
            r_n += (r_kin - r_n) * kk
            vy_n += (b * r_kin - vy_n) * kk

        self.vx, self.vy, self.r = vx_n, vy_n, r_n
        sn, cs = math.sin(self.psi), math.cos(self.psi)
        self.x += (vx_n * sn + vy_n * cs) * h
        self.z += (vx_n * cs - vy_n * sn) * h
        self.psi = wrap_angle(self.psi + r_n * h)

        # Telemetry for wheels / skid sounds / effects
        peak_f = math.tan(math.pi / (2.0 * s.C)) / s.B_front
        peak_r = math.tan(math.pi / (2.0 * s.C)) / s.B_rear
        self.alpha_front, self.alpha_rear = alpha_f, alpha_r
        self.slide_front = max(abs(alpha_f) / peak_f if speed > 2.0 else 0.0, 1.5 if sat_f and speed > 1.0 else 0.0)
        self.slide_rear = max(abs(alpha_r) / peak_r if speed > 2.0 else 0.0, 1.5 if sat_r and speed > 1.0 else 0.0)
        self.traction_loss_front, self.traction_loss_rear = sat_f, sat_r
        self._vlong_f = vlong_f
        self._driven_saturated = (sat_f and df > 0) or (sat_r and dr > 0) or (
            self.traction_control and abs(self._drive_force) > 0.0 and (
                (df > 0 and abs(self._drive_force * df) > TC_LIMIT * fmax_f) or
                (dr > 0 and abs(self._drive_force * dr) > TC_LIMIT * fmax_r)))

    # ------------------------------------------------------- visual dynamics
    def _update_body_motion(self, dt):
        s = self.spec
        w = 2.0 * math.pi * s.body_freq_hz
        z = s.body_damping
        pitch_t = -s.pitch_deg_per_ms2 * self._ax_f      # accelerate -> nose up (negative rotation_x)
        roll_t = s.roll_deg_per_ms2 * self._ay_f         # turn right -> body leans left (+rotation_z)
        n = max(1, math.ceil(dt / 0.01))
        h = dt / n
        for _ in range(n):
            self._pitch_v += (w * w * (pitch_t - self.pitch_deg) - 2 * z * w * self._pitch_v) * h
            self.pitch_deg += self._pitch_v * h
            self._roll_v += (w * w * (roll_t - self.roll_deg) - 2 * z * w * self._roll_v) * h
            self.roll_deg += self._roll_v * h
        self.pitch_deg = clamp(self.pitch_deg, -6.0, 6.0)
        self.roll_deg = clamp(self.roll_deg, -8.0, 8.0)

    def _update_wheels(self, dt):
        s = self.spec
        R = s.wheel_radius
        front = self._vlong_f / R
        rear = 0.0 if self.hand > 0.5 else self.vx / R
        if self._driven_saturated and abs(self.drive_cmd) > 0.3:      # visible wheelspin
            spin = 35.0 * math.copysign(1.0, self.drive_cmd)
            if s.drive == "FWD":
                front += spin
            else:
                rear += spin
        rates = (front, front, rear, rear)
        for i, rate in enumerate(rates):
            self.wheel_angle_deg[i] = (self.wheel_angle_deg[i] + math.degrees(rate * dt)) % 360.0

    # ------------------------------------------------------------- collisions
    def resolve_contact(self, nx, nz, depth, px, pz, restitution=0.2, friction=0.35):
        """Impulse response against an immovable obstacle.
        (nx, nz): unit normal pointing from the obstacle toward the vehicle; (px, pz): contact point."""
        s = self.spec
        self.x += nx * depth
        self.z += nz * depth
        wx, wz = self.world_velocity()
        rx, rz = px - self.x, pz - self.z
        vpx, vpz = wx + self.r * rz, wz - self.r * rx            # velocity of the contact point
        vn = vpx * nx + vpz * nz
        if vn >= 0.0:
            return 0.0
        e = restitution if -vn > 1.0 else 0.0
        inv_m, inv_i = 1.0 / s.mass, 1.0 / s.inertia
        cross_n = nx * rz - nz * rx
        j = -(1.0 + e) * vn / (inv_m + cross_n * cross_n * inv_i)
        tx, tz = -nz, nx
        vt = vpx * tx + vpz * tz
        cross_t = tx * rz - tz * rx
        jt = clamp(-vt / (inv_m + cross_t * cross_t * inv_i), -friction * j, friction * j)
        jx, jz = j * nx + jt * tx, j * nz + jt * tz
        self._set_world_velocity(wx + jx * inv_m, wz + jz * inv_m)
        self.r += (jx * rz - jz * rx) * inv_i
        impact = -vn
        self.last_impact_speed = max(self.last_impact_speed, impact)
        if impact > 1.5:
            self.impact_events.append((impact, px, pz))
        # body kick for the suspension model
        self._pitch_v += clamp(-vn * 0.4, 0.0, 6.0) * (1 if nz * math.cos(self.psi) + nx * math.sin(self.psi) < 0 else -1)
        return impact
