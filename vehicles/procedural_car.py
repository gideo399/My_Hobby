"""Procedural, stylised car bodies (no external assets needed).

Bodies are lofted from cross-section rings (rear -> front) so they have tapered noses, shoulders,
a separate glasshouse with raked windscreen/rear window, wheel-well openings, mirrors, lights,
grille, splitter and door shut-lines.  Everything is returned as MeshData parts:

    body  : paint + glass + trim + headlights (static vertex colours)
    tail  : rear lights (own entity so the brake light can change brightness)
    wheel : one tyre+rim mesh per side (see build_wheel)

Units are metres; the model origin is the centre of the wheelbase on the ground, +Z forward.
"""
import math

from utilities.mesh_builder import MeshBuilder

GLASS = (0.06, 0.09, 0.13, 1.0)
TRIM = (0.035, 0.035, 0.04, 1.0)
UNDER = (0.05, 0.05, 0.05, 1.0)
CHROME = (0.78, 0.80, 0.84, 1.0)
HEAD = (1.0, 0.95, 0.75, 1.0)
TAIL = (1.0, 0.12, 0.08, 1.0)
TIRE = (0.05, 0.05, 0.055, 1.0)
RIM = (0.74, 0.76, 0.80, 1.0)

# body stations: (t along length 0=rear..1=front, y_bottom, y_belt, y_top, half-width fraction)
# cabin stations: (t, y_roof or None (flush with body), base half-width frac, roof half-width frac)
STYLES = {
    "sedan": dict(
        body=[(0.000, 0.46, 0.70, 0.84, 0.74), (0.025, 0.34, 0.68, 0.94, 0.92),
              (0.080, 0.22, 0.66, 0.99, 0.98), (0.250, 0.20, 0.66, 0.99, 1.00),
              (0.620, 0.20, 0.66, 0.93, 1.00), (0.740, 0.20, 0.64, 0.91, 1.00),
              (0.900, 0.24, 0.62, 0.85, 0.98), (0.970, 0.30, 0.58, 0.76, 0.92),
              (1.000, 0.42, 0.54, 0.64, 0.76)],
        cabin=[(0.285, None, 0.88, 0.78), (0.335, 1.42, 0.87, 0.74), (0.560, 1.46, 0.87, 0.74),
               (0.640, 1.44, 0.87, 0.74), (0.735, None, 0.88, 0.80)],
        head=dict(t=0.962, y=0.66, x=0.66, size=(0.34, 0.11, 0.12)),
        tail=dict(t=0.034, y=0.80, x=0.66, size=(0.38, 0.10, 0.10)),
        grille_y=0.46, lip_y=0.34, rear_strip_y=0.34, doors=(0.40, 0.58),
        exhaust=False,
    ),
    "sports": dict(
        body=[(0.000, 0.34, 0.52, 0.64, 0.74), (0.030, 0.24, 0.54, 0.80, 0.90),
              (0.120, 0.16, 0.54, 0.88, 0.98), (0.280, 0.16, 0.54, 0.90, 1.00),
              (0.420, 0.16, 0.54, 0.84, 1.00), (0.600, 0.16, 0.54, 0.76, 1.00),
              (0.800, 0.16, 0.52, 0.64, 0.98), (0.930, 0.18, 0.46, 0.55, 0.94),
              (0.980, 0.22, 0.42, 0.48, 0.86), (1.000, 0.30, 0.40, 0.44, 0.70)],
        cabin=[(0.360, None, 0.88, 0.74), (0.425, 1.16, 0.86, 0.66), (0.520, 1.21, 0.86, 0.64),
               (0.600, 1.19, 0.86, 0.64), (0.700, None, 0.88, 0.76)],
        head=dict(t=0.958, y=0.50, x=0.70, size=(0.40, 0.08, 0.12)),
        tail=dict(t=0.030, y=0.66, x=0.68, size=(0.44, 0.08, 0.10)),
        grille_y=0.34, lip_y=0.24, rear_strip_y=0.28, doors=(0.50,),
        exhaust=True,
    ),
}


def _interp(stations, t, idx):
    if t <= stations[0][0]:
        return stations[0][idx]
    for s0, s1 in zip(stations, stations[1:]):
        if t <= s1[0]:
            k = (t - s0[0]) / (s1[0] - s0[0])
            return s0[idx] + (s1[idx] - s0[idx]) * k
    return stations[-1][idx]


def build_body(spec, paint):
    st = STYLES[spec.style]
    L, W2 = spec.length, spec.width / 2.0
    body_hw = W2 - 0.04                    # tyres protrude 4 cm beyond the body sides
    mb = MeshBuilder(bake_light=True)
    z_of = lambda t: (t - 0.5) * L

    # ---- lower body loft ----
    rings = []
    for t, yb, ybelt, ytop, hwf in st["body"]:
        hw, z = body_hw * hwf, z_of(t)
        ylow = yb + 0.35 * (ybelt - yb)
        rings.append([(-hw * 0.88, yb, z), (hw * 0.88, yb, z), (hw, ylow, z), (hw, ybelt, z),
                      (hw * 0.90, ytop, z), (-hw * 0.90, ytop, z), (-hw, ybelt, z), (-hw, ylow, z)])
    colour = lambda n: UNDER if n[1] < -0.6 else paint
    mb.loft(rings, colour, "body", cap_start=(0, 0, -1), cap_end=(0, 0, 1))

    # ---- glasshouse ----
    crings = []
    for t, yroof, hwb, hwr in st["cabin"]:
        base = _interp(st["body"], t, 3) - 0.015
        roof = base if yroof is None else yroof
        crings.append([(-hwb * body_hw, base, z_of(t)), (hwb * body_hw, base, z_of(t)),
                       (hwr * body_hw, roof, z_of(t)), (-hwr * body_hw, roof, z_of(t))])
    mb.loft(crings, lambda n: paint if n[1] > 0.9 else GLASS, "body", skip_edges=(0,))
    front_t = st["cabin"][-1][0]
    base_front = _interp(st["body"], front_t, 3)

    # ---- lights, grille, splitter, plates of trim ----
    h = st["head"]
    for sx in (-1, 1):
        mb.box((sx * h["x"] * body_hw, h["y"], z_of(h["t"])), h["size"], HEAD, part="body", shade=False)
    tl = st["tail"]
    for sx in (-1, 1):
        mb.box((sx * tl["x"] * body_hw, tl["y"], z_of(tl["t"])), tl["size"], TAIL, part="tail", shade=False)
    mb.box((0, st["grille_y"], z_of(0.975)), (body_hw * 0.62, 0.13, 0.09), TRIM, part="body")
    mb.box((0, st["lip_y"], z_of(0.985)), (body_hw * 1.50, 0.06, 0.14), TRIM, part="body")
    mb.box((0, st["rear_strip_y"], z_of(0.012)), (body_hw * 1.60, 0.08, 0.12), TRIM, part="body")
    if st["exhaust"]:
        for sx in (-1, 1):
            mb.box((sx * 0.38, 0.27, z_of(-0.002)), (0.11, 0.07, 0.10), CHROME, part="body")

    # ---- mirrors ----
    for sx in (-1, 1):
        mb.box((sx * (body_hw * 0.88 + 0.07), base_front + 0.10, z_of(front_t - 0.035)),
               (0.14, 0.10, 0.20), paint, part="body")

    # ---- door shut lines ----
    for t in st["doors"]:
        y0 = _interp(st["body"], t, 2) - 0.03            # just under the belt line
        y1 = _interp(st["body"], t, 1) + 0.10            # down to the sill
        for sx in (-1, 1):
            mb.box((sx * (body_hw + 0.004), (y0 + y1) / 2, z_of(t)), (0.012, y0 - y1, 0.014), TRIM, part="body")

    # ---- wheel-well openings (dark half discs behind each wheel) ----
    R = spec.wheel_radius
    for sx in (-1, 1):
        for sz in (-1, 1):
            mb.sector((sx * (body_hw + 0.006), R, sz * spec.wheelbase / 2), R + 0.055,
                      math.radians(-100), math.radians(100), TRIM, sx, part="body")
    return mb


def build_wheel(spec, side):
    """Tyre + 5-spoke rim. `side` = +1 if the outer face points toward +X, -1 toward -X."""
    mb = MeshBuilder(bake_light=False)
    R, w = spec.wheel_radius, spec.wheel_width
    mb.frustum((0, 0, 0), R, R, w, TIRE, axis="x", segments=22, part="wheel")
    xo = side * (w / 2 + 0.004)
    rr = R * 0.66
    n = 10
    for k in range(0, n, 2):                       # five silver wedges = five spokes
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0 = (xo, rr * math.cos(a0), rr * math.sin(a0))
        p1 = (xo, rr * math.cos(a1), rr * math.sin(a1))
        mb.tri((xo, 0, 0), p0, p1, RIM, "wheel", outward=(side, 0, 0), shade=False)
    mb.frustum((side * (w / 2 + 0.006), 0, 0), R * 0.20, R * 0.20, 0.012, CHROME, axis="x", segments=10, part="wheel")
    return mb
