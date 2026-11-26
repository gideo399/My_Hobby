"""Building and block generators (all footprints are axis-aligned and face a street).

Facades are textured (windows come from the per-style textures in core/asset_manager.py) and tiled so
windows land on whole bays and floors; geometry is reserved for things you can see in silhouette:
setbacks, podiums, parapets, rooftop plant, awnings, balconies, pitched roofs, chimneys, garages, doors.

Block kinds: downtown (towers/offices on a paved plaza), commercial (shops / mixed-use / offices),
residential (houses + small apartment blocks), park, parking lot.
"""
import math

from environment import props
from environment.layout import CURB_H, SurfaceMap, block_rect
from environment.props import obox

ROOF_TAR = (0.33, 0.33, 0.35, 1.0)
ROOF_TILES = [(0.52, 0.24, 0.17, 1), (0.30, 0.30, 0.34, 1), (0.40, 0.30, 0.22, 1), (0.22, 0.26, 0.30, 1)]
PASTELS = [(1.0, 1.0, 1.0, 1), (1.0, 0.94, 0.82, 1), (0.84, 0.90, 1.0, 1), (0.88, 1.0, 0.88, 1), (1.0, 0.88, 0.88, 1),
           (0.95, 0.90, 0.75, 1)]
BRICK_TINTS = [(1.0, 1.0, 1.0, 1), (1.0, 0.90, 0.80, 1), (0.82, 0.78, 0.76, 1), (0.95, 0.80, 0.70, 1)]
GLASS_TINTS = [(0.85, 0.95, 1.0, 1), (0.92, 1.0, 0.95, 1), (0.80, 0.86, 0.92, 1), (1.0, 0.96, 0.88, 1)]
AWNINGS = [(0.75, 0.12, 0.10, 1), (0.10, 0.30, 0.60, 1), (0.12, 0.45, 0.25, 1), (0.85, 0.60, 0.10, 1), (0.40, 0.15, 0.45, 1)]
DARK = (0.10, 0.10, 0.12, 1)
CONCRETE = props.CONCRETE
CENTER_EXCLUSION = 34.0       # keep buildings out of the roundabout


class LotFrame:
    """Local lot coordinates: u = lateral offset from lot centre, v = depth from the street edge."""
    def __init__(self, rect, f):
        x0, z0, x1, z1 = rect
        self.f, self.t = f, (-f[1], f[0])
        self.cx, self.cz = (x0 + x1) / 2, (z0 + z1) / 2
        self.W = (x1 - x0) if f[1] else (z1 - z0)
        self.D = (z1 - z0) if f[1] else (x1 - x0)
        self.ox, self.oz = self.cx + f[0] * self.D / 2, self.cz + f[1] * self.D / 2

    def pt(self, u, v):
        return self.ox + self.t[0] * u - self.f[0] * v, self.oz + self.t[1] * u - self.f[1] * v

    def rect(self, u0, u1, v0, v1):
        a, b = self.pt(u0, v0), self.pt(u1, v1)
        return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def _near_center(rect, r=CENTER_EXCLUSION):
    x0, z0, x1, z1 = rect
    nx, nz = min(max(0.0, x0), x1) if x0 > 0 else (x1 if x1 < 0 else 0.0), min(max(0.0, z0), z1) if z0 > 0 else (z1 if z1 < 0 else 0.0)
    return math.hypot(nx, nz) < r


def register(cb, rect, kind="building", restitution=0.12):
    x0, z0, x1, z1 = rect
    cb.solid(kind, (x0 + x1) / 2, (z0 + z1) / 2, (x1 - x0) / 2, (z1 - z0) / 2, restitution, True)
    if kind == "building":
        cb.building_rects.append(rect)


def tier(cb, rect, y0, floors, fh, style, tint, rng, bay=3.6):
    x0, z0, x1, z1 = rect
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    cells = (4, 1) if style == "shop" else (4, 4)
    mb.facade_walls(x0, z0, x1, z1, y0, y0 + floors * fh, tint, "f_" + style, bay, fh, cells, rng)
    return y0 + floors * fh


def roof_flat(cb, rect, y, rng, equip=True, parapet=0.8, pcol=(0.62, 0.62, 0.60, 1)):
    x0, z0, x1, z1 = rect
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    mb.fquad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), (0, 1, 0), ROOF_TAR, "plain")
    if parapet:
        t = 0.3
        mb.fbox(x0, y, z0, x1, y + parapet, z0 + t, pcol, "plain")
        mb.fbox(x0, y, z1 - t, x1, y + parapet, z1, pcol, "plain")
        mb.fbox(x0, y, z0 + t, x0 + t, y + parapet, z1 - t, pcol, "plain")
        mb.fbox(x1 - t, y, z0 + t, x1, y + parapet, z1 - t, pcol, "plain")
    if equip and (x1 - x0) > 8 and (z1 - z0) > 8:
        for _ in range(rng.randint(1, 3)):
            w, d, h = rng.uniform(1.5, 3.5), rng.uniform(1.5, 3.5), rng.uniform(1.0, 2.2)
            px = rng.uniform(x0 + 2 + w / 2, x1 - 2 - w / 2)
            pz = rng.uniform(z0 + 2 + d / 2, z1 - 2 - d / 2)
            mb.fbox(px - w / 2, y, pz - d / 2, px + w / 2, y + h, pz + d / 2, (0.55, 0.57, 0.58, 1), "plain")


def front_features(cb, rect, f, y_ground_top, rng, awning=True, door=True):
    """Entrance door, optional shop awning + fascia on the street-facing wall."""
    x0, z0, x1, z1 = rect
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    fx, fz = f
    px, pz = cx + fx * ((x1 - x0) / 2 if fx else 0), cz + fz * ((z1 - z0) / 2 if fz else 0)
    width = (z1 - z0) if fx else (x1 - x0)
    if door:
        obox(mb, px, pz, 0.0, 2.4, 0.9, 0.06, f, DARK, off_d=0.05)
    if awning and width > 8:
        col = rng.choice(AWNINGS)
        obox(mb, px, pz, y_ground_top - 1.5, y_ground_top - 1.35, width / 2 - 0.5, 0.9, f, col, off_d=0.9)
        obox(mb, px, pz, y_ground_top - 1.35, y_ground_top - 0.8, width / 2 - 0.5, 0.03, f, col, off_d=1.78)


def balconies(cb, rect, f, floors, fh, rng, y0=0.0, bay=3.6):
    x0, z0, x1, z1 = rect
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    fx, fz = f
    px, pz = cx + fx * ((x1 - x0) / 2 if fx else 0), cz + fz * ((z1 - z0) / 2 if fz else 0)
    width = (z1 - z0) if fx else (x1 - x0)
    n = max(1, round(width / bay))
    for fl in range(1, floors):
        y = y0 + fl * fh
        for k in range(0, n, 2):
            a = (k + 0.5) * width / n - width / 2
            obox(mb, px, pz, y, y + 0.14, 0.95, 0.65, f, CONCRETE, off_d=0.65, off_a=a)
            obox(mb, px, pz, y + 0.14, y + 1.05, 0.95, 0.03, f, (0.25, 0.27, 0.3, 1), off_d=1.27, off_a=a)


# =================================================================================== buildings
def tower(cb, rect, f, rng, floors):
    x0, z0, x1, z1 = rect
    ins = 1.5
    base = (x0 + ins, z0 + ins, x1 - ins, z1 - ins)
    y = tier(cb, base, 0.0, 1, 4.6, "shop", (0.9, 0.9, 0.9, 1), rng, bay=3.4)
    front_features(cb, base, f, y, rng, awning=False)
    y = tier(cb, base, y, 2, 4.0, "office", (0.85, 0.85, 0.88, 1), rng)
    roof_flat(cb, base, y, rng, equip=False, parapet=0.5)
    s = rng.uniform(4.5, 7.0)
    t1 = (base[0] + s, base[1] + s, base[2] - s, base[3] - s)
    tint = rng.choice(GLASS_TINTS)
    top_floors = max(6, floors - 3)
    split = top_floors if floors < 26 else int(top_floors * 0.7)
    y = tier(cb, t1, y, split, 3.8, "glass", tint, rng, bay=3.4)
    if floors >= 26:
        s2 = rng.uniform(3.0, 4.5)
        t2 = (t1[0] + s2, t1[1] + s2, t1[2] - s2, t1[3] - s2)
        roof_flat(cb, t1, y, rng, equip=False, parapet=0.4)
        y = tier(cb, t2, y, top_floors - split, 3.8, "glass", tint, rng, bay=3.4)
        t1 = t2
    roof_flat(cb, t1, y, rng, equip=True, parapet=1.0)
    mb = cb.mb((t1[0] + t1[2]) / 2, (t1[1] + t1[3]) / 2)
    if floors >= 24:
        sx, sz = (t1[0] + t1[2]) / 2, (t1[1] + t1[3]) / 2
        mb.fcyl(sx, y, sz, 0.35, 16.0, (0.7, 0.7, 0.72, 1), "plain", seg=6, r_top=0.08)
        mb.fbox(sx - 3, y + 1.0, sz - 3, sx + 3, y + 3.5, sz + 3, (0.5, 0.52, 0.55, 1), "plain")
    register(cb, base)
    cb.stats["towers"] += 1


def office(cb, rect, f, rng, floors):
    x0, z0, x1, z1 = rect
    base = (x0 + 1.0, z0 + 1.0, x1 - 1.0, z1 - 1.0)
    y = tier(cb, base, 0.0, 1, 4.4, "shop", (0.92, 0.92, 0.92, 1), rng, bay=3.4)
    front_features(cb, base, f, y, rng, awning=False)
    style = rng.choice(("office", "office", "glass"))
    tint = (0.95, 0.95, 0.95, 1) if style == "office" else rng.choice(GLASS_TINTS)
    y = tier(cb, base, y, floors - 1, 3.7, style, tint, rng)
    roof_flat(cb, base, y, rng)
    register(cb, base)
    cb.stats["offices"] += 1


def apartment(cb, rect, f, rng, floors, mixed=False):
    x0, z0, x1, z1 = rect
    base = (x0 + 0.8, z0 + 0.8, x1 - 0.8, z1 - 0.8)
    tint = rng.choice(BRICK_TINTS)
    y = 0.0
    if mixed:
        y = tier(cb, base, 0.0, 1, 4.2, "shop", (0.92, 0.92, 0.92, 1), rng, bay=3.4)
        front_features(cb, base, f, y, rng)
    top = tier(cb, base, y, floors - (1 if mixed else 0), 3.3, "brick", tint, rng, bay=3.4)
    balconies(cb, base, f, floors - (1 if mixed else 0), 3.3, rng, y0=y)
    if not mixed:
        front_features(cb, base, f, 3.3, rng, awning=False)
    roof_flat(cb, base, top, rng, equip=True)
    mb = cb.mb((base[0] + base[2]) / 2, (base[1] + base[3]) / 2)
    if rng.random() < 0.5:                               # water tank on the roof
        tx, tz = (base[0] + base[2]) / 2 + rng.uniform(-3, 3), (base[1] + base[3]) / 2 + rng.uniform(-3, 3)
        mb.fcyl(tx, top, tz, 1.5, 2.4, (0.45, 0.30, 0.20, 1), "plain", seg=8, r_top=1.7, cap=True)
    register(cb, base)
    cb.stats["apartments"] += 1


def shop(cb, rect, f, rng, floors):
    x0, z0, x1, z1 = rect
    base = (x0 + 0.3, z0 + 0.3, x1 - 0.3, z1 - 0.3)
    y = tier(cb, base, 0.0, 1, 4.2, "shop", rng.choice(((1, 1, 1, 1), (1, 0.9, 0.85, 1), (0.9, 0.95, 1, 1))), rng, bay=3.4)
    front_features(cb, base, f, y, rng)
    if floors > 1:
        y = tier(cb, base, y, floors - 1, 3.4, rng.choice(("brick", "concrete")), rng.choice(BRICK_TINTS), rng)
    roof_flat(cb, base, y, rng, parapet=0.6)
    register(cb, base)
    cb.stats["shops"] += 1


def house(cb, rect, f, rng):
    fr = LotFrame(rect, f)
    W, D = fr.W, fr.D
    bw = min(W - 9.0, 11.5)
    bd = rng.uniform(8.5, 10.5)
    two = rng.random() < 0.55
    fh = 3.0
    floors = 2 if two else 1
    v0 = 7.0
    u0 = -W / 2 + 2.0                 # house sits toward one side, garage + driveway on the other
    body = fr.rect(u0, u0 + bw, v0, v0 + bd)
    tint = rng.choice(PASTELS)
    top = tier(cb, body, 0.0, floors, fh, "siding", tint, rng, bay=3.2)
    # gable roof (ridge parallel to the street), with overhang
    ov, rise = 0.45, rng.uniform(2.0, 2.8)
    rcol = rng.choice(ROOF_TILES)
    a, b = u0 - ov, u0 + bw + ov
    ve, vf, vm = v0 - ov, v0 + bd + ov, v0 + bd / 2
    mb = cb.mb(*fr.pt((a + b) / 2, vm))
    def P(u, v, y):
        wx, wz = fr.pt(u, v)
        return (wx, y, wz)
    mb.quad(P(a, ve, top - 0.1), P(b, ve, top - 0.1), P(b, vm, top + rise), P(a, vm, top + rise), rcol, "plain", outward=(0, 1, 0))
    mb.quad(P(a, vf, top - 0.1), P(b, vf, top - 0.1), P(b, vm, top + rise), P(a, vm, top + rise), rcol, "plain", outward=(0, 1, 0))
    for u, sgn in ((u0, -1), (u0 + bw, 1)):               # gable end walls
        tx, tz = fr.t
        mb.tri(P(u, v0, top), P(u, v0 + bd, top), P(u, vm, top + rise - 0.1), tint, "plain", outward=(tx * sgn * -1, 0, tz * sgn * -1))
    cu, cv = u0 + bw * 0.7, vm
    cx_, cz_ = fr.pt(cu, cv)
    mb.fbox(cx_ - 0.4, top, cz_ - 0.4, cx_ + 0.4, top + rise + 1.0, cz_ + 0.4, (0.5, 0.25, 0.2, 1), "plain")
    # front door + step
    dx_, dz_ = fr.pt(u0 + bw * 0.3, v0)
    obox(mb, dx_, dz_, 0.0, 2.2, 0.55, 0.05, f, rng.choice(AWNINGS))
    obox(mb, dx_, dz_, 0.0, 0.18, 1.0, 0.6, f, CONCRETE, off_d=0.6)
    register(cb, body, "building")
    # garage wing + driveway
    gw = 4.4
    gu0 = u0 + bw
    if gu0 + gw < W / 2 - 0.5:
        g = fr.rect(gu0, gu0 + gw, v0 + 0.5, v0 + 6.5)
        gtop = tier(cb, g, 0.0, 1, 3.0, "siding", tint, rng, bay=3.2)
        roof_flat(cb, g, gtop, rng, equip=False, parapet=0.0)
        gx, gz = fr.pt(gu0 + gw / 2, v0 + 0.5)
        obox(mb, gx, gz, 0.0, 2.3, 1.8, 0.05, f, (0.80, 0.80, 0.78, 1), off_d=0.0)
        register(cb, g, "building")
        dr = fr.rect(gu0 + 0.2, gu0 + gw - 0.2, 0.0, v0 + 0.5)
        mb.fquad((dr[0], 0.02, dr[1]), (dr[2], 0.02, dr[1]), (dr[2], 0.02, dr[3]), (dr[0], 0.02, dr[3]), (0, 1, 0),
                 (0.55, 0.55, 0.55, 1), "plain", shade=False)
        fence_gap = (gu0 - 0.3, gu0 + gw + 0.3)
    else:
        fence_gap = None
    # front fence with a gap for the driveway, path to the door, trees
    fv = 1.2
    segs = [(-W / 2 + 0.3, W / 2 - 0.3)]
    if fence_gap:
        segs = [(-W / 2 + 0.3, fence_gap[0]), (fence_gap[1], W / 2 - 0.3)]
    for ua, ub in segs:
        if ub - ua > 1.0:
            (xa, za), (xb, zb) = fr.pt(ua, fv), fr.pt(ub, fv)
            props.fence_run(cb, xa, za, xb, zb, solid=True)
    pa = fr.rect(u0 + bw * 0.3 - 0.6, u0 + bw * 0.3 + 0.6, 0.0, v0 + 0.6)
    mb.fquad((pa[0], 0.02, pa[1]), (pa[2], 0.02, pa[1]), (pa[2], 0.02, pa[3]), (pa[0], 0.02, pa[3]), (0, 1, 0),
             (0.62, 0.60, 0.56, 1), "plain", shade=False)
    tx_, tz_ = fr.pt(rng.uniform(-W / 2 + 3, u0 - 0.5 if u0 > -W / 2 + 3.5 else -W / 2 + 3.5), rng.uniform(2.8, 5.0))
    props.tree(cb, tx_, tz_, rng, scale=0.8)
    bx, bz = fr.pt(u0 + 1.0, v0 - 0.7)
    props.bush(cb, bx, bz, rng, 0.8)
    bx, bz = fr.pt(u0 + bw - 1.0, v0 - 0.7)
    props.bush(cb, bx, bz, rng, 0.8)
    if rng.random() < 0.6:
        rx, rz = fr.pt(rng.uniform(-W / 2 + 3, W / 2 - 3), v0 + bd + rng.uniform(3, 6))
        props.tree(cb, rx, rz, rng, scale=0.9)
    cb.stats["houses"] += 1


# ===================================================================================== open areas
def split_span(L, wmin, wmax, rng):
    n = max(1, round(L / ((wmin + wmax) / 2.0)))
    w = [rng.uniform(0.85, 1.15) for _ in range(n)]
    tot = sum(w)
    out, p = [], 0.0
    for k in range(n):
        out.append((p, p + L * w[k] / tot))
        p += L * w[k] / tot
    return out


def frontage_lots(rect, depth, wmin, wmax, rng):
    x0, z0, x1, z1 = rect
    lots = []
    for a, b in split_span(x1 - x0, wmin, wmax, rng):
        lots.append(((x0 + a, z0, x0 + b, z0 + depth), (0, -1)))
        lots.append(((x0 + a, z1 - depth, x0 + b, z1), (0, 1)))
    for a, b in split_span(z1 - z0 - 2 * depth, wmin, wmax, rng):
        lots.append(((x0, z0 + depth + a, x0 + depth, z0 + depth + b), (-1, 0)))
        lots.append(((x1 - depth, z0 + depth + a, x1, z0 + depth + b), (1, 0)))
    return lots


def plaza(cb, rect, rng):
    x0, z0, x1, z1 = rect
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    mb = cb.mb(cx, cz)
    for _ in range(4):
        px, pz = rng.uniform(x0 + 4, x1 - 4), rng.uniform(z0 + 4, z1 - 4)
        if math.hypot(px, pz) > 31:
            mb.fbox(px - 1.2, CURB_H, pz - 1.2, px + 1.2, CURB_H + 0.5, pz + 1.2, CONCRETE, "plain")
            props.tree(cb, px, pz, rng, kind="round", scale=0.7)
    bx, bz = rng.uniform(x0 + 5, x1 - 5), rng.uniform(z0 + 5, z1 - 5)
    if math.hypot(bx, bz) > 31:
        props.bench(cb, bx, bz, 0, 1)


def garden_ground(cb, rect, rng, trees=3):
    x0, z0, x1, z1 = rect
    for _ in range(trees):
        props.tree(cb, rng.uniform(x0 + 3, x1 - 3), rng.uniform(z0 + 3, z1 - 3), rng, scale=1.0)


def parking_area(cb, rect, rng, fill=0.5):
    x0, z0, x1, z1 = rect
    mb = cb.mb((x0 + x1) / 2, (z0 + z1) / 2)
    mb.fquad((x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1), (0, 1, 0), (1, 1, 1, 1), "asphalt",
             uv=[(x0 / 6, z0 / 6), (x1 / 6, z0 / 6), (x1 / 6, z1 / 6), (x0 / 6, z1 / 6)], shade=False)
    cb.surface.fill_rect(SurfaceMap.ASPHALT, x0, z0, x1, z1)
    paint = lambda a, b, c, d: mb.fquad((a, 0.03, b), (c, 0.03, b), (c, 0.03, d), (a, 0.03, d), (0, 1, 0), (0.92, 0.92, 0.9, 1), "paint", shade=False)
    xs = []
    x = x0 + 2.0
    while x + 2.7 <= x1 - 2.0:
        xs.append(x)
        x += 2.7
    z = z0 + 2.0
    while xs and z + 17.2 <= z1 - 1.5:
        for (ra, rb), yaw in (((z, z + 5.4), 0), ((z + 11.8, z + 17.2), 180)):   # nose-in toward the aisle
            for xx in xs + [xs[-1] + 2.7]:
                paint(xx - 0.05, ra, xx + 0.05, rb)
            paint(xs[0], ra - 0.05, xs[-1] + 2.7, ra + 0.05)
            paint(xs[0], rb - 0.05, xs[-1] + 2.7, rb + 0.05)
            for xx in xs:
                if rng.random() < fill:
                    props.parked_car(cb, xx + 1.35, (ra + rb) / 2, yaw, rng)
        z += 18.2
    for (px, pz) in ((x0 + 3, z0 + 3), (x1 - 3, z0 + 3), (x0 + 3, z1 - 3), (x1 - 3, z1 - 3)):
        props.lamp(cb, px, pz, 1 if px < (x0 + x1) / 2 else -1, 0, h=8.0)


def park(cb, rect, rng):
    x0, z0, x1, z1 = rect
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    mb = cb.mb(cx, cz)
    PATH_COL = (0.74, 0.67, 0.52, 1)
    quad = lambda a, b, c, d, col, y=0.01: mb.fquad((a, y, b), (c, y, b), (c, y, d), (a, y, d), (0, 1, 0), col, "plain", shade=False)
    for rr in ((x0, cz - 1.5, x1, cz + 1.5), (cx - 1.5, z0, cx + 1.5, z1)):
        quad(*rr, PATH_COL)
        cb.surface.fill_rect(SurfaceMap.PATH, *rr)
    px0, pz0 = cx - 34, cz - 30
    quad(px0, pz0, px0 + 20, pz0 + 13, (0.22, 0.42, 0.58, 1), y=-0.035)
    cb.solid("pond", px0 + 10, pz0 + 6.5, 10.0, 6.5, 0.05, False)
    for k in range(5):                                          # rocks on the shore
        mb.fbox(px0 + 2 + k * 3.8, -0.06, pz0 - 0.5, px0 + 3.2 + k * 3.8, 0.35, pz0 + 0.7, (0.5, 0.5, 0.48, 1), "plain")
    placed = 0
    tries = 0
    while placed < 30 and tries < 200:
        tries += 1
        x, z = rng.uniform(x0 + 3, x1 - 3), rng.uniform(z0 + 3, z1 - 3)
        if abs(x - cx) < 3.5 or abs(z - cz) < 3.5:
            continue
        if px0 - 3 < x < px0 + 23 and pz0 - 3 < z < pz0 + 16:
            continue
        props.tree(cb, x, z, rng, scale=1.1)
        placed += 1
    for _ in range(14):
        x, z = rng.uniform(x0 + 3, x1 - 3), rng.uniform(z0 + 3, z1 - 3)
        if abs(x - cx) > 3 and abs(z - cz) > 3 and not (px0 - 2 < x < px0 + 22 and pz0 - 2 < z < pz0 + 15):
            props.bush(cb, x, z, rng)
    for k in range(3):
        for sg in (-1, 1):
            props.bench(cb, cx + sg * 2.4, cz + (k - 1) * 17.0 + 8.0, -sg, 0)
    props.trash_bin(cb, cx + 2.4, cz + 3.0)
    props.trash_bin(cb, cx - 3.0, cz - 5.0)
    # simple playground: swing frame + climbing blocks
    gx, gz = cx + 18, cz + 14
    for sx in (-2.0, 2.0):
        mb.fbox(gx + sx - 0.08, 0, gz - 0.08, gx + sx + 0.08, 2.6, gz + 0.08, props.RED, "plain")
    mb.fbox(gx - 2.1, 2.5, gz - 0.06, gx + 2.1, 2.65, gz + 0.06, props.RED, "plain")
    cb.solid("playground", gx, gz, 2.2, 0.3, 0.1, False)
    for k, col in enumerate((props.YELLOW, props.BLUE, props.RED)):
        mb.fbox(gx + 5 + k * 1.6, 0, gz - 0.7, gx + 6.4 + k * 1.6, 0.8 + k * 0.4, gz + 0.7, col, "plain")
    cb.solid("playground", gx + 6.6, gz, 2.5, 0.8, 0.1, False)


# ==================================================================================== block types
def downtown_block(cb, i, j, rng):
    x0, z0, x1, z1 = block_rect(i, j)
    mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
    g = 3.0
    mb = cb.mb(mx, mz)
    mb.fquad((x0, CURB_H, z0), (x1, CURB_H, z0), (x1, CURB_H, z1), (x0, CURB_H, z1), (0, 1, 0), (1, 1, 1, 1), "sidewalk",
             uv=[(x0 / 4, z0 / 4), (x1 / 4, z0 / 4), (x1 / 4, z1 / 4), (x0 / 4, z1 / 4)], shade=False)
    cb.surface.fill_rect(SurfaceMap.SIDEWALK, x0, z0, x1, z1)
    lots = [((x0, z0, mx - g / 2, mz - g / 2), 0, 0), ((mx + g / 2, z0, x1, mz - g / 2), 1, 0),
            ((x0, mz + g / 2, mx - g / 2, z1), 0, 1), ((mx + g / 2, mz + g / 2, x1, z1), 1, 1)]
    for lot, a, b in lots:
        if _near_center(lot):
            plaza(cb, lot, rng)
            continue
        cx, cz = (lot[0] + lot[2]) / 2, (lot[1] + lot[3]) / 2
        d = math.hypot(cx, cz)
        cand = [((-1, 0) if a == 0 else (1, 0), i if a == 0 else i + 1), ((0, -1) if b == 0 else (0, 1), j if b == 0 else j + 1)]
        cand.sort(key=lambda c: (c[1] % 2, rng.random()))
        f = cand[0][0]
        if rng.random() < 0.6:
            floors = int(26 + 12 * max(0.0, 1.0 - (d - 60) / 130.0)) + rng.randint(-4, 5)
            tower(cb, lot, f, rng, max(14, floors))
        else:
            office(cb, lot, f, rng, rng.randint(8, 14))


def commercial_block(cb, i, j, rng):
    rect = block_rect(i, j)
    depth = 24.0
    for lot, f in frontage_lots(rect, depth, 20.0, 30.0, rng):
        if _near_center(lot):
            plaza(cb, lot, rng)
            continue
        r = rng.random()
        if r < 0.32:
            shop(cb, lot, f, rng, rng.choice((1, 1, 2)))
        elif r < 0.62:
            apartment(cb, lot, f, rng, rng.randint(4, 7), mixed=True)
        elif r < 0.9:
            office(cb, lot, f, rng, rng.randint(6, 11))
        else:
            apartment(cb, lot, f, rng, rng.randint(5, 7))
    x0, z0, x1, z1 = rect
    court = (x0 + depth, z0 + depth, x1 - depth, z1 - depth)
    mb = cb.mb((court[0] + court[2]) / 2, (court[1] + court[3]) / 2)
    mb.fquad((court[0], CURB_H, court[1]), (court[2], CURB_H, court[1]), (court[2], CURB_H, court[3]), (court[0], CURB_H, court[3]),
             (0, 1, 0), (1, 1, 1, 1), "sidewalk", uv=[(court[0] / 4, court[1] / 4), (court[2] / 4, court[1] / 4), (court[2] / 4, court[3] / 4), (court[0] / 4, court[3] / 4)], shade=False)
    cb.surface.fill_rect(SurfaceMap.SIDEWALK, *court)
    garden_ground(cb, court, rng, 3)


def residential_block(cb, i, j, rng):
    rect = block_rect(i, j)
    depth = 28.0
    for lot, f in frontage_lots(rect, depth, 20.0, 27.0, rng):
        w = (lot[2] - lot[0]) if f[1] else (lot[3] - lot[1])
        if _near_center(lot):
            plaza(cb, lot, rng)
        elif w >= 24.0 and rng.random() < 0.22:
            apartment(cb, lot, f, rng, rng.randint(4, 6))
        else:
            house(cb, lot, f, rng)
    x0, z0, x1, z1 = rect
    garden_ground(cb, (x0 + depth, z0 + depth, x1 - depth, z1 - depth), rng, 4)


def lot_block(cb, i, j, rng):
    x0, z0, x1, z1 = block_rect(i, j)
    parking_area(cb, (x0 + 2, z0 + 2, x1 - 2, z1 - 2), rng, fill=0.45)
    for k in range(7):
        props.tree(cb, rng.choice((x0 + 1.0, x1 - 1.0)), rng.uniform(z0 + 4, z1 - 4), rng, scale=0.8)


def park_block(cb, i, j, rng):
    park(cb, block_rect(i, j), rng)


BLOCK_BUILDERS = {"downtown": downtown_block, "commercial": commercial_block, "residential": residential_block,
                  "lot": lot_block, "park": park_block}
