"""Road network geometry: carriageways, lane markings, sidewalks + curbs, zebra crossings, stop lines,
intersections (4-way / T / corner), the central roundabout, signals, signs, street furniture and the
lane graph (for Phase 3 traffic AI).

Conventions used by the segment builder ("AxisFrame"): a road runs along the 'along' axis at fixed
'across' offset c from its centre-line.  For a road along +Z (axis 'z') traffic in the +along direction
drives on c > 0 (right-hand traffic); for a road along +X (axis 'x') it drives on c < 0.
"""
import math
from dataclasses import dataclass

from environment import props
from environment.layout import (AVE_CW, CURB_H, N, RB_R_ISLAND, RB_R_OUT, RB_SW, S, SurfaceMap, cw,
                                is_avenue, is_roundabout, pos, row, sw)

UP = (0, 1, 0)
WHITE = (1, 1, 1, 1)
Y_PAINT = 0.03
PAINT_W = (0.92, 0.92, 0.90, 1.0)
PAINT_Y = (0.95, 0.75, 0.10, 1.0)
CURB_COL = (0.68, 0.68, 0.66, 1.0)
LAWN = (0.30, 0.50, 0.24, 1.0)
LIMIT_AVE, LIMIT_ST = 16.7, 11.1          # m/s (60 / 40 km/h)


@dataclass
class Lane:
    axis: str
    line: int
    seg: int
    direction: int            # +1 / -1 along the axis
    index: int                # 0 = inner lane
    c: float                  # across offset of the lane centre
    start: tuple              # world (x, z)
    end: tuple
    from_node: tuple
    to_node: tuple
    limit: float


class AxisFrame:
    def __init__(self, axis, line):
        self.axis, self.line = axis, line
        self.rs = 1 if axis == "z" else -1             # c-sign used by +along traffic
        self.u = (0.0, 1.0) if axis == "z" else (1.0, 0.0)   # unit 'along' vector (world)
        self.a = (1.0, 0.0) if axis == "z" else (0.0, 1.0)   # unit 'across' vector (world)

    def pt(self, along, c):
        return (self.line + c, along) if self.axis == "z" else (along, self.line + c)

    def rect(self, a0, c0, a1, c1):
        (xa, za), (xb, zb) = self.pt(a0, c0), self.pt(a1, c1)
        return min(xa, xb), min(za, zb), max(xa, xb), max(za, zb)

    def curb(self, side):                              # 'c+' / 'c-' -> world face name
        if self.axis == "z":
            return "xmax" if side == "c+" else "xmin"
        return "zmax" if side == "c+" else "zmin"


# ------------------------------------------------------------------------ primitive emitters
def asphalt(cb, x0, z0, x1, z1):
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    mb.fquad((x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1), UP, WHITE, "asphalt",
             uv=[(x0 / 6, z0 / 6), (x1 / 6, z0 / 6), (x1 / 6, z1 / 6), (x0 / 6, z1 / 6)], shade=False)
    cb.surface.fill_rect(SurfaceMap.ASPHALT, x0, z0, x1, z1)


def sidewalk(cb, x0, z0, x1, z1, curbs=(), y=CURB_H):
    if x1 - x0 < 0.05 or z1 - z0 < 0.05:
        return
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    mb.fquad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), UP, WHITE, "sidewalk",
             uv=[(x0 / 4, z0 / 4), (x1 / 4, z0 / 4), (x1 / 4, z1 / 4), (x0 / 4, z1 / 4)], shade=False)
    q = mb.fquad
    if "xmin" in curbs:
        q((x0, 0, z0), (x0, y, z0), (x0, y, z1), (x0, 0, z1), (-1, 0, 0), CURB_COL, "plain")
    if "xmax" in curbs:
        q((x1, 0, z0), (x1, y, z0), (x1, y, z1), (x1, 0, z1), (1, 0, 0), CURB_COL, "plain")
    if "zmin" in curbs:
        q((x0, 0, z0), (x1, 0, z0), (x1, y, z0), (x0, y, z0), (0, 0, -1), CURB_COL, "plain")
    if "zmax" in curbs:
        q((x0, 0, z1), (x1, 0, z1), (x1, y, z1), (x0, y, z1), (0, 0, 1), CURB_COL, "plain")
    cb.surface.fill_rect(SurfaceMap.SIDEWALK, x0, z0, x1, z1)


def paint(cb, x0, z0, x1, z1, color=PAINT_W, y=Y_PAINT):
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    mb.fquad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), UP, color, "paint", shade=False)


def _frange(a, b, step):
    v = a
    while v < b:
        yield v
        v += step


# ------------------------------------------------------------------------------- segments
def _control(li, node_k, rb):
    if rb:
        return "yield"
    if is_avenue(li) and is_avenue(node_k):
        return "signal"
    if not is_avenue(li):
        return "stop"
    return None


def build_segment(cb, axis, li, k, rng):
    f = AxisFrame(axis, pos(li))
    rs = f.rs
    ci, si, ri = cw(li), sw(li), row(li)
    avenue = is_avenue(li)
    ends = []
    for nk in (k, k + 1):
        ni, nj = (li, nk) if axis == "z" else (nk, li)
        rb = is_roundabout(ni, nj)
        r = row(nk)
        if rb:
            ends.append(dict(asph=22.0, sw=math.sqrt(RB_R_OUT ** 2 - ci ** 2), cross=29.6, stop=33.4, mark=34.4,
                             node=(ni, nj), ctrl="yield"))
        else:
            ends.append(dict(asph=r, sw=r, cross=r + 0.8, stop=r + 4.5, mark=r + 5.5, node=(ni, nj),
                             ctrl=_control(li, nk, False)))
    pa, pb = pos(k), pos(k + 1)
    A0, A1 = pa + ends[0]["asph"], pb - ends[1]["asph"]
    S0, S1 = pa + ends[0]["sw"], pb - ends[1]["sw"]
    M0, M1 = pa + ends[0]["mark"], pb - ends[1]["mark"]

    asphalt(cb, *f.rect(A0, -ci, A1, ci))
    sidewalk(cb, *f.rect(S0, -ri, S1, -ci), curbs=(f.curb("c+"),))
    sidewalk(cb, *f.rect(S0, ci, S1, ri), curbs=(f.curb("c-"),))

    pr = lambda a0, c0, a1, c1, col=PAINT_W: paint(cb, *f.rect(a0, c0, a1, c1), col)
    if avenue:
        for c0, c1 in ((0.38, 0.50), (-0.50, -0.38)):                  # double yellow around the median
            pr(M0, c0, M1, c1, PAINT_Y)
        for c0, c1 in ((ci - 0.55, ci - 0.41), (-(ci - 0.41), -(ci - 0.55))):   # solid edge lines
            pr(M0, c0, M1, c1)
        for sg in (1, -1):                                              # dashed lane divider
            for a in _frange(M0 + 1.0, M1 - 3.0, 9.0):
                pr(a, sg * 4.0 - 0.08, a + 3.0, sg * 4.0 + 0.08)
    else:
        for a in _frange(M0 + 1.0, M1 - 3.0, 9.0):
            pr(a, -0.06, a + 3.0, 0.06, PAINT_Y)
        pr(M0, 3.35, M1, 3.47)
        pr(M0, -3.47, M1, -3.35)

    # zebra crossings + stop / yield lines + control devices at both ends
    for e, end in enumerate(ends):
        if e == 0:
            a_c0, a_c1 = pa + end["cross"], pa + end["cross"] + 3.0
            a_s0, a_s1 = pa + end["stop"] - 0.4, pa + end["stop"]
            side, sgn_face, a_pole = -rs, +1, pa + end["stop"] + 0.5
        else:
            a_c0, a_c1 = pb - end["cross"] - 3.0, pb - end["cross"]
            a_s0, a_s1 = pb - end["stop"], pb - end["stop"] + 0.4
            side, sgn_face, a_pole = rs, -1, pb - end["stop"] - 0.5
        for c in _frange(-ci + 0.7, ci - 0.6, 1.1):
            pr(a_c0, c, a_c1, c + 0.55)
        if end["ctrl"] is not None:
            lo, hi = (0.5, ci) if avenue else (0.0, 3.4)
            pr(a_s0, min(side * lo, side * hi), a_s1, max(side * lo, side * hi))
            px, pz = f.pt(a_pole, side * (ci + 0.9))
            fx, fz = f.u[0] * sgn_face, f.u[1] * sgn_face
            if end["ctrl"] == "signal":
                props.traffic_signal(cb, px, pz, fx, fz)
                cb.signal_sites.append(dict(x=px, z=pz, fx=fx, fz=fz, node=end["node"], axis=axis))
            else:
                props.road_sign(cb, px, pz, fx, fz, end["ctrl"])
            cb.stop_lines.append(dict(node=end["node"], axis=axis, ctrl=end["ctrl"],
                                      pos=f.pt((a_s0 + a_s1) / 2, side * (lo + hi) / 2)))

    # lane graph
    lane_cs = (2.25, 5.75) if avenue else (1.7,)
    limit = LIMIT_AVE if avenue else LIMIT_ST
    for direction in (1, -1):
        sg = rs * direction
        for idx, lc in enumerate(lane_cs):
            p0, p1 = f.pt(A0, sg * lc), f.pt(A1, sg * lc)
            if direction == 1:
                cb.lanes.append(Lane(axis, li, k, 1, idx, sg * lc, p0, p1, ends[0]["node"], ends[1]["node"], limit))
            else:
                cb.lanes.append(Lane(axis, li, k, -1, idx, sg * lc, p1, p0, ends[1]["node"], ends[0]["node"], limit))
    cb.segments.append(dict(axis=axis, line=li, k=k, a0=A0, a1=A1, c=ci, row=ri, avenue=avenue))

    # ---------------------------------------------------------------- roadside furniture
    mid = (pos(k) + pos(k + 1)) / 2
    cx, cz = f.pt(mid, 0)
    downtown = math.hypot(cx, cz) < 330
    spacing = 32.0 if avenue else 38.0
    sides = (1, -1)
    for sg in sides:
        off = 0.0 if sg > 0 else spacing / 2
        for a in _frange(M0 + 6.0 + off, M1 - 5.0, spacing):
            x, z = f.pt(a, sg * (ci + 0.8))
            props.lamp(cb, x, z, -sg * f.a[0], -sg * f.a[1])
            ta = a + spacing / 2
            if ta < M1 - 5.0 and rng.random() < 0.9:
                tx, tz = f.pt(ta, sg * (ci + (2.0 if avenue else 1.8)))
                props.tree(cb, tx, tz, rng, scale=0.9 if avenue else 0.8)
        if downtown:
            for _ in range(2 if avenue else 1):
                a = rng.uniform(M0 + 10, M1 - 10)
                x, z = f.pt(a, sg * (ri - 0.9))
                props.bench(cb, x, z, -sg * f.a[0], -sg * f.a[1])
                bx, bz = f.pt(a + 1.8, sg * (ri - 0.9))
                props.trash_bin(cb, bx, bz)
    if avenue and rng.random() < 0.5:
        sg = rng.choice(sides)
        x, z = f.pt(mid + rng.uniform(-10, 10), sg * (ci + 1.7))
        props.bus_stop(cb, x, z, -sg * f.a[0], -sg * f.a[1])
    if avenue:
        for direction in (1, -1):
            if rng.random() < 0.4:
                sg = rs * direction
                a = M0 + 8 if direction == 1 else M1 - 8
                x, z = f.pt(a, sg * (ci + 0.9))
                props.road_sign(cb, x, z, -f.u[0] * direction, -f.u[1] * direction, "speed")
    else:                                              # parked cars in the parking lanes
        for sg in sides:
            heading = {("z", 1): 0, ("z", -1): 180, ("x", 1): 270, ("x", -1): 90}[(axis, sg)]
            for a in _frange(M0 + 3.0, M1 - 4.0, 6.8):
                if rng.random() < cb.parked_density:
                    x, z = f.pt(a, sg * 4.55)
                    props.parked_car(cb, x, z, heading, rng)


# ------------------------------------------------------------------------------- intersections
def build_node(cb, i, j, rng):
    px, pz = pos(i), pos(j)
    ri, rj, ci, cj = row(i), row(j), cw(i), cw(j)
    arms = {"E": i < N, "W": i > -N, "N": j < N, "S": j > -N}
    cb.nodes[(i, j)] = dict(pos=(px, pz), roundabout=is_roundabout(i, j), arms=arms,
                            signalised=is_avenue(i) and is_avenue(j) and not is_roundabout(i, j))
    if is_roundabout(i, j):
        _roundabout(cb, px, pz, rng)
        return
    asphalt(cb, px - (ri if arms["W"] else ci), pz - cj, px + (ri if arms["E"] else ci), pz + cj)
    asphalt(cb, px - ci, pz - (rj if arms["S"] else cj), px + ci, pz + (rj if arms["N"] else cj))
    for sx in (1, -1):
        for sz in (1, -1):
            x0, x1 = sorted((px + sx * ci, px + sx * ri))
            z0, z1 = sorted((pz + sz * cj, pz + sz * rj))
            curbs = []
            if arms["N" if sz > 0 else "S"]:
                curbs.append("xmin" if sx > 0 else "xmax")
            if arms["E" if sx > 0 else "W"]:
                curbs.append("zmin" if sz > 0 else "zmax")
            sidewalk(cb, x0, z0, x1, z1, curbs)
    for key, sx, sz in (("E", 1, 0), ("W", -1, 0), ("N", 0, 1), ("S", 0, -1)):
        if arms[key]:
            continue
        if sx:
            x0, x1 = sorted((px + sx * ci, px + sx * ri))
            sidewalk(cb, x0, pz - cj, x1, pz + cj, ("xmin" if sx > 0 else "xmax",))
        else:
            z0, z1 = sorted((pz + sz * cj, pz + sz * rj))
            sidewalk(cb, px - ci, z0, px + ci, z1, ("zmin" if sz > 0 else "zmax",))


def _arc_quads(cb, px, pz, r0, r1, a0, a1, y, steps, color, part, uvscale=None, curb_inner=False, curb_outer=False):
    mb = cb.mb(px + (r0 + r1) / 2 * math.cos((a0 + a1) / 2), pz + (r0 + r1) / 2 * math.sin((a0 + a1) / 2))
    for s in range(steps):
        t0, t1 = a0 + (a1 - a0) * s / steps, a0 + (a1 - a0) * (s + 1) / steps
        c0, s0, c1, s1 = math.cos(t0), math.sin(t0), math.cos(t1), math.sin(t1)
        p = [(px + r0 * c0, y, pz + r0 * s0), (px + r0 * c1, y, pz + r0 * s1),
             (px + r1 * c1, y, pz + r1 * s1), (px + r1 * c0, y, pz + r1 * s0)]
        uv = [(q[0] / uvscale, q[2] / uvscale) for q in p] if uvscale else None
        mb.fquad(*p, UP, color, part, uv=uv, shade=False)
        if curb_inner:
            tm = (t0 + t1) / 2
            mb.fquad((px + r0 * c0, 0, pz + r0 * s0), (px + r0 * c1, 0, pz + r0 * s1),
                     (px + r0 * c1, y, pz + r0 * s1), (px + r0 * c0, y, pz + r0 * s0),
                     (-math.cos(tm), 0, -math.sin(tm)), CURB_COL, "plain")
        if curb_outer:
            tm = (t0 + t1) / 2
            mb.fquad((px + r1 * c0, 0, pz + r1 * s0), (px + r1 * c1, 0, pz + r1 * s1),
                     (px + r1 * c1, y, pz + r1 * s1), (px + r1 * c0, y, pz + r1 * s0),
                     (math.cos(tm), 0, math.sin(tm)), CURB_COL, "plain")


def _roundabout(cb, px, pz, rng):
    # asphalt disc (fan of wedges), sidewalk ring between the arms, raised central island
    _arc_quads(cb, px, pz, 0.0, RB_R_OUT, 0, 2 * math.pi, 0.0, 48, WHITE, "asphalt", uvscale=6.0)
    cb.surface.fill_disc(SurfaceMap.ASPHALT, px, pz, RB_R_OUT)
    gap = math.asin(AVE_CW / RB_R_OUT)
    for q in range(4):
        a0, a1 = q * math.pi / 2 + gap, (q + 1) * math.pi / 2 - gap
        _arc_quads(cb, px, pz, RB_R_OUT, RB_R_OUT + RB_SW, a0, a1, CURB_H, 8, WHITE, "sidewalk", uvscale=4.0, curb_inner=True)
    cb.surface.fill_disc(SurfaceMap.SIDEWALK, px, pz, RB_R_OUT + RB_SW, RB_R_OUT)
    for q in range(4):                                   # restore carriageway cells overwritten by the ring
        ax, az = math.cos(q * math.pi / 2), math.sin(q * math.pi / 2)
        x0, x1 = sorted((px + ax * 20.0 - az * AVE_CW, px + ax * (RB_R_OUT + RB_SW) + az * AVE_CW))
        z0, z1 = sorted((pz + az * 20.0 + ax * AVE_CW, pz + az * (RB_R_OUT + RB_SW) - ax * AVE_CW))
        cb.surface.fill_rect(SurfaceMap.ASPHALT, x0, z0, x1, z1)
    # island
    yi = CURB_H + 0.02
    _arc_quads(cb, px, pz, 0.0, RB_R_ISLAND, 0, 2 * math.pi, yi, 32, LAWN, "plain", curb_outer=True)
    cb.surface.fill_disc(SurfaceMap.SIDEWALK, px, pz, RB_R_ISLAND)
    mb = cb.mb(px, pz)
    mb.fcyl(px, yi, pz, 3.4, 0.6, props.CONCRETE, "plain", seg=12, cap=True)
    mb.fcyl(px, yi + 0.6, pz, 0.8, 8.0, (0.75, 0.75, 0.72, 1), "plain", seg=8, r_top=0.5, cap=True)
    mb.bicone(px, yi + 9.2, pz, 1.4, 1.6, 0.8, (0.85, 0.7, 0.2, 1), "plain", 8)
    for k in range(6):
        a = k * math.pi / 3 + 0.3
        props.tree(cb, px + 8.5 * math.cos(a), pz + 8.5 * math.sin(a), rng, kind="round", scale=0.9)
    for k in range(12):
        a = k * math.pi / 6
        props.bush(cb, px + 12.0 * math.cos(a), pz + 12.0 * math.sin(a), rng)
    n = 20                                              # solid ring of oriented boxes
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        chord = RB_R_ISLAND * math.tan(math.pi / n) + 0.15
        cb.solid("island", px + (RB_R_ISLAND - 0.5) * math.cos(a), pz + (RB_R_ISLAND - 0.5) * math.sin(a),
                 0.6, chord, 0.2, False, psi_deg=-math.degrees(a))
    # lane markings on the circulating carriageway
    mid = (RB_R_ISLAND + RB_R_OUT) / 2
    for k in range(36):
        a0 = 2 * math.pi * k / 36
        if k % 2 == 0:
            _arc_quads_paint(cb, px, pz, mid - 0.08, mid + 0.08, a0, a0 + math.pi / 36 * 1.4)
    _arc_quads_paint(cb, px, pz, RB_R_ISLAND + 0.45, RB_R_ISLAND + 0.6, 0, 2 * math.pi, steps=48)
    for k in range(4):                                   # lamps on the outer sidewalk ring
        a = k * math.pi / 2 + math.pi / 4
        x, z = px + (RB_R_OUT + 1.6) * math.cos(a), pz + (RB_R_OUT + 1.6) * math.sin(a)
        dx, dz = (-1 if math.cos(a) > 0 else 1, 0) if abs(math.cos(a)) > abs(math.sin(a)) else (0, -1 if math.sin(a) > 0 else 1)
        props.lamp(cb, x, z, dx, dz)


def _arc_quads_paint(cb, px, pz, r0, r1, a0, a1, steps=3):
    _arc_quads(cb, px, pz, r0, r1, a0, a1, Y_PAINT, steps, PAINT_W, "paint")


def road_steps(cb):
    """Generator: yields (fraction, label) so the caller can time-slice generation across frames."""
    import random
    total = (2 * N + 1) ** 2 + 2 * (2 * N + 1) * (2 * N)
    done = 0
    for i in range(-N, N + 1):
        for j in range(-N, N + 1):
            build_node(cb, i, j, random.Random(cb.seed * 7919 + i * 131 + j))
            done += 1
        yield done / total, "Laying out intersections"
    for li in range(-N, N + 1):
        for k in range(-N, N):
            for axis in ("z", "x"):
                build_segment(cb, axis, li, k, random.Random(cb.seed * 104729 + li * 977 + k * 31 + (axis == "x")))
                done += 1
        yield done / total, "Paving roads"
