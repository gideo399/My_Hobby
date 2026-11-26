"""Driving HUD: speed, gear, RPM bar, drift/TCS indicators, 0-100 timer, controls, messages, pause overlay."""
from ursina import Entity, Text, camera, window
from ursina import color as ucolor

from utilities.helpers import clamp


def rgba(r, g, b, a=1.0):
    return ucolor.Color(r, g, b, a)


class ZeroToHundred:
    """Stopwatch: arms at standstill, starts on first movement, stops at 100 km/h. Pure logic."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.state, self.t, self.result = "armed", 0.0, None

    def update(self, kmh, dt):
        if self.state == "armed" and kmh > 2.0:
            self.state, self.t = "running", 0.0
        if self.state == "running":
            self.t += dt
            if kmh >= 100.0:
                self.state, self.result = "done", self.t
            elif kmh < 1.0 and self.t > 0.5:
                self.state = "armed"
        elif self.state == "done" and kmh < 1.0:
            self.state = "armed"

    def text(self):
        if self.state == "running":
            return f"0-100: {self.t:4.1f}s"
        if self.result is not None:
            return f"0-100: {self.result:.2f}s"
        return "0-100: --"


HELP = ("CONTROLS\n"
        "W / Up        Accelerate\n"
        "S / Down      Brake / Reverse\n"
        "A D / Left Right  Steer\n"
        "Space         Handbrake\n"
        "C  Camera     R  Reset     M  Map\n"
        "T  Traction control\n"
        "1 / 2  Swap car   TAB  Next car\n"
        "H  Horn (audio: Phase 5)\n"
        "F1 Hide help      ESC  Pause")


class HUD:
    BAR_W = 0.36

    def __init__(self):
        a = window.aspect_ratio
        right, left = 0.5 * a - 0.04, -0.5 * a + 0.03
        ui = camera.ui
        Entity(parent=ui, model="quad", color=rgba(0, 0, 0, 0.38), scale=(0.42, 0.21),
               origin=(0.5, -0.5), position=(right + 0.02, -0.49))
        self.speed = Text("0", parent=ui, origin=(0.5, 0), position=(right - 0.02, -0.34), scale=3.2, color=ucolor.white)
        Text("km/h", parent=ui, origin=(0.5, 0), position=(right - 0.02, -0.395), scale=1.1, color=rgba(.8, .8, .8))
        self.gear = Text("N", parent=ui, origin=(-0.5, 0), position=(right - 0.39, -0.34), scale=3.2, color=rgba(1, .85, .2))
        Entity(parent=ui, model="quad", color=rgba(1, 1, 1, 0.18), scale=(self.BAR_W, 0.018),
               origin=(-0.5, 0), position=(right - 0.39, -0.445))
        self.rpm_fill = Entity(parent=ui, model="quad", color=rgba(.3, .9, .3), scale=(0.001, 0.018),
                               origin=(-0.5, 0), position=(right - 0.39, -0.445))
        self.status = Text("", parent=ui, origin=(0.5, 0), position=(right - 0.02, -0.28), scale=1.0, color=rgba(1, .6, .1))
        self.timer = Text("0-100: --", parent=ui, origin=(0, 0), position=(0, 0.46), scale=1.3, color=ucolor.white)
        self.info = Text("", parent=ui, origin=(-0.5, -0.5), position=(left, -0.47), scale=1.0, color=rgba(.9, .9, .9))
        self.msg = Text("", parent=ui, origin=(0, 0), position=(0, 0.38), scale=1.5, color=rgba(1, .9, .3))
        self.help = Text(HELP, parent=ui, origin=(-0.5, 0.5), position=(left, 0.47), scale=0.8, color=rgba(1, 1, 1, 0.85))
        self.overlay = Entity(parent=ui, model="quad", color=rgba(0, 0, 0, 0.6), scale=(3, 2), enabled=False)
        self.loading = Text("", parent=ui, origin=(0, 0), scale=2.0, color=ucolor.white)
        self.pause_text = Text("PAUSED\n\nESC  Resume\nQ  Quit", parent=ui, origin=(0, 0), scale=2.2,
                               color=ucolor.white, enabled=False)
        self.z100 = ZeroToHundred()
        self._msg_t = 0.0
        self._cache = {}

    def _set(self, key, widget, value):
        if self._cache.get(key) != value:
            self._cache[key] = value
            widget.text = value

    def flash(self, text, seconds=2.0):
        self.msg.text, self._msg_t = text, seconds

    def toggle_help(self):
        self.help.enabled = not self.help.enabled

    def set_paused(self, paused):
        self.overlay.enabled = paused
        self.pause_text.enabled = paused

    def reset_timer(self):
        self.z100.reset()

    def update(self, car, camera_mode, dt):
        p, s = car.physics, car.spec
        self._set("speed", self.speed, str(int(round(p.speed_kmh))))
        self._set("gear", self.gear, p.display_gear)
        frac = clamp(p.rpm / s.redline_rpm, 0.0, 1.0)
        self.rpm_fill.scale_x = max(0.001, self.BAR_W * frac)
        key = 0 if frac < 0.7 else 1 if frac < 0.9 else 2
        if self._cache.get("rpmcol") != key:
            self._cache["rpmcol"] = key
            self.rpm_fill.color = (rgba(.3, .9, .3), rgba(1, .8, .1), rgba(1, .2, .1))[key]
        drifting = max(p.slide_front, p.slide_rear) > 1.0 and p.speed > 5.0
        self._set("status", self.status, ("DRIFT  " if drifting else "") + ("TCS ON" if p.traction_control else "TCS OFF"))
        self.z100.update(p.speed_kmh, dt)
        self._set("timer", self.timer, self.z100.text())
        self._set("info", self.info, f"{s.name}   |   camera: {camera_mode}")
        if self._msg_t > 0.0:
            self._msg_t -= dt
            if self._msg_t <= 0.0:
                self.msg.text = ""
