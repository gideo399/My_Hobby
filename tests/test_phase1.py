"""Pure-Python tests (no Ursina/Panda3D needed).   Run from the project root:  python -m tests.test_phase1"""
import math

from core.camera_rig import CameraRig
from utilities.collision import CollisionWorld, OBB2D, Obstacle, obb_overlap, segment_vs_obb
from utilities.mesh_builder import MeshBuilder, v_cross, v_dot, v_sub
from vehicles.procedural_car import build_body, build_wheel
from vehicles.vehicle_controller import InputSmoother
from vehicles.vehicle_physics import DriveInput, VehiclePhysics
from vehicles.vehicle_specs import SEDAN, SPORTS_CAR

DT = 1 / 60
SPECS = (SPORTS_CAR, SEDAN)


def sim(spec, seconds, inp, **init):
    p = VehiclePhysics(spec)
    for k, v in init.items():
        setattr(p, k, v)
    for _ in range(int(seconds / DT)):
        p.step(inp(p) if callable(inp) else inp, DT)
    return p


def test_acceleration_braking_topspeed():
    for s in SPECS:
        p, t100 = VehiclePhysics(s), None
        for i in range(60 * 40):
            p.step(DriveInput(throttle=1), DT)
            if t100 is None and p.speed_kmh >= 100:
                t100 = (i + 1) * DT
        assert 3.5 < t100 < 12, (s.name, t100)
        assert 150 < p.speed_kmh < 320
        p.vx, p.vy, p.r = 100 / 3.6, 0.0, 0.0
        x0, z0 = p.x, p.z
        for _ in range(60 * 10):
            p.step(DriveInput(brake=1), DT)
            if p.speed < 0.2:
                break
        d = math.hypot(p.x - x0, p.z - z0)
        assert p.speed < 0.3 and 25 < d < 60, (s.name, d)


def test_standstill_and_reverse():
    for s in SPECS:
        p = sim(s, 10, DriveInput(steer=1))
        assert p.speed < 0.01 and abs(p.x) < 0.01 and abs(p.z) < 0.01
        p = sim(s, 4, DriveInput(brake=1))
        assert p.vx < -3 and p.display_gear == "R"


def test_cornering_and_stability():
    for s in SPECS:
        p = sim(s, 6, lambda q: DriveInput(throttle=0.3 if q.vx < 20 else 0, steer=0.4), vx=20.0)
        assert p.r > 0 and 0.2 < p.ay / 9.81 < 1.3        # right turn, plausible lateral g
        assert p.roll_deg > 0 and abs(math.degrees(p.alpha_rear)) < 12
        for v in (30, 45, 60):                              # full lock at speed must not spin out
            q = sim(s, 3, DriveInput(steer=1), vx=float(v))
            assert math.isfinite(q.x) and q.ay / 9.81 < 1.4


def test_handbrake_breaks_rear_loose():
    p = sim(SPORTS_CAR, 1.0, DriveInput(steer=0.6, handbrake=1), vx=25.0)
    assert abs(math.degrees(p.alpha_rear)) > 15 and p.slide_rear > 1.0


def test_traction_control():
    on, off = VehiclePhysics(SPORTS_CAR), VehiclePhysics(SPORTS_CAR)
    off.traction_control = False
    on.vx = off.vx = 12.0
    for _ in range(240):
        on.step(DriveInput(throttle=1, steer=0.5), DT)
        off.step(DriveInput(throttle=1, steer=0.5), DT)
    assert abs(math.degrees(on.alpha_rear)) < 15
    assert off.speed < on.speed           # without TCS the car spins and scrubs speed


def test_weight_transfer_and_body_motion():
    p = sim(SPORTS_CAR, 1.0, DriveInput(throttle=1))
    assert p.pitch_deg < -0.3                                # squat: nose up
    p.vx = 30.0
    for _ in range(60):
        p.step(DriveInput(brake=1), DT)
    assert p.pitch_deg > 0.3                                 # dive: nose down


def test_frame_rate_independence():
    out = []
    for fps in (30, 60, 144):
        p = VehiclePhysics(SPORTS_CAR)
        for _ in range(fps * 5):
            p.step(DriveInput(throttle=1), 1.0 / fps)
        out.append(p.z)
    assert max(out) - min(out) < 0.02 * max(out), out


def test_collision_sat_and_response():
    a = OBB2D(0, 0, 1, 2, 0)
    assert obb_overlap(a, OBB2D(0, 10, 1, 1, 0)) is None
    c = obb_overlap(a, OBB2D(0, 2.8, 1, 1, 0))
    assert c and abs(c.nz + 1) < 1e-9 and abs(c.depth - 0.2) < 1e-9
    # car drives into a wall: stops, cannot pass
    world = CollisionWorld()
    world.add(Obstacle(OBB2D(0, 40, 20, 1, 0), "wall"))
    p = VehiclePhysics(SPORTS_CAR)
    p.vx = 30.0
    for _ in range(600):
        box = OBB2D(p.x, p.z, 0.93, 2.23, p.psi)
        p.step(DriveInput(throttle=1), DT, on_substep=lambda ph: _collide(world, ph))
    assert p.z < 40 - 1 - 2.2 + 0.5, p.z
    assert p.last_impact_speed > 20


def _collide(world, ph):
    for _ in range(3):
        box = OBB2D(ph.x, ph.z, 0.93, 2.23, ph.psi)
        hits = [(obb_overlap(box, o.obb), o) for o in world.query(box)]
        hits = [(c, o) for c, o in hits if c]
        if not hits:
            return
        c, o = max(hits, key=lambda h: h[0].depth)
        ph.resolve_contact(c.nx, c.nz, c.depth, c.px, c.pz, o.restitution, o.friction)


def test_corner_hit_induces_yaw():
    world = CollisionWorld()
    world.add(Obstacle(OBB2D(2.0, 30, 1.2, 1, 0), "wall"))   # catches only the right-front corner
    p = VehiclePhysics(SPORTS_CAR)
    p.vx = 20.0
    for _ in range(120):
        p.step(DriveInput(), DT, on_substep=lambda ph: _collide(world, ph))
    assert p.r > 0 or p.psi > 0.02          # nose pushed toward the right


def test_raycast():
    w = CollisionWorld()
    w.add(Obstacle(OBB2D(0, 10, 2, 1, 0)))
    hit = w.raycast(0, 0, 0, 20)
    assert hit and abs(hit[0] - 0.45) < 1e-9
    assert w.raycast(5, 0, 5, 20) is None
    assert segment_vs_obb(0, 10, 0, 20, OBB2D(0, 10, 2, 1, 0)) is None   # starts inside


def test_camera_does_not_clip_through_walls():
    w = CollisionWorld()
    w.add(Obstacle(OBB2D(0, -4, 20, 0.5, 0)))                 # wall right behind the car
    rig = CameraRig(w)
    p = VehiclePhysics(SPORTS_CAR)
    for _ in range(30):
        pose = rig.update(DT, p)
    assert pose.z > -3.6, pose.z
    rig2 = CameraRig(None)
    for _ in range(30):
        pose2 = rig2.update(DT, p)
    assert pose2.z < -5


def test_input_smoother():
    sm = InputSmoother()
    o = sm.update(DriveInput(throttle=1, steer=1), 0.05)
    assert 0 < o.throttle < 1 and 0 < o.steer < 1
    for _ in range(100):
        o = sm.update(DriveInput(), 0.05)
    assert o.throttle == 0 and o.steer == 0


def test_meshes_valid_and_outward():
    for s in SPECS:
        mb = build_body(s, s.default_paint)
        for name, m in mb.parts.items():
            m.validate()
            assert m.tri_count > 20
        (x0, y0, z0), (x1, y1, z1) = mb.parts["body"].bounds()
        assert y0 >= 0.0 and abs(y1 - s.height) < 0.02
        assert abs((x1 - x0) - s.width) < 0.1 and abs((z1 - z0) - s.length) < 0.25
        for side in (-1, 1):
            w = build_wheel(s, side).parts["wheel"]
            w.validate()
            (a0, b0, c0), (a1, b1, c1) = w.bounds()
            assert abs((b1 - b0) - 2 * s.wheel_radius) < 1e-6


def test_winding_matches_normals():
    """Every emitted triangle's winding must agree with its stored outward normal (left-handed rule)."""
    mb = MeshBuilder()
    mb.box((0, 0, 0), (2, 2, 2), (1, 1, 1, 1), yaw_deg=30)
    mb.frustum((0, 0, 0), 1, 0.5, 2, (1, 1, 1, 1), "y", 8)
    m = mb.part()
    for i in range(0, len(m.triangles), 3):
        a, b, c = (m.vertices[m.triangles[i + k]] for k in range(3))
        n = tuple(-x for x in v_cross(v_sub(b, a), v_sub(c, a)))
        assert v_dot(n, m.normals[m.triangles[i]]) > 0
        cen = tuple(sum(p[k] for p in (a, b, c)) / 3 for k in range(3))
        assert v_dot(m.normals[m.triangles[i]], cen) > 0      # points away from the origin (convex solids)


def main():
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print("PASS", n)
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    main()
