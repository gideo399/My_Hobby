"""Realistic 3D Open-World Driving Simulator - PHASE 1 (core driving prototype).

Run:  python main.py
"""
from ursina import Sky, Ursina, window
from ursina import color as ucolor

from core.game_manager import GameManager
from core.settings import SETTINGS


def main():
    g = SETTINGS.graphics
    app = Ursina(title="Driving Simulator - Phase 1", borderless=False, fullscreen=g.fullscreen,
                 vsync=g.vsync, development_mode=False, show_ursina_splash=False)
    window.exit_button.visible = False
    window.fps_counter.enabled = g.show_fps
    window.color = ucolor.Color(0.53, 0.70, 0.88, 1.0)
    try:
        Sky()
    except Exception as exc:                      # sky texture is cosmetic; never block the game on it
        print("Sky unavailable:", exc)
    GameManager()
    app.run()


if __name__ == "__main__":
    main()
