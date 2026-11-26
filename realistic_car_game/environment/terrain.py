"""World boundary: ground plane, outer tree belt, perimeter wall and distant backdrop hills.

Honest scope note: vehicle physics is planar in Phase 2, so the *drivable* area is flat. The hills are a
non-drivable backdrop beyond the perimeter wall (they give horizon, depth and scale). Drivable slopes need
a height-field physics layer and are planned together with Bullet integration.
"""
import math

from environment import props
from environment.layout import CITY_HALF, WALL_HALF, WORLD_HALF
from utilities.mesh_builder import MeshBuilder

WALL_COL = (0.55, 0.56, 0.58, 1.0)


def _smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def build_ground(mb):
    h = WORLD_HALF
    mb.fquad((-h, -0.06, -h), (h, -0.06, -h), (h, -0.06, h), (-h, -0.06, h), (0, 1, 0), (1, 1, 1, 1), "ground",
             uv=[(-h / 8, -h / 8), (h / 8, -h / 8), (h / 8, h / 8), (-h / 8, h / 8)], shade=False)


def build_perimeter(cb):
    w, thick, hgt, step = WALL_HALF, 1.4, 2.4, 110.0
    for sgn in (-1, 1):
        a = -w
        while a < w - 0.1:
            b = min(a + step, w)
            for (x0, z0, x1, z1) in ((a, sgn * w - thick / 2, b, sgn * w + thick / 2), (sgn * w - thick / 2, a, sgn * w + thick / 2, b)):
                cb.mb((x0 + x1) / 2, (z0 + z1) / 2).fbox(x0, 0, z0, x1, hgt, z1, WALL_COL, "plain")
                cb.solid("wall", (x0 + x1) / 2, (z0 + z1) / 2, (x1 - x0) / 2, (z1 - z0) / 2, 0.15, True)
            a = b


def build_belt(cb, rng, count=420):
    placed, tries = 0, 0
    while placed < count and tries < count * 6:
        tries += 1
        x, z = rng.uniform(-WALL_HALF + 6, WALL_HALF - 6), rng.uniform(-WALL_HALF + 6, WALL_HALF - 6)
        if max(abs(x), abs(z)) < CITY_HALF + 14:
            continue
        props.tree(cb, x, z, rng, kind=rng.choice(("conifer", "conifer", "round", "tall")), scale=rng.uniform(1.0, 1.5))
        placed += 1
    for sx, sz, dx, dz in ((CITY_HALF + 25, 30, -1, 0), (-CITY_HALF - 25, -30, 1, 0), (30, CITY_HALF + 25, 0, -1), (-30, -CITY_HALF - 25, 0, 1)):
        props.billboard(cb, sx, sz, dx, dz, rng)


def build_hills(mb, rng):
    n_theta = 120
    radial = (0.0, 0.07, 0.18, 0.36, 0.62, 1.0)
    phases = [rng.uniform(0, 6.28) for _ in range(3)]

    def amp(theta):
        return 38 + 22 * math.sin(3 * theta + phases[0]) + 14 * math.sin(7 * theta + phases[1]) + 8 * math.sin(13 * theta + phases[2])

    def point(k, s):
        th = 2 * math.pi * k / n_theta
        c, sn = math.cos(th), math.sin(th)
        r0 = WORLD_HALF / max(abs(c), abs(sn))
        r = r0 + 900.0 * s
        y = -0.06 + amp(th) * _smooth(0.0, 0.45, s) * (1.0 - 0.25 * _smooth(0.7, 1.0, s)) + 2.0 * math.sin(th * 41 + s * 9)
        return (r * c, y, r * sn)

    def color(y):
        t = max(0.0, min(1.0, y / 60.0))
        return (0.30 + 0.18 * t, 0.46 - 0.04 * t, 0.22 + 0.10 * t, 1.0)

    for k in range(n_theta):
        for a in range(len(radial) - 1):
            p = [point(k, radial[a]), point(k + 1, radial[a]), point(k + 1, radial[a + 1]), point(k, radial[a + 1])]
            ym = sum(q[1] for q in p) / 4
            mb.quad(*p, color(ym), "plain", outward=(0, 1, 0))
