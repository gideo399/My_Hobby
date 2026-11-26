"""Software preview of the generated city (no GPU/Ursina): painter's-algorithm perspective render with
approximate texture colours. Usage: python -m tests.preview_render  -> writes /tmp/preview_*.png"""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw

from environment.city import CityBuilder

TEX = {"asphalt": (62, 62, 66), "sidewalk": (186, 184, 178), "ground": (70, 104, 52), "f_glass": (70, 100, 130),
       "f_office": (190, 190, 186), "f_brick": (150, 82, 62), "f_shop": (95, 110, 120), "f_siding": (228, 225, 218),
       "f_concrete": (170, 170, 166)}


def collect(cb, center, radius):
    tris = []
    def add(data, part):
        v = np.asarray(data.vertices, dtype=float)
        c = np.asarray(data.colors, dtype=float)[:, :3]
        n = np.asarray(data.normals, dtype=float)
        idx = np.asarray(data.triangles).reshape(-1, 3)
        base = np.array(TEX.get(part, (255, 255, 255)), dtype=float) / 255.0
        for t in idx:
            p = v[t]
            ctr = p.mean(axis=0)
            if abs(ctr[0] - center[0]) > radius or abs(ctr[2] - center[1]) > radius:
                continue
            col = (c[t].mean(axis=0) * base * 255).clip(0, 255)
            flat = bool(abs(n[t[0]][1]) > 0.99 and p[:, 1].max() < 0.2)
            tris.append((p, n[t[0]], col, flat))
    for b in cb.chunks.values():
        for part, data in b.parts.items():
            if data.vertices:
                add(data, part)
    add(cb.ground_mb.parts["ground"], "ground")
    return tris


def render(tris, eye, target, fov_deg, size, path, sky=(135, 178, 225)):
    W, H = size
    eye, target = np.array(eye, float), np.array(target, float)
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross([0, 1, 0], f); r /= np.linalg.norm(r)      # Ursina is left-handed: +X is right
    u = np.cross(f, r)
    focal = (W / 2) / math.tan(math.radians(fov_deg) / 2)
    img = Image.new("RGB", (W, H), sky)
    d = ImageDraw.Draw(img)
    items = []
    near = 0.3
    for p, n, col, flat in tris:
        if np.dot(n, eye - p.mean(axis=0)) <= 0:           # back-face
            continue
        rel = p - eye
        cam = np.stack([rel @ r, rel @ u, rel @ f], axis=1)   # (x, y, z) in camera space
        poly = []                                              # Sutherland-Hodgman against z = near
        for k in range(3):
            a, b = cam[k], cam[(k + 1) % 3]
            ain, bin_ = a[2] > near, b[2] > near
            if ain:
                poly.append(a)
            if ain != bin_:
                t = (near - a[2]) / (b[2] - a[2])
                poly.append(a + (b - a) * t)
        if len(poly) < 3:
            continue
        pts = [(W / 2 + focal * q[0] / q[2], H / 2 - focal * q[1] / q[2]) for q in poly]
        if max(abs(x) for pt in pts for x in (pt[0] - W / 2, pt[1] - H / 2)) > 2e7:
            continue
        items.append(((0 if flat else 1, -float(np.mean([q[2] for q in poly]))), pts, tuple(int(c) for c in col)))
    items.sort(key=lambda t: t[0])
    for _, pts, col in items:
        d.polygon(pts, fill=col)
    img.save(path)
    return len(items)


def main():
    cb = CityBuilder(seed=7).generate()
    print("tris", cb.tri_count())
    views = {
        "chase": ((5.75, 2.6, -190.0), (5.75, 1.5, -100.0), 85, 220, (5.75, -120.0)),
        "downtown": ((-60.0, 110.0, -330.0), (0.0, 25.0, 0.0), 60, 300, (0.0, 0.0)),
        "houses": ((330.0, 75.0, -250.0), (385.0, 0.0, -50.0), 55, 200, (385.0, -60.0)),
        "top": ((0.0, 420.0, 0.1), (0.0, 0.0, 0.0), 40, 230, (0.0, 0.0)),
    }
    only = sys.argv[1:] or list(views)
    for name in only:
        eye, tgt, fov, rad, ctr = views[name]
        tris = collect(cb, ctr, rad)
        n = render(tris, eye, tgt, fov, (1100, 640) if name != "top" else (900, 900), f"/tmp/preview_{name}.png")
        print(name, n, "triangles drawn")


if __name__ == "__main__":
    main()
