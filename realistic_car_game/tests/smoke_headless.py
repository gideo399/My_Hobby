"""Runs the REAL game code (GameManager, Car, TestTrack, HUD, camera) against a permissive stub of
Ursina so wiring/logic errors surface without a GPU.  It cannot detect real Ursina API mismatches.
Run from the project root:  python -m tests.smoke_headless"""
import sys
import time
import types
from collections import defaultdict


class _Any:
    """Accepts any constructor kwargs / attribute reads / writes."""
    def __init__(self, *a, **k):
        self.__dict__.update(k)
        self.__dict__.setdefault("enabled", True)
        self.__dict__.setdefault("children", [])

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return 0.0


class Entity(_Any):
    default = None


class Color(tuple):
    def __new__(cls, *c):
        return tuple.__new__(cls, c)


def build_stub():
    m = types.ModuleType("ursina")
    for n in ("Entity", "Text", "Mesh", "Texture", "Sky"):
        setattr(m, n, type(n, (Entity,), {}))
    m.Vec3 = lambda *a: a
    m.held_keys = defaultdict(int)
    m.camera = Entity(ui=Entity())
    m.window = Entity(aspect_ratio=16 / 9)
    m.application = Entity(quit=lambda: None)
    m.destroy = lambda e: None
    m.Ursina = Entity
    col = types.ModuleType("ursina.color")
    col.Color = Color
    col.white = Color(1, 1, 1, 1)
    m.color = col
    sys.modules["ursina"] = m
    sys.modules["ursina.color"] = col
    return m


def _frames(gm, n):
    for _ in range(n):
        gm.update()


def smoke_test_track(ur):
    from core.game_manager import GameManager
    gm = GameManager("test_track")
    keys = ur.held_keys
    keys["w"] = 1
    _frames(gm, 480)
    assert gm.car.physics.speed_kmh > 100, gm.car.physics.speed_kmh
    gm.input("c"); gm.input("c"); _frames(gm, 30); gm.input("c")
    keys["d"] = 1; keys["space"] = 1; _frames(gm, 120)
    keys["d"] = keys["space"] = 0
    gm.input("t"); gm.input("2"); _frames(gm, 60)
    assert gm.car.spec.style == "sedan"
    gm.input("tab"); gm.input("r"); _frames(gm, 10)
    assert abs(gm.car.physics.z) < 1.0
    gm.car.physics.z, gm.car.physics.vx = 850.0, 40.0
    keys["w"] = 1
    _frames(gm, 240)
    assert gm.car.physics.z < 900.0 - 2.5, gm.car.physics.z
    keys["w"] = 0
    print("  test_track world OK")


def smoke_city(ur):
    import math
    from core.game_manager import GameManager
    from core.settings import SETTINGS
    gm = GameManager("city")
    n = 0
    while gm.car is None:
        gm.update()
        n += 1
        assert n < 20000
    assert gm.loader.done and len(gm.loader.chunk_entities) > 20 and gm.minimap is not None
    keys = ur.held_keys
    p = gm.car.physics
    assert abs(p.x - 5.75) < 1e-6 and p.z == -175.0
    # drive north along the central avenue for a while: the lane is clear so nothing is hit
    keys["w"] = 1
    _frames(gm, 360)
    assert p.z > -100 and abs(p.x - 5.75) < 1.5 and not p.impact_events, (p.x, p.z)
    # the roundabout island must stop a car driving straight at it
    p.x, p.z, p.vx, p.vy, p.r, p.psi = 0.0, -60.0, 30.0, 0.0, 0.0, 0.0
    min_r = 1e9
    for _ in range(360):
        gm.update()
        min_r = min(min_r, math.hypot(p.x, p.z))
    assert min_r > 13.0, min_r
    assert math.hypot(p.x, p.z) > 13.0, (p.x, p.z)           # slides around the ring, never onto the island
    # grass: lower grip + extra rolling resistance, asphalt: full grip
    p.x, p.z, p.vx = 500.0, 0.0, 10.0
    from vehicles.vehicle_physics import DriveInput
    gm.car.step(DriveInput(), 1 / 60)
    assert abs(p.grip_scale - 0.55) < 1e-9 and p.extra_rolling > 0.0
    p.x, p.z = 5.75, -150.0
    gm.car.step(DriveInput(), 1 / 60)
    assert p.grip_scale == 1.0
    # distance culling toggles chunk entities
    gm.loader._cull_t = 0
    gm.loader.update(0.3, 0.0, 0.0, 150.0)
    states = {e.enabled for ents, _ in gm.loader.chunk_entities.values() for e in ents}
    assert states == {True, False}, states
    gm.loader._cull_t = 0
    gm.loader.update(0.3, 0.0, 0.0, 5000.0)
    assert all(e.enabled for ents, _ in gm.loader.chunk_entities.values() for e in ents)
    gm.input("m"); gm.input("m"); gm.input("2"); _frames(gm, 20)
    assert gm.car.spec.style == "sedan"
    print("  city world OK  (%d chunks, %d obstacles)" % (len(gm.loader.chunk_entities), len(gm.world.obstacles)))


def main():
    ur = build_stub()
    time.dt = 1 / 60
    smoke_test_track(ur)
    ur.held_keys.clear()
    smoke_city(ur)
    import math
    print("smoke test OK")


if __name__ == "__main__":
    main()
