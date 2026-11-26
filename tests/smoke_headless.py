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


def main():
    ur = build_stub()
    time.dt = 1 / 60
    from core.game_manager import GameManager
    from core.settings import SETTINGS
    gm = GameManager()
    keys = ur.held_keys

    def run(frames):
        for _ in range(frames):
            gm.update()

    keys["w"] = 1
    run(480)
    p = gm.car.physics
    assert p.speed_kmh > 100, p.speed_kmh
    gm.input("c"); gm.input("c"); run(30); gm.input("c")
    keys["d"] = 1; keys["space"] = 1; run(120)
    keys["d"] = keys["space"] = 0
    gm.input("t"); gm.input("2"); run(60)
    assert gm.car.spec.style == "sedan"
    gm.input("tab"); gm.input("r"); run(10)
    assert abs(gm.car.physics.z) < 1.0
    # drive straight into the end wall at the end of the road: must be stopped by collision
    gm.car.physics.z, gm.car.physics.vx = 850.0, 40.0
    keys["w"] = 1
    run(240)
    assert gm.car.physics.z < 900.0 - 2.5, gm.car.physics.z
    gm.input("escape"); gm.update(); gm.input("escape")
    gm.input("h"); gm.input("f"); gm.input("f1")
    # all HUD / camera numbers must be finite
    import math
    assert all(math.isfinite(v) for v in (gm.car.physics.x, gm.car.physics.z, ur.camera.fov))
    print("smoke test OK  (final speed %.0f km/h, z=%.1f)" % (gm.car.physics.speed_kmh, gm.car.physics.z))


if __name__ == "__main__":
    main()
