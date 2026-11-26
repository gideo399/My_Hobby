"""Street furniture, vegetation and parked cars.

All functions take a CityBuilder `cb` (see city.py) that supplies cb.mb(x, z) -> the MeshBuilder of the
render chunk containing (x, z), and cb.solid(...) to register collision.  Orientation arguments (dx, dz)
are axis-aligned unit vectors (one of them 0).  Everything is built from the cheap primitives in
utilities/mesh_builder.py: no external assets.
"""
import math

POLE = (0.30, 0.31, 0.34, 1.0)
TRUNK = (0.30, 0.20, 0.12, 1.0)
CONCRETE = (0.66, 0.66, 0.64, 1.0)
WOOD = (0.52, 0.36, 0.20, 1.0)
WHITE = (0.93, 0.93, 0.92, 1.0)
RED = (0.78, 0.10, 0.10, 1.0)
BLUE = (0.10, 0.28, 0.65, 1.0)
YELLOW = (0.95, 0.76, 0.10, 1.0)
GREEN_BIN = (0.16, 0.32, 0.22, 1.0)
PAINTS = [(0.75, 0.08, 0.06, 1), (0.10, 0.28, 0.55, 1), (0.85, 0.85, 0.86, 1), (0.08, 0.08, 0.09, 1),
          (0.45, 0.47, 0.50, 1), (0.88, 0.70, 0.12, 1), (0.12, 0.40, 0.22, 1), (0.55, 0.30, 0.15, 1)]


def obox(mb, x, z, y0, y1, a, b, d, color, off_d=0.0, off_a=0.0, part="plain", shade=True):
    """Axis-aligned box described relative to a facing d=(dx,dz): `b` = half extent along d,
    `a` = half extent along the perpendicular, with offsets along d / perpendicular."""
    dx, dz = d
    cx, cz = x + dx * off_d - dz * off_a, z + dz * off_d + dx * off_a
    hx, hz = (b, a) if dx else (a, b)
    mb.fbox(cx - hx, y0, cz - hz, cx + hx, y1, cz + hz, color, part, shade=shade)


def lamp(cb, x, z, dx, dz, h=8.5):
    mb = cb.mb(x, z)
    mb.fcyl(x, 0, z, 0.12, h, POLE, "plain", seg=6, r_top=0.08)
    mb.fbox(x - 0.18, 0, z - 0.18, x + 0.18, 0.35, z + 0.18, POLE, "plain")
    obox(mb, x, z, h - 0.14, h - 0.04, 1.0, 0.06, (dx, dz), POLE, off_d=1.0)
    obox(mb, x, z, h - 0.28, h - 0.10, 0.17, 0.46, (dx, dz), (0.78, 0.78, 0.72, 1.0), off_d=2.0)
    cb.solid("lamp", x, z, 0.14, 0.14, 0.1, False)


def traffic_signal(cb, x, z, fx, fz, h=3.7):
    """Signal head on a pole, facing (fx, fz) toward approaching drivers. Lamps are static (dim) in
    Phase 2; Phase 3 animates them.  Returns the head centre for later use."""
    mb = cb.mb(x, z)
    mb.fcyl(x, 0, z, 0.09, h + 0.4, POLE, "plain", seg=6)
    hx, hz = x + fx * 0.28, z + fz * 0.28
    obox(mb, hx, hz, h - 0.55, h + 0.55, 0.17, 0.17, (fx, fz), (0.07, 0.07, 0.08, 1.0))
    face = (hx + fx * 0.175, hz + fz * 0.175)
    for k, col in enumerate(((0.45, 0.08, 0.08, 1), (0.45, 0.35, 0.05, 1), (0.08, 0.38, 0.14, 1))):
        yc = h + 0.35 - k * 0.35
        px, pz = face
        t = (-fz, fx)
        mb.fquad((px - t[0] * 0.1, yc - 0.1, pz - t[1] * 0.1), (px + t[0] * 0.1, yc - 0.1, pz + t[1] * 0.1),
                 (px + t[0] * 0.1, yc + 0.1, pz + t[1] * 0.1), (px - t[0] * 0.1, yc + 0.1, pz - t[1] * 0.1),
                 (fx, 0, fz), col, "plain", shade=False)
    cb.solid("signal", x, z, 0.1, 0.1, 0.1, False)
    return hx, hz


def sign_plate(mb, x, y, z, fx, fz, r, sides, color, rim=None, rot=0.0, lift=0.0):
    """Flat sign facing (fx, fz): regular polygon with an optional contrasting inner polygon."""
    t = (-fz, fx)

    def poly(rad, off):
        pts = []
        for k in range(sides):
            a = rot + 2 * math.pi * k / sides
            u, v = rad * math.cos(a), rad * math.sin(a)
            pts.append((x + t[0] * u + fx * off, y + v, z + t[1] * u + fz * off))
        return pts
    mb.polygon(poly(r, 0.03 + lift), color, (fx, 0, fz), "plain", shade=False)
    if rim is not None:
        mb.polygon(poly(r * 0.78, 0.045 + lift), rim, (fx, 0, fz), "plain", shade=False)
    if lift == 0.0:
        mb.polygon(list(reversed(poly(r, 0.0))), (0.5, 0.5, 0.5, 1), (-fx, 0, -fz), "plain", shade=False)


def road_sign(cb, x, z, fx, fz, kind):
    mb = cb.mb(x, z)
    top = 2.6
    mb.fcyl(x, 0, z, 0.045, top, POLE, "plain", seg=5)
    y = top - 0.05
    if kind == "stop":
        sign_plate(mb, x, y, z, fx, fz, 0.38, 8, WHITE, None, rot=math.pi / 8)
        sign_plate(mb, x, y, z, fx, fz, 0.32, 8, (0.80, 0.12, 0.12, 1), None, rot=math.pi / 8, lift=0.02)
    elif kind == "yield":
        sign_plate(mb, x, y, z, fx, fz, 0.5, 3, RED, WHITE, rot=math.pi / 2 + math.pi)
    elif kind == "speed":
        sign_plate(mb, x, y - 0.1, z, fx, fz, 0.36, 12, RED, WHITE)
    elif kind == "crossing":
        sign_plate(mb, x, y - 0.1, z, fx, fz, 0.5, 4, YELLOW, YELLOW, rot=0.0)
    elif kind == "parking":
        sign_plate(mb, x, y - 0.1, z, fx, fz, 0.36, 4, BLUE, WHITE, rot=math.pi / 4)
    cb.solid("sign", x, z, 0.07, 0.07, 0.1, False)


def tree(cb, x, z, rng, kind=None, scale=1.0):
    mb = cb.mb(x, z)
    kind = kind or rng.choice(("round", "round", "tall", "conifer"))
    s = scale * rng.uniform(0.85, 1.2)
    leaf = (rng.uniform(0.16, 0.30), rng.uniform(0.40, 0.58), rng.uniform(0.14, 0.24), 1.0)
    if kind == "conifer":
        leaf = (0.10 + rng.uniform(0, 0.06), 0.30 + rng.uniform(0, 0.10), 0.14 + rng.uniform(0, 0.06), 1.0)
        mb.fcyl(x, 0, z, 0.22 * s, 1.6 * s, TRUNK, "plain", seg=6, r_top=0.15 * s)
        for k in range(3):
            mb.fcyl(x, (1.0 + k * 1.5) * s, z, (2.0 - k * 0.55) * s, 2.3 * s, leaf, "plain", seg=7, r_top=0.03)
    else:
        th = (2.4 if kind == "round" else 3.4) * s
        mb.fcyl(x, 0, z, 0.20 * s, th, TRUNK, "plain", seg=6, r_top=0.12 * s)
        rot = rng.uniform(0, 1)
        if kind == "round":
            mb.bicone(x, th + 1.5 * s, z, 2.5 * s, 2.0 * s, 1.7 * s, leaf, "plain", 7, rot)
            mb.bicone(x + 0.7 * s, th + 0.6 * s, z - 0.5 * s, 1.7 * s, 1.3 * s, 1.1 * s,
                      (leaf[0] * 0.9, leaf[1] * 0.92, leaf[2] * 0.9, 1.0), "plain", 6, rot)
        else:
            mb.bicone(x, th + 0.6 * s, z, 2.0 * s, 1.8 * s, 1.5 * s, leaf, "plain", 7, rot)
            mb.bicone(x, th + 2.6 * s, z, 1.5 * s, 1.6 * s, 1.3 * s,
                      (leaf[0] * 1.05, leaf[1] * 1.05, leaf[2], 1.0), "plain", 6, rot)
    cb.solid("tree", x, z, 0.24 * s, 0.24 * s, 0.1, False)


def bush(cb, x, z, rng, scale=1.0):
    mb = cb.mb(x, z)
    s = scale * rng.uniform(0.8, 1.3)
    c = (rng.uniform(0.18, 0.28), rng.uniform(0.38, 0.52), rng.uniform(0.15, 0.22), 1.0)
    mb.bicone(x, 0.45 * s, z, 0.75 * s, 0.55 * s, 0.4 * s, c, "plain", 6, rng.uniform(0, 1))


def bench(cb, x, z, dx, dz):
    mb = cb.mb(x, z)
    d = (dx, dz)
    obox(mb, x, z, 0.42, 0.48, 0.85, 0.22, d, WOOD)
    obox(mb, x, z, 0.48, 0.92, 0.85, 0.03, d, WOOD, off_d=-0.2)
    for s in (-0.7, 0.7):
        obox(mb, x, z, 0.0, 0.42, 0.04, 0.2, d, POLE, off_a=s)
    cb.solid("bench", x, z, *((0.24, 0.87) if dx else (0.87, 0.24)), 0.2, False)


def trash_bin(cb, x, z):
    mb = cb.mb(x, z)
    mb.fcyl(x, 0, z, 0.26, 0.9, GREEN_BIN, "plain", seg=8)
    mb.fcyl(x, 0.9, z, 0.28, 0.08, POLE, "plain", seg=8, cap=True)
    cb.solid("bin", x, z, 0.27, 0.27, 0.1, False)


def bus_stop(cb, x, z, dx, dz):
    """Shelter whose open side faces the road direction (dx, dz)."""
    mb = cb.mb(x, z)
    d = (dx, dz)
    obox(mb, x, z, 2.45, 2.6, 1.7, 0.85, d, (0.22, 0.26, 0.30, 1.0))
    obox(mb, x, z, 0.5, 2.45, 1.6, 0.04, d, (0.45, 0.62, 0.72, 1.0), off_d=-0.7)
    for s in (-1.6, 1.6):
        obox(mb, x, z, 0.0, 2.45, 0.05, 0.05, d, POLE, off_a=s, off_d=0.6)
        obox(mb, x, z, 0.0, 2.45, 0.05, 0.05, d, POLE, off_a=s, off_d=-0.7)
    obox(mb, x, z, 0.42, 0.48, 1.3, 0.2, d, WOOD, off_d=-0.45)
    sx, sz = x + (-dz) * 2.3, z + dx * 2.3                 # sign pole beside the shelter
    mb.fcyl(sx, 0, sz, 0.045, 2.8, POLE, "plain", seg=5)
    obox(mb, sx, sz, 2.2, 2.9, 0.3, 0.03, d, BLUE, off_d=0.06)
    cb.solid("bus_stop", x, z, *((0.9, 1.7) if dx else (1.7, 0.9)), 0.1, False)


def billboard(cb, x, z, dx, dz, rng):
    mb = cb.mb(x, z)
    d = (dx, dz)
    for s in (-3.2, 3.2):
        obox(mb, x, z, 0.0, 11.0, 0.18, 0.18, d, POLE, off_a=s)
    base = rng.choice(PAINTS)
    obox(mb, x, z, 7.0, 11.5, 4.6, 0.15, d, (0.2, 0.2, 0.22, 1.0))
    obox(mb, x, z, 7.2, 11.3, 4.4, 0.05, d, base, off_d=0.17, shade=False)
    for k in range(3):                       # simple graphic blocks so it reads as an advert
        obox(mb, x, z, 7.8 + k * 1.2, 8.6 + k * 1.2, 1.0 + k * 0.8, 0.02, d, WHITE, off_d=0.21, off_a=-2.0 + k * 1.6, shade=False)
    for s in (-3.2, 3.2):
        px, pz = x + (-dz) * s, z + dx * s
        cb.solid("billboard", px, pz, 0.22, 0.22, 0.1, True)


def fence_run(cb, x0, z0, x1, z1, color=WHITE, h=1.0, solid=True):
    """Picket fence along an axis-aligned line."""
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    length = abs(x1 - x0) + abs(z1 - z0)
    if length < 0.5:
        return
    n = max(1, int(length / 1.8))
    for k in range(n + 1):
        t = k / n
        px, pz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
        mb.fbox(px - 0.05, 0, pz - 0.05, px + 0.05, h, pz + 0.05, color, "plain")
    for y in (0.35, 0.8):
        mb.fbox(min(x0, x1) - 0.03, y, min(z0, z1) - 0.03, max(x0, x1) + 0.03, y + 0.07, max(z0, z1) + 0.03, color, "plain")
    if solid:
        cb.solid("fence", (x0 + x1) / 2, (z0 + z1) / 2, abs(x1 - x0) / 2 + 0.06, abs(z1 - z0) / 2 + 0.06, 0.1, False)


def guard_rail(cb, x0, z0, x1, z1):
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    mb.fbox(min(x0, x1) - 0.05, 0.45, min(z0, z1) - 0.05, max(x0, x1) + 0.05, 0.85, max(z0, z1) + 0.05, (0.7, 0.72, 0.74, 1), "plain")
    n = max(1, int((abs(x1 - x0) + abs(z1 - z0)) / 3.0))
    for k in range(n + 1):
        t = k / n
        px, pz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
        mb.fbox(px - 0.06, 0, pz - 0.06, px + 0.06, 0.9, pz + 0.06, POLE, "plain")
    cb.solid("barrier", (x0 + x1) / 2, (z0 + z1) / 2, abs(x1 - x0) / 2 + 0.1, abs(z1 - z0) / 2 + 0.1, 0.15, False)


# ----------------------------------------------------------------------------- parked cars
class CarLibrary:
    """Cached low-poly car meshes for static parked cars (body from procedural_car, box wheels)."""
    def __init__(self):
        self._cache = {}

    def get(self, style, paint_idx):
        key = (style, paint_idx)
        if key not in self._cache:
            from vehicles.procedural_car import build_body
            from vehicles.vehicle_specs import VEHICLE_SPECS
            spec = VEHICLE_SPECS[style]
            self._cache[key] = (spec, build_body(spec, PAINTS[paint_idx % len(PAINTS)]))
        return self._cache[key]


_LIB = CarLibrary()


def parked_car(cb, x, z, yaw_deg, rng):
    """Static parked car merged into the chunk mesh. yaw 0 = nose toward +Z, 90 = toward +X."""
    if cb.parked_budget <= 0:
        return False
    cb.parked_budget -= 1
    style = rng.choice(("sedan", "sedan", "sports"))
    spec, body = _LIB.get(style, rng.randrange(len(PAINTS)))
    mb = cb.mb(x, z)
    mb.add_mesh(body, (x, 0.0, z), yaw_deg, part="plain", part_map={"body": "plain", "tail": "plain"})
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    for sx in (-1, 1):
        for sz in (-1, 1):
            lx, lz = sx * spec.track / 2, sz * spec.wheelbase / 2
            wx, wz = x + lx * c + lz * s, z - lx * s + lz * c
            ww = spec.wheel_width / 2
            hx, hz = (ww, spec.wheel_radius) if abs(c) > 0.7 else (spec.wheel_radius, ww)
            mb.fbox(wx - hx, 0.0, wz - hz, wx + hx, spec.wheel_radius * 2, wz + hz, (0.05, 0.05, 0.055, 1), "plain", shade=False)
    hx, hz = (spec.width / 2, spec.length / 2) if abs(c) > 0.7 else (spec.length / 2, spec.width / 2)
    cb.solid("parked_car", x, z, hx - 0.03, hz - 0.03, 0.25, True)
    return True
