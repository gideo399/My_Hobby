"""Realistic 3D Open-World Driving Simulator.

Run:  python main.py                    (Phase 2 city)
      python main.py --world test_track (Phase 1 test road)
"""
import argparse

from ursina import Sky, Ursina, window
from ursina import color as ucolor

from core.game_manager import GameManager
from core.settings import SETTINGS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", choices=("city", "test_track"), default=SETTINGS.world)
    ap.add_argument("--seed", type=int, default=SETTINGS.seed)
    ap.add_argument("--draw-distance", type=float, default=SETTINGS.graphics.draw_distance)
    args = ap.parse_args()
    SETTINGS.world, SETTINGS.seed = args.world, args.seed
    SETTINGS.graphics.draw_distance = args.draw_distance

    g = SETTINGS.graphics
    app = Ursina(title="Driving Simulator - Phase 2", borderless=False, fullscreen=g.fullscreen,
                 vsync=g.vsync, development_mode=False, show_ursina_splash=False)
    window.exit_button.visible = False
    window.fps_counter.enabled = g.show_fps
    window.color = ucolor.Color(0.53, 0.70, 0.88, 1.0)
    try:
        Sky()
    except Exception as exc:                      # sky texture is cosmetic; never block the game on it
        print("Sky unavailable:", exc)
    GameManager(args.world)
    app.run()


if __name__ == "__main__":
    main()
