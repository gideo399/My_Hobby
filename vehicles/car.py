"""Car = physics (VehiclePhysics) + collision + Ursina visuals.

Entity hierarchy (all in the engine's left-handed, Y-up, metres space):

  root              position (x, 0, z) and rotation_y = heading
  └─ model_frame    shifted so its origin is the centre of the wheelbase
     ├─ body_pivot  at CG height; receives pitch/roll from the suspension model
     │   ├─ body    (paint/glass/trim/headlights, one mesh)   └─ tail (brake lights)
     └─ wheel pivots (steer about Y) └─ spin (rotation_x = rolling angle)
"""
import math

from ursina import Entity, Vec3, destroy
from ursina import color as ucolor

from core.asset_manager import to_ursina_mesh
from utilities.collision import OBB2D, obb_overlap
from vehicles.procedural_car import build_body, build_wheel
from vehicles.vehicle_physics import DriveInput, VehiclePhysics

TAIL_OFF = (0.34, 0.34, 0.34, 1.0)
TAIL_ON = (1.0, 1.0, 1.0, 1.0)


class Car:
    def __init__(self, spec, world=None, x=0.0, z=0.0, heading_deg=0.0, paint=None, settings=None):
        self.spec = spec
        self.world = world
        fixed = settings.physics.fixed_dt if settings else None
        kwargs = {"fixed_dt": fixed} if fixed else {}
        self.physics = VehiclePhysics(spec, x, z, math.radians(heading_deg), **kwargs)
        self.paint = paint or spec.default_paint
        self._tail_lit = None
        self._build_visuals()
        self.sync_visuals()

    # ------------------------------------------------------------------ visuals
    def _build_visuals(self):
        s = self.spec
        body = build_body(s, self.paint)
        self.root = Entity()
        self.model_frame = Entity(parent=self.root, z=(s.a - s.b) / 2.0)
        self.body_pivot = Entity(parent=self.model_frame, y=s.cg_height)
        Entity(parent=self.body_pivot, model=to_ursina_mesh(body.parts["body"]), y=-s.cg_height)
        self.tail = Entity(parent=self.body_pivot, model=to_ursina_mesh(body.parts["tail"]), y=-s.cg_height)

        self.wheel_pivots, self.wheel_spins = [], []
        meshes = {-1: to_ursina_mesh(build_wheel(s, -1).parts["wheel"]),
                  +1: to_ursina_mesh(build_wheel(s, +1).parts["wheel"])}
        # order matches VehiclePhysics.wheel_angle_deg: FL, FR, RL, RR
        for sx, sz in ((-1, +1), (+1, +1), (-1, -1), (+1, -1)):
            pivot = Entity(parent=self.model_frame,
                           position=Vec3(sx * s.track / 2.0, s.wheel_radius, sz * s.wheelbase / 2.0))
            spin = Entity(parent=pivot, model=meshes[sx])
            self.wheel_pivots.append(pivot)
            self.wheel_spins.append(spin)

    def sync_visuals(self):
        p = self.physics
        self.root.position = Vec3(p.x, 0.0, p.z)
        self.root.rotation_y = math.degrees(p.psi)
        self.body_pivot.rotation_x = p.pitch_deg
        self.body_pivot.rotation_z = p.roll_deg
        steer_deg = math.degrees(p.steer)
        self.wheel_pivots[0].rotation_y = steer_deg
        self.wheel_pivots[1].rotation_y = steer_deg
        for i, spin in enumerate(self.wheel_spins):
            spin.rotation_x = p.wheel_angle_deg[i]
        lit = p.brake_lit
        if lit != self._tail_lit:
            self._tail_lit = lit
            self.tail.color = ucolor.Color(*(TAIL_ON if lit else TAIL_OFF))

    # ------------------------------------------------------------------ physics
    def obb(self):
        p, s = self.physics, self.spec
        off = (s.a - s.b) / 2.0
        return OBB2D(p.x + math.sin(p.psi) * off, p.z + math.cos(p.psi) * off,
                     s.width / 2.0 - 0.03, s.length / 2.0 - 0.02, p.psi)

    def _collide(self, phys):
        if self.world is None:
            return
        for _ in range(3):                      # a few passes handle corners / multiple contacts
            box = self.obb()
            best, best_ob = None, None
            for ob in self.world.query(box):
                c = obb_overlap(box, ob.obb)
                if c is not None and (best is None or c.depth > best.depth):
                    best, best_ob = c, ob
            if best is None:
                return
            phys.resolve_contact(best.nx, best.nz, best.depth + 0.002, best.px, best.pz,
                                 best_ob.restitution, best_ob.friction)

    def step(self, inputs: DriveInput, dt):
        self.physics.step(inputs, dt, on_substep=self._collide)

    def reset(self, x, z, heading_deg):
        self.physics.reset(x, z, math.radians(heading_deg))
        self.sync_visuals()

    def destroy(self):
        destroy(self.root)
