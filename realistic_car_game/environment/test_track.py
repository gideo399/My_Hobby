"""Phase 1 test environment: a 1.15 km four-lane road, a skid pad, cones, barriers, posts and walls.

Everything static is merged into a handful of meshes (ground, asphalt, paint, props) -> 4 draw calls.
Every solid prop also registers an OBB in the CollisionWorld.  Real city generation arrives in Phase 2.
"""
import math

from ursina import Entity

from core.asset_manager import to_ursina_mesh
from utilities.collision import OBB2D, Obstacle
from utilities.mesh_builder import MeshBuilder

LANE_W = 3.6
ROAD_HALF = 2 * LANE_W            # 7.2 m
ROAD_Z0, ROAD_Z1 = -250.0, 900.0
GROUND_X, GROUND_Z0, GROUND_Z1 = 350.0, -350.0, 1000.0

Y_GROUND, Y_ROAD, Y_PAINT = -0.06, 0.0, 0.035
CONCRETE = (0.64, 0.64, 0.62, 1.0)
ORANGE = (1.0, 0.42, 0.05, 1.0)
WHITE = (0.93, 0.93, 0.93, 1.0)
RED = (0.78, 0.10, 0.10, 1.0)
DARK = (0.12, 0.12, 0.13, 1.0)
WALL = (0.46, 0.48, 0.52, 1.0)
YELLOW = (0.95, 0.75, 0.10, 1.0)
PAINT_WHITE = (0.92, 0.92, 0.90, 1.0)
UP = (0, 1, 0)


class TestTrack:
    spawn = (5.4, 0.0, 0.0)       # x, z, heading_deg  (outer right-hand lane, facing +Z)

    def __init__(self, world, assets):
        self.world = world
        self.assets = assets
        self._build()

    # ----------------------------------------------------------- helpers
    def _solid(self, cx, cz, hx, hz, psi_deg=0.0, kind="solid", restitution=0.2):
        self.world.add(Obstacle(OBB2D(cx, cz, hx, hz, math.radians(psi_deg)), kind, restitution))

    @staticmethod
    def _flat_quad(mb, x0, z0, x1, z1, y, color, uv=None, shade=False):
        mb.quad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), color, outward=UP, uv=uv, shade=shade)

    # -------------------------------------------------------------- build
    def _build(self):
        a = self.assets
        grass = a.noise_texture("grass", (70, 104, 52), 11, seed=11)
        asphalt = a.noise_texture("asphalt", (62, 62, 66), 7, seed=5, speckle=0.012)
        white = (1, 1, 1, 1)
        uv = lambda p: (p[0] / 6.0, p[2] / 6.0)

        g = MeshBuilder(bake_light=False)
        self._flat_quad(g, -GROUND_X, GROUND_Z0, GROUND_X, GROUND_Z1, Y_GROUND, white,
                        uv=lambda p: (p[0] / 8.0, p[2] / 8.0))
        Entity(model=to_ursina_mesh(g.parts["main"]), texture=grass)

        r = MeshBuilder(bake_light=False)
        self._flat_quad(r, -ROAD_HALF, ROAD_Z0, ROAD_HALF, ROAD_Z1, Y_ROAD, white, uv=uv)
        pad_c, pad_r = (-85.0, 160.0), 45.0
        n = 64
        ring = [(pad_c[0] + pad_r * math.cos(2 * math.pi * i / n), Y_ROAD, pad_c[1] + pad_r * math.sin(2 * math.pi * i / n))
                for i in range(n)]
        r.polygon(ring, white, UP, uv=uv, shade=False)
        self._flat_quad(r, pad_c[0] + pad_r - 2.0, pad_c[1] - 7.0, -ROAD_HALF, pad_c[1] + 7.0, Y_ROAD, white, uv=uv)
        Entity(model=to_ursina_mesh(r.parts["main"]), texture=asphalt)

        self._build_paint(pad_c)
        self._build_props()

    def _build_paint(self, pad_c):
        p = MeshBuilder(bake_light=False)
        y = Y_PAINT
        q = lambda x0, z0, x1, z1, col: self._flat_quad(p, x0, z0, x1, z1, y, col)
        q(-ROAD_HALF + 0.25, ROAD_Z0, -ROAD_HALF + 0.45, ROAD_Z1, PAINT_WHITE)        # edge lines
        q(ROAD_HALF - 0.45, ROAD_Z0, ROAD_HALF - 0.25, ROAD_Z1, PAINT_WHITE)
        q(-0.22, ROAD_Z0, -0.10, ROAD_Z1, YELLOW)                                       # double yellow
        q(0.10, ROAD_Z0, 0.22, ROAD_Z1, YELLOW)
        z = ROAD_Z0
        while z < ROAD_Z1:                                                              # dashed lane lines
            for lx in (-LANE_W, LANE_W):
                q(lx - 0.08, z, lx + 0.08, z + 3.0, PAINT_WHITE)
            z += 9.0
        # skid-pad ring + centre mark
        n, rad = 72, 30.0
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            pts = [(pad_c[0] + (rad - 0.12) * c0, y, pad_c[1] + (rad - 0.12) * s0),
                   (pad_c[0] + (rad + 0.12) * c0, y, pad_c[1] + (rad + 0.12) * s0),
                   (pad_c[0] + (rad + 0.12) * c1, y, pad_c[1] + (rad + 0.12) * s1),
                   (pad_c[0] + (rad - 0.12) * c1, y, pad_c[1] + (rad - 0.12) * s1)]
            p.quad(*pts, PAINT_WHITE, outward=UP, shade=False)
        q(pad_c[0] - 0.5, pad_c[1] - 0.5, pad_c[0] + 0.5, pad_c[1] + 0.5, YELLOW)
        Entity(model=to_ursina_mesh(p.parts["main"]))

    def _cone(self, mb, x, z):
        mb.box((x, 0.02, z), (0.46, 0.04, 0.46), DARK)
        mb.frustum((x, 0.39, z), 0.17, 0.04, 0.70, ORANGE, "y", 10, caps=(False, True))
        mb.frustum((x, 0.37, z), 0.126, 0.089, 0.20, WHITE, "y", 10, caps=(False, False))
        self._solid(x, z, 0.23, 0.23, kind="cone", restitution=0.1)

    def _barrier(self, mb, x, z, yaw_deg=0.0, length=3.0):
        mb.box((x, 0.22, z), (0.80, 0.44, length), CONCRETE, yaw_deg)
        mb.box((x, 0.64, z), (0.42, 0.40, length), CONCRETE, yaw_deg)
        mb.box((x, 0.86, z), (0.44, 0.04, length), YELLOW, yaw_deg)
        self._solid(x, z, 0.40, length / 2.0, yaw_deg, kind="barrier", restitution=0.15)

    def _wall(self, mb, cx, cz, width, depth, height, color=WALL, stripes=False, along_x=True):
        mb.box((cx, height / 2.0, cz), (width, height, depth) if along_x else (depth, height, width), color)
        self._solid(cx, cz, (width if along_x else depth) / 2.0, (depth if along_x else width) / 2.0, kind="wall")
        if stripes:                                           # hazard stripes on the face toward the road
            step = 2.0
            k = 0
            x = cx - width / 2.0 + step / 2.0
            while x < cx + width / 2.0:
                if k % 2 == 0:
                    mb.box((x, height * 0.5, cz - depth / 2.0 - 0.01), (step, height * 0.9, 0.03), RED)
                x += step
                k += 1

    def _build_props(self):
        mb = MeshBuilder(bake_light=True)
        # slalom
        for i, z in enumerate(range(250, 426, 25)):
            self._cone(mb, 3.0 if i % 2 == 0 else -3.0, float(z))
        # lane closure taper
        for i in range(8):
            self._cone(mb, 7.0 - i * 0.5, 520.0 + i * 6.0)
        # barrier run along the left edge
        for k in range(26):
            self._barrier(mb, -8.6, 560.0 + k * 3.1)
        # staggered chicane
        self._barrier(mb, -3.0, 700.0, 90.0, 8.0)
        self._barrier(mb, 3.6, 740.0, 90.0, 8.0)
        self._barrier(mb, -3.0, 780.0, 90.0, 8.0)
        # delineator posts + distance markers
        for z in range(-240, 890, 30):
            for sx in (-1, 1):
                mb.box((sx * (ROAD_HALF + 0.9), 0.45, float(z)), (0.12, 0.9, 0.12), WHITE)
                mb.box((sx * (ROAD_HALF + 0.9), 0.80, float(z)), (0.13, 0.12, 0.13), ORANGE)
                self._solid(sx * (ROAD_HALF + 0.9), float(z), 0.07, 0.07, kind="post", restitution=0.05)
        for z in range(100, 900, 100):
            mb.box((ROAD_HALF + 2.4, 1.3, float(z)), (0.25, 2.6, 0.25), WHITE)
            mb.box((ROAD_HALF + 2.4, 2.45, float(z)), (0.9, 0.5, 0.12), RED)
            self._solid(ROAD_HALF + 2.4, float(z), 0.13, 0.13, kind="post", restitution=0.05)
        # end wall with hazard stripes and the perimeter
        self._wall(mb, 0.0, ROAD_Z1 + 1.0, 46.0, 2.0, 3.0, color=CONCRETE, stripes=True)
        self._wall(mb, 0.0, GROUND_Z1 - 1.0, 2 * GROUND_X, 2.0, 2.0)
        self._wall(mb, 0.0, GROUND_Z0 + 1.0, 2 * GROUND_X, 2.0, 2.0)
        self._wall(mb, -GROUND_X + 1.0, (GROUND_Z0 + GROUND_Z1) / 2.0, GROUND_Z1 - GROUND_Z0, 2.0, 2.0, along_x=False)
        self._wall(mb, GROUND_X - 1.0, (GROUND_Z0 + GROUND_Z1) / 2.0, GROUND_Z1 - GROUND_Z0, 2.0, 2.0, along_x=False)
        Entity(model=to_ursina_mesh(mb.parts["main"]))
