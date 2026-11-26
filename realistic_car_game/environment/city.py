"""City generator + (Ursina) loader.

CityBuilder is pure Python: it produces per-chunk MeshBuilders, collision obstacles, the surface map, the
lane graph and signal sites.  CityLoader time-slices generation and entity creation across frames so the
window stays responsive and can show a progress message.
"""
import math
import random
import time
from collections import defaultdict

from environment import buildings, roads, terrain
from environment.layout import CHUNK, N, SurfaceMap, WORLD_HALF, block_rect, pos
from utilities.collision import OBB2D, CollisionWorld, Obstacle
from utilities.mesh_builder import MeshBuilder

PARKS = {(2, -3), (-4, 1), (-1, 2), (3, 0)}
LOTS = {(-3, -1), (1, 2)}
TEXTURED_PARTS = ("asphalt", "sidewalk", "ground") + tuple("f_" + s for s in ("glass", "office", "brick", "shop", "siding", "concrete"))


def block_kind(i, j):
    if (i, j) in PARKS:
        return "park"
    if (i, j) in LOTS:
        return "lot"
    d = math.hypot(pos(i) + 55.0, pos(j) + 55.0)
    return "downtown" if d < 190 else "commercial" if d < 330 else "residential"


class CityBuilder:
    spawn = (5.75, -175.0, 0.0)         # x, z, heading_deg: outer northbound lane of the central avenue

    def __init__(self, world=None, seed=7):
        self.world = world if world is not None else CollisionWorld()
        self.seed = seed
        self.chunks = {}
        self.surface = SurfaceMap()
        self.lanes, self.signal_sites, self.stop_lines, self.segments = [], [], [], []
        self.nodes, self.building_rects = {}, []
        self.parked_budget, self.parked_density = 150, 0.10
        self.stats = defaultdict(int)
        self.ground_mb = MeshBuilder(bake_light=False)
        self.hills_mb = MeshBuilder(bake_light=True, gain=1.25)
        self.done = False

    # --------------------------------------------------------------- services for generators
    def mb(self, x, z):
        key = (math.floor(x / CHUNK), math.floor(z / CHUNK))
        b = self.chunks.get(key)
        if b is None:
            b = self.chunks[key] = MeshBuilder(bake_light=True, gain=1.25)
        return b

    def solid(self, kind, cx, cz, hx, hz, restitution=0.2, blocks_camera=True, psi_deg=0.0):
        self.world.add(Obstacle(OBB2D(cx, cz, hx, hz, math.radians(psi_deg)), kind, restitution,
                                blocks_camera=blocks_camera))
        self.stats["solid_" + kind] += 1

    # --------------------------------------------------------------------------- generation
    def steps(self):
        """Generator yielding (progress 0..1, message). Run to exhaustion to finish the city."""
        for frac, msg in roads.road_steps(self):
            yield 0.35 * frac, msg
        blocks = [(i, j) for i in range(-N, N) for j in range(-N, N)]
        for n, (i, j) in enumerate(blocks):
            kind = block_kind(i, j)
            buildings.BLOCK_BUILDERS[kind](self, i, j, random.Random(self.seed * 31337 + i * 1009 + j * 17))
            self.stats["block_" + kind] += 1
            yield 0.35 + 0.55 * (n + 1) / len(blocks), "Constructing buildings"
        rng = random.Random(self.seed)
        terrain.build_ground(self.ground_mb)
        terrain.build_belt(self, rng)
        terrain.build_perimeter(self)
        terrain.build_hills(self.hills_mb, rng)
        yield 0.95, "Planting trees and hills"
        self.done = True
        yield 1.0, "Done"

    def generate(self):
        for _ in self.steps():
            pass
        return self

    def tri_count(self):
        return sum(m.tri_count for b in self.chunks.values() for m in b.parts.values())


# ======================================================================================== loader
class CityLoader:
    """Builds the city over several frames and creates the Ursina entities."""
    def __init__(self, world, assets, seed=7):
        self.cb = CityBuilder(world, seed)
        self.assets = assets
        self.progress, self.message, self.done = 0.0, "Starting", False
        self._gen = self._run()
        self.chunk_entities = {}
        self._cull_t = 0.0

    @property
    def spawn(self):
        return self.cb.spawn

    @property
    def surface(self):
        return self.cb.surface

    def _run(self):
        for frac, msg in self.cb.steps():
            self.progress, self.message = 0.8 * frac, msg
            yield
        from ursina import Entity
        from core.asset_manager import to_ursina_mesh
        tex = self.assets.city_textures()
        e = Entity(model=to_ursina_mesh(self.cb.ground_mb.parts["ground"]), texture=tex["ground"])
        Entity(model=to_ursina_mesh(self.cb.hills_mb.parts["plain"]))
        keys = list(self.cb.chunks)
        for n, key in enumerate(keys):
            b = self.cb.chunks[key]
            ents, lo, hi = [], [1e9, 1e9], [-1e9, -1e9]
            for part, data in b.parts.items():
                if not data.vertices:
                    continue
                ents.append(Entity(model=to_ursina_mesh(data), texture=tex.get(part)))
                (x0, _, z0), (x1, _, z1) = data.bounds()
                lo[0], lo[1], hi[0], hi[1] = min(lo[0], x0), min(lo[1], z0), max(hi[0], x1), max(hi[1], z1)
                self.chunk_entities[key] = (ents, (lo[0], lo[1], hi[0], hi[1]))
                self.progress, self.message = 0.8 + 0.2 * (n + 1) / len(keys), "Building meshes"
                yield                                   # one mesh per frame keeps the window responsive
        self.done = True

    def step(self, budget=0.03):
        t = time.perf_counter()
        while not self.done and time.perf_counter() - t < budget:
            try:
                next(self._gen)
            except StopIteration:
                self.done = True
        return self.done

    def update(self, dt, cam_x, cam_z, draw_distance):
        """Distance-cull chunk entities (cheap: runs a few times per second)."""
        self._cull_t -= dt
        if self._cull_t > 0:
            return
        self._cull_t = 0.25
        for ents, (x0, z0, x1, z1) in self.chunk_entities.values():
            dx = max(x0 - cam_x, 0.0, cam_x - x1)
            dz = max(z0 - cam_z, 0.0, cam_z - z1)
            vis = math.hypot(dx, dz) < draw_distance
            for e in ents:
                if e.enabled != vis:
                    e.enabled = vis
