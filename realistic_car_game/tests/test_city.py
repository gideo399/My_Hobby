"""Pure-Python tests of the generated city (no Ursina needed). Run: python -m tests.test_city"""
import math
import time

from environment.city import CityBuilder
from environment.layout import N, SurfaceMap, block_rect
from utilities.collision import OBB2D, obb_overlap

_CB = None


def city():
    global _CB
    if _CB is None:
        _CB = CityBuilder(seed=7).generate()
    return _CB


def test_generation_is_deterministic_and_bounded():
    t = time.time()
    a = CityBuilder(seed=7).generate()
    assert time.time() - t < 20
    b = city()
    assert a.tri_count() == b.tri_count() and len(a.world.obstacles) == len(b.world.obstacles)
    assert 100_000 < b.tri_count() < 700_000, b.tri_count()
    for k, builder in b.chunks.items():
        for part, m in builder.parts.items():
            m.validate()


def test_variety_of_content():
    s = city().stats
    for key in ("towers", "offices", "apartments", "shops", "houses", "block_park", "block_lot",
                "solid_tree", "solid_lamp", "solid_bench", "solid_bus_stop", "solid_parked_car", "solid_island"):
        assert s[key] > 0, key
    assert s["houses"] > 100 and s["solid_building"] > 400


def test_buildings_stay_inside_blocks_and_do_not_overlap():
    cb = city()
    blocks = [block_rect(i, j) for i in range(-N, N) for j in range(-N, N)]
    bs = [o for o in cb.world.obstacles if o.kind == "building"]
    boxes = []
    for o in bs:
        b = o.obb
        r = (b.cx - b.hx, b.cz - b.hz, b.cx + b.hx, b.cz + b.hz)
        assert any(r[0] >= x0 - 0.01 and r[1] >= z0 - 0.01 and r[2] <= x1 + 0.01 and r[3] <= z1 + 0.01
                   for x0, z0, x1, z1 in blocks), r
        boxes.append(r)
    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            A, B = boxes[a], boxes[b]
            ox = min(A[2], B[2]) - max(A[0], B[0])
            oz = min(A[3], B[3]) - max(A[1], B[1])
            assert not (ox > 0.05 and oz > 0.05), (A, B)


def test_spawn_is_clear_and_on_asphalt():
    cb = city()
    x, z, h = cb.spawn
    box = OBB2D(x, z, 1.0, 2.3, math.radians(h))
    assert not [o for o in cb.world.query(box) if obb_overlap(box, o.obb)]
    assert cb.surface.kind_at(x, z) == SurfaceMap.ASPHALT


def test_every_lane_is_drivable():
    """A car-sized box swept along every lane centre-line must not touch any obstacle."""
    cb = city()
    bad = []
    for lane in cb.lanes:
        (x0, z0), (x1, z1) = lane.start, lane.end
        length = math.hypot(x1 - x0, z1 - z0)
        psi = math.atan2(x1 - x0, z1 - z0)
        n = max(2, int(length / 1.5))
        for k in range(n + 1):
            t = k / n
            x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            box = OBB2D(x, z, 0.95, 2.3, psi)
            hits = [o for o in cb.world.query(box) if obb_overlap(box, o.obb)]
            if hits:
                bad.append((lane.axis, lane.line, lane.seg, lane.direction, lane.index, round(x, 1), round(z, 1), hits[0].kind))
                break
            assert cb.surface.kind_at(x, z) == SurfaceMap.ASPHALT, (x, z)
    assert not bad, bad[:8]


def test_lane_graph_and_nodes():
    cb = city()
    assert len(cb.nodes) == (2 * N + 1) ** 2
    assert cb.nodes[(0, 0)]["roundabout"] and not cb.nodes[(1, 1)]["roundabout"]
    nodes = set(cb.nodes)
    for lane in cb.lanes:
        assert lane.from_node in nodes and lane.to_node in nodes and lane.from_node != lane.to_node
    per = {}
    for lane in cb.lanes:
        per.setdefault((lane.axis, lane.line, lane.seg, lane.direction), []).append(lane)
    assert all(len(v) in (1, 2) for v in per.values())
    assert len(cb.signal_sites) > 40 and len(cb.stop_lines) > 100


def test_right_hand_traffic():
    cb = city()
    for lane in cb.lanes:
        if lane.axis == "z":                 # northbound (+z) must be on the east (+x) half
            assert (lane.c > 0) == (lane.direction == 1)
        else:                                # eastbound (+x) drives on the south (-z) half
            assert (lane.c < 0) == (lane.direction == 1)


def test_surface_map_properties():
    cb = city()
    s = cb.surface
    assert s.kind_at(500, 500) == SurfaceMap.GRASS           # outside the city
    assert s.kind_at(0, 20) == SurfaceMap.ASPHALT           # roundabout carriageway
    assert s.kind_at(0, 0) == SurfaceMap.SIDEWALK           # raised island
    grip_g, roll_g, h_g = s.query(500, 500)
    grip_a, roll_a, h_a = s.query(5.75, -150)
    assert grip_g < grip_a and roll_g > roll_a and h_g < h_a
    img = s.minimap_image(128, cb.building_rects)
    assert img.size[0] >= 100


def test_perimeter_wall_contains_the_player():
    cb = city()
    for ang in range(0, 360, 15):
        dx, dz = math.sin(math.radians(ang)), math.cos(math.radians(ang))
        hit = cb.world.raycast(0.0, 0.0, dx * 800, dz * 800)
        assert hit is not None, ang
    # ...and the camera ray ignores thin poles/trees but not buildings
    assert cb.world.raycast(5.75, -175, 5.75, -165, blockers_only=True) is None


def main():
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print("PASS", n)
    print(f"\n{len(tests)} city tests passed")


if __name__ == "__main__":
    main()
