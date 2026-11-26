"""2D (top-down) oriented-box collision, spatial grid and ray casting.

Conventions (identical to Ursina): +X right, +Y up, +Z forward, 1 unit = 1 metre.
A heading `psi` (radians) means forward = (sin psi, cos psi) in the (x, z) plane and
right = (cos psi, -sin psi); increasing psi turns clockwise seen from above, which is
exactly Ursina's `rotation_y` (in degrees).
"""
import math
from dataclasses import dataclass


@dataclass
class OBB2D:
    cx: float
    cz: float
    hx: float      # half extent along the box's right axis
    hz: float      # half extent along the box's forward axis
    psi: float = 0.0

    def axes(self):
        s, c = math.sin(self.psi), math.cos(self.psi)
        return (c, -s), (s, c)         # right, forward

    def corners(self):
        (rx, rz), (fx, fz) = self.axes()
        out = []
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            out.append((self.cx + sx * self.hx * rx + sz * self.hz * fx,
                        self.cz + sx * self.hx * rz + sz * self.hz * fz))
        return out

    def aabb(self):
        pts = self.corners()
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        return min(xs), min(zs), max(xs), max(zs)

    def to_local(self, x, z):
        (rx, rz), (fx, fz) = self.axes()
        dx, dz = x - self.cx, z - self.cz
        return dx * rx + dz * rz, dx * fx + dz * fz

    def contains(self, x, z, margin=0.0):
        lx, lz = self.to_local(x, z)
        return abs(lx) <= self.hx + margin and abs(lz) <= self.hz + margin


@dataclass
class Contact:
    nx: float      # normal pointing from B towards A (the direction A must move to separate)
    nz: float
    depth: float
    px: float      # contact point (world)
    pz: float


def obb_overlap(a: OBB2D, b: OBB2D):
    """Separating-axis test. Returns Contact (normal pushes A out of B) or None."""
    (arx, arz), (afx, afz) = a.axes()
    (brx, brz), (bfx, bfz) = b.axes()
    dx, dz = a.cx - b.cx, a.cz - b.cz
    best = None
    for ux, uz in ((arx, arz), (afx, afz), (brx, brz), (bfx, bfz)):
        ra = a.hx * abs(ux * arx + uz * arz) + a.hz * abs(ux * afx + uz * afz)
        rb = b.hx * abs(ux * brx + uz * brz) + b.hz * abs(ux * bfx + uz * bfz)
        d = dx * ux + dz * uz
        overlap = ra + rb - abs(d)
        if overlap <= 0.0:
            return None
        if best is None or overlap < best[0]:
            sgn = 1.0 if d >= 0.0 else -1.0
            best = (overlap, ux * sgn, uz * sgn)
    depth, nx, nz = best

    # Contact point: deepest corner of A inside B, else deepest corner of B inside A.
    a_c = min(a.corners(), key=lambda p: p[0] * nx + p[1] * nz)
    b_c = max(b.corners(), key=lambda p: p[0] * nx + p[1] * nz)
    if b.contains(*a_c, margin=0.02):
        px, pz = a_c
    elif a.contains(*b_c, margin=0.02):
        px, pz = b_c
    else:
        px, pz = (a_c[0] + b_c[0]) * 0.5, (a_c[1] + b_c[1]) * 0.5
    return Contact(nx, nz, depth, px, pz)


def segment_vs_obb(x0, z0, x1, z1, box: OBB2D):
    """Slab test in box space. Returns entry fraction t in [0,1] or None.
    Segments that start inside the box are ignored (return None)."""
    lx0, lz0 = box.to_local(x0, z0)
    lx1, lz1 = box.to_local(x1, z1)
    if abs(lx0) <= box.hx and abs(lz0) <= box.hz:
        return None
    t0, t1 = 0.0, 1.0
    for p0, p1, h in ((lx0, lx1, box.hx), (lz0, lz1, box.hz)):
        d = p1 - p0
        if abs(d) < 1e-9:
            if abs(p0) > h:
                return None
            continue
        ta, tb = (-h - p0) / d, (h - p0) / d
        if ta > tb:
            ta, tb = tb, ta
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 > t1:
            return None
    return t0


class Obstacle:
    """A static solid. `entity` is optional (visual may be merged into a shared mesh)."""
    def __init__(self, obb: OBB2D, kind="solid", restitution=0.2, friction=0.35, entity=None,
                 blocks_camera=True):
        self.blocks_camera = blocks_camera      # thin poles/trees should not make the camera jitter
        self.obb = obb
        self.kind = kind
        self.restitution = restitution
        self.friction = friction
        self.entity = entity


class CollisionWorld:
    """Uniform grid broad-phase over static obstacles."""
    def __init__(self, cell=16.0):
        self.cell = cell
        self._grid = {}
        self.obstacles = []

    def _cells(self, aabb):
        x0, z0, x1, z1 = aabb
        c = self.cell
        for ix in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for iz in range(int(math.floor(z0 / c)), int(math.floor(z1 / c)) + 1):
                yield ix, iz

    def add(self, obstacle: Obstacle):
        self.obstacles.append(obstacle)
        for key in self._cells(obstacle.obb.aabb()):
            self._grid.setdefault(key, []).append(obstacle)
        return obstacle

    def query(self, obb: OBB2D):
        seen, out = set(), []
        for key in self._cells(obb.aabb()):
            for ob in self._grid.get(key, ()):
                if id(ob) not in seen:
                    seen.add(id(ob))
                    out.append(ob)
        return out

    def raycast(self, x0, z0, x1, z1, blockers_only=False):
        """Nearest obstacle hit by the segment: (t, obstacle) or None."""
        aabb = (min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1))
        seen, best = set(), None
        for key in self._cells(aabb):
            for ob in self._grid.get(key, ()):
                if id(ob) in seen:
                    continue
                seen.add(id(ob))
                if blockers_only and not ob.blocks_camera:
                    continue
                t = segment_vs_obb(x0, z0, x1, z1, ob.obb)
                if t is not None and (best is None or t < best[0]):
                    best = (t, ob)
        return best
