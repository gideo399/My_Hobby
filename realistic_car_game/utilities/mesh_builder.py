"""Engine-independent procedural mesh construction.

Everything is built as flat-shaded triangles with *per-vertex colours* so a whole car body (paint,
glass, trim, lights) is ONE draw call.  Winding is decided automatically: each face is oriented so
its normal points away from a reference ("inside" point or explicit "outward" vector), which removes
the usual inside-out-mesh bugs.  Ursina is left-handed, so for a counter-clockwise (front-facing)
triangle (a, b, c) the outward normal is  -(b-a) x (c-a).

If a model ever renders inside-out on your machine, flip FLIP_WINDING below.

Lighting is *baked* into the vertex colours (fake directional + sky light) in Phase 1; Phase 5 will
replace it with real lights/shadows (build with bake_light=False then).
"""
import math
from dataclasses import dataclass, field

FLIP_WINDING = False
_LIGHT = (0.45, 0.80, -0.40)
_l = math.sqrt(sum(c * c for c in _LIGHT))
LIGHT_DIR = tuple(c / _l for c in _LIGHT)


def v_sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v_mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def v_dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def v_cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def v_len(a): return math.sqrt(v_dot(a, a))


def centroid(points):
    n = float(len(points))
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)


def rot_y(x, z, deg):
    """Rotate (x, z) with Ursina's rotation_y convention."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return x * c + z * s, -x * s + z * c


@dataclass
class MeshData:
    vertices: list = field(default_factory=list)
    triangles: list = field(default_factory=list)   # flat index list
    normals: list = field(default_factory=list)
    uvs: list = field(default_factory=list)
    colors: list = field(default_factory=list)      # (r, g, b, a) floats 0..1

    @property
    def tri_count(self):
        return len(self.triangles) // 3

    def bounds(self):
        xs, ys, zs = zip(*self.vertices)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def validate(self):
        n = len(self.vertices)
        assert len(self.normals) == n and len(self.uvs) == n and len(self.colors) == n
        assert all(0 <= i < n for i in self.triangles) and len(self.triangles) % 3 == 0


class MeshBuilder:
    def __init__(self, bake_light=True, gain=1.0):
        self.parts = {}
        self.bake_light = bake_light
        self.gain = gain                    # brightness multiplier for baked lighting (clamped to 1)

    def part(self, name="main"):
        return self.parts.setdefault(name, MeshData())

    # ------------------------------------------------------------- primitives
    def _shade(self, col, n):
        f = (0.50 + 0.34 * max(0.0, v_dot(n, LIGHT_DIR)) + 0.16 * (0.5 + 0.5 * n[1])) * self.gain
        return (min(1.0, col[0] * f), min(1.0, col[1] * f), min(1.0, col[2] * f), col[3])

    def tri(self, a, b, c, color, part="main", inside=None, outward=None, uv=None, shade=True):
        n = v_mul(v_cross(v_sub(b, a), v_sub(c, a)), -1.0)
        ln = v_len(n)
        if ln < 1e-9:
            return
        n = v_mul(n, 1.0 / ln)
        ref = outward if outward is not None else (v_sub(centroid((a, b, c)), inside) if inside is not None else None)
        uvs = None
        if uv is not None:
            uvs = [uv(p) for p in (a, b, c)] if callable(uv) else list(uv)
        if ref is not None and v_dot(n, ref) < 0.0:
            b, c = c, b
            n = v_mul(n, -1.0)
            if uvs:
                uvs[1], uvs[2] = uvs[2], uvs[1]
        col = color(n) if callable(color) else color
        if shade and self.bake_light:
            col = self._shade(col, n)
        order = (a, b, c) if not FLIP_WINDING else (a, c, b)
        uv_order = (0, 1, 2) if not FLIP_WINDING else (0, 2, 1)
        m = self.part(part)
        base = len(m.vertices)
        for k, p in enumerate(order):
            m.vertices.append(p)
            m.normals.append(n)
            m.colors.append(col)
            m.uvs.append(uvs[uv_order[k]] if uvs else (0.0, 0.0))
            m.triangles.append(base + k)

    def quad(self, a, b, c, d, color, part="main", inside=None, outward=None, uv=None, shade=True):
        if uv is not None and not callable(uv):
            uv = list(uv)
            self.tri(a, b, c, color, part, inside, outward, uv[0:3], shade)
            self.tri(a, c, d, color, part, inside, outward, [uv[0], uv[2], uv[3]], shade)
        else:
            self.tri(a, b, c, color, part, inside, outward, uv, shade)
            self.tri(a, c, d, color, part, inside, outward, uv, shade)

    def polygon(self, points, color, outward, part="main", uv=None, shade=True):
        """Convex polygon as a fan around its centroid."""
        c = centroid(points)
        n = len(points)
        for i in range(n):
            self.tri(c, points[i], points[(i + 1) % n], color, part, outward=outward, uv=uv, shade=shade)

    def box(self, center, size, color, yaw_deg=0.0, part="main", shade=True):
        cx, cy, cz = center
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        pts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    rx, rz = rot_y(sx * hx, sz * hz, yaw_deg)
                    pts.append((cx + rx, cy + sy * hy, cz + rz))
        # index = sx*4 + sy*2 + sz with sx,sy,sz in {0,1} -> pts order below
        def P(sx, sy, sz):
            return pts[sx * 4 + sy * 2 + sz]
        faces = [(P(0, 0, 0), P(0, 1, 0), P(0, 1, 1), P(0, 0, 1)),
                 (P(1, 0, 0), P(1, 1, 0), P(1, 1, 1), P(1, 0, 1)),
                 (P(0, 0, 0), P(1, 0, 0), P(1, 0, 1), P(0, 0, 1)),
                 (P(0, 1, 0), P(1, 1, 0), P(1, 1, 1), P(0, 1, 1)),
                 (P(0, 0, 0), P(1, 0, 0), P(1, 1, 0), P(0, 1, 0)),
                 (P(0, 0, 1), P(1, 0, 1), P(1, 1, 1), P(0, 1, 1))]
        for f in faces:
            self.quad(*f, color, part, inside=center, shade=shade)

    def _ring(self, center, axis, r, n, a0=0.0):
        cx, cy, cz = center
        out = []
        for i in range(n):
            a = a0 + 2 * math.pi * i / n
            ca, sa = math.cos(a), math.sin(a)
            if axis == "y":
                out.append((cx + r * ca, cy, cz + r * sa))
            elif axis == "x":
                out.append((cx, cy + r * ca, cz + r * sa))
            else:
                out.append((cx + r * ca, cy + r * sa, cz))
        return out

    def frustum(self, center, r0, r1, length, color, axis="y", segments=12, part="main",
                caps=(True, True), shade=True):
        """Cone/cylinder along `axis`; r0 at the negative end, r1 at the positive end."""
        off = {"x": (length / 2, 0, 0), "y": (0, length / 2, 0), "z": (0, 0, length / 2)}[axis]
        c0, c1 = v_sub(center, off), v_add(center, off)
        ring0 = self._ring(c0, axis, r0, segments)
        ring1 = self._ring(c1, axis, r1, segments)
        for i in range(segments):
            j = (i + 1) % segments
            self.quad(ring0[i], ring0[j], ring1[j], ring1[i], color, part, inside=center, shade=shade)
        unit = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
        if caps[0] and r0 > 1e-6:
            self.polygon(ring0, color, v_mul(unit, -1.0), part, shade=shade)
        if caps[1] and r1 > 1e-6:
            self.polygon(ring1, color, unit, part, shade=shade)

    def sector(self, center, radius, a0, a1, color, axis_dir, part="main", segments=14, shade=True):
        """Flat circular sector perpendicular to the X axis (angle measured from +Y toward +Z)."""
        cx, cy, cz = center
        pts = [(cx, cy + radius * math.cos(a0 + (a1 - a0) * i / segments),
                cz + radius * math.sin(a0 + (a1 - a0) * i / segments)) for i in range(segments + 1)]
        for i in range(segments):
            self.tri(center, pts[i], pts[i + 1], color, part, outward=(axis_dir, 0, 0), shade=shade)

    def loft(self, rings, color, part="main", skip_edges=(), cap_start=None, cap_end=None, shade=True):
        """Skin between consecutive closed cross-section rings (same point count)."""
        n = len(rings[0])
        for i in range(len(rings) - 1):
            ra, rb = rings[i], rings[i + 1]
            inside = v_mul(v_add(centroid(ra), centroid(rb)), 0.5)
            for j in range(n):
                if j in skip_edges:
                    continue
                k = (j + 1) % n
                self.quad(ra[j], ra[k], rb[k], rb[j], color, part, inside=inside, shade=shade)
        if cap_start is not None:
            self.polygon(rings[0], color, cap_start, part, shade=shade)
        if cap_end is not None:
            self.polygon(rings[-1], color, cap_end, part, shade=shade)

    # ------------------------------------------------------------------
    # Phase 2 additions: fast primitives whose outward normal is known by the caller.
    # ------------------------------------------------------------------
    def fquad(self, a, b, c, d, n, color, part="main", uv=None, shade=True):
        """Quad with a known unit outward normal `n`; vertex order is fixed automatically."""
        cr = v_mul(v_cross(v_sub(b, a), v_sub(c, a)), -1.0)
        pts, uvs = [a, b, c, d], (list(uv) if uv else None)
        if v_dot(cr, n) < 0.0:
            pts = [a, d, c, b]
            if uvs:
                uvs = [uvs[0], uvs[3], uvs[2], uvs[1]]
        col = self._shade(color, n) if (shade and self.bake_light) else color
        m = self.part(part)
        base = len(m.vertices)
        for k in (0, 1, 2, 0, 2, 3):
            m.vertices.append(pts[k])
            m.normals.append(n)
            m.colors.append(col)
            m.uvs.append(uvs[k] if uvs else (0.0, 0.0))
        order = (0, 1, 2, 3, 4, 5) if not FLIP_WINDING else (0, 2, 1, 3, 5, 4)
        # vertices were appended in winding order; flipping only permutes indices within each triangle
        m.triangles.extend(base + i for i in order)

    def ftri(self, a, b, c, n, color, part="main", uv=None, shade=True):
        self.tri(a, b, c, color, part, outward=n, uv=uv, shade=shade)

    def fbox(self, x0, y0, z0, x1, y1, z1, color, part="main", shade=True, bottom=False):
        """Axis-aligned box from min/max corners (bottom face skipped unless asked)."""
        q = self.fquad
        q((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (-1, 0, 0), color, part, shade=shade)
        q((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0), color, part, shade=shade)
        q((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (0, 0, -1), color, part, shade=shade)
        q((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1), color, part, shade=shade)
        q((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (0, 1, 0), color, part, shade=shade)
        if bottom:
            q((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0), color, part, shade=shade)

    def fcyl(self, x, y0, z, r, h, color, part="main", seg=6, r_top=None, cap=False, shade=True):
        """Vertical cylinder / cone frustum with flat radial normals (cheap poles, trunks, signs)."""
        r_top = r if r_top is None else r_top
        ring = [(2 * math.pi * i / seg) for i in range(seg + 1)]
        slope = (r - r_top) / h if h > 0 else 0.0
        for i in range(seg):
            a0, a1 = ring[i], ring[i + 1]
            am = 0.5 * (a0 + a1)
            ln = math.sqrt(1.0 + slope * slope)
            n = (math.cos(am) / ln, slope / ln, math.sin(am) / ln)
            self.fquad((x + r * math.cos(a0), y0, z + r * math.sin(a0)),
                       (x + r * math.cos(a1), y0, z + r * math.sin(a1)),
                       (x + r_top * math.cos(a1), y0 + h, z + r_top * math.sin(a1)),
                       (x + r_top * math.cos(a0), y0 + h, z + r_top * math.sin(a0)), n, color, part, shade=shade)
        if cap and r_top > 1e-6:
            top = [(x + r_top * math.cos(a), y0 + h, z + r_top * math.sin(a)) for a in ring[:-1]]
            self.polygon(top, color, (0, 1, 0), part, shade=shade)

    def bicone(self, x, y, z, r, h_up, h_down, color, part="main", seg=7, rot=0.0):
        """Low-poly blob (two cones base to base) used for tree canopies and bushes."""
        ring = [(x + r * math.cos(rot + 2 * math.pi * i / seg), y, z + r * math.sin(rot + 2 * math.pi * i / seg))
                for i in range(seg)]
        top, bot = (x, y + h_up, z), (x, y - h_down, z)
        for i in range(seg):
            a, b = ring[i], ring[(i + 1) % seg]
            self.tri(top, a, b, color, part, inside=(x, y, z))
            self.tri(bot, b, a, color, part, inside=(x, y, z))

    def facade_walls(self, x0, z0, x1, z1, y0, y1, color, part, bay_w, floor_h, cells=(4, 4),
                     rng=None, sides="nsew"):
        """Four textured walls of an axis-aligned tier. UVs advance one texture tile per
        `cells` bays/floors, so windows always land on whole bays and whole floors."""
        floors = max(1, round((y1 - y0) / floor_h))
        v1 = floors / float(cells[1])
        faces = (("w", (x0, z0, x0, z1), (-1, 0, 0)), ("e", (x1, z1, x1, z0), (1, 0, 0)),
                 ("s", (x1, z0, x0, z0), (0, 0, -1)), ("n", (x0, z1, x1, z1), (0, 0, 1)))
        for key, (ax, az, bx, bz), nrm in faces:
            if key not in sides:
                continue
            length = math.hypot(bx - ax, bz - az)
            if length < 0.5:
                continue
            bays = max(1, round(length / bay_w))
            u0 = (rng.randrange(cells[0]) / float(cells[0])) if rng else 0.0
            u1 = u0 + bays / float(cells[0])
            self.fquad((ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az), nrm, color, part,
                       uv=[(u0, 0.0), (u1, 0.0), (u1, v1), (u0, v1)])

    def add_mesh(self, src, offset, yaw_deg=0.0, part="main", part_map=None):
        """Append every part of a pre-built MeshBuilder/MeshData dict, rotated about Y and translated."""
        parts = src.parts if hasattr(src, "parts") else {"main": src}
        ox, oy, oz = offset
        r = math.radians(yaw_deg)
        c, s = math.cos(r), math.sin(r)
        for name, data in parts.items():
            m = self.part((part_map or {}).get(name, part))
            base = len(m.vertices)
            for (x, y, z) in data.vertices:
                m.vertices.append((x * c + z * s + ox, y + oy, -x * s + z * c + oz))
            for (x, y, z) in data.normals:
                m.normals.append((x * c + z * s, y, -x * s + z * c))
            m.uvs.extend(data.uvs)
            m.colors.extend(data.colors)
            m.triangles.extend(base + i for i in data.triangles)
