"""Top-down minimap generated from the city's surface map (north = up)."""
from ursina import Entity, Texture, camera, window
from ursina import color as ucolor

from environment.layout import CITY_HALF, WORLD_HALF

REGION = CITY_HALF + 40.0            # metres shown on each side of the centre


class MiniMap:
    SIZE = 0.30

    def __init__(self, surface, building_rects):
        img = surface.minimap_image(512, building_rects)
        px = img.width / (2 * WORLD_HALF)
        c = img.width / 2
        img = img.crop((int(c - REGION * px), int(c - REGION * px), int(c + REGION * px), int(c + REGION * px)))
        right = 0.5 * window.aspect_ratio - 0.04
        self.cx, self.cy = right - self.SIZE / 2, 0.5 - 0.06 - self.SIZE / 2
        self.frame = Entity(parent=camera.ui, model="quad", color=ucolor.Color(0, 0, 0, 0.55),
                            scale=self.SIZE + 0.012, position=(self.cx, self.cy))
        self.map = Entity(parent=camera.ui, model="quad", texture=Texture(img), scale=self.SIZE,
                          position=(self.cx, self.cy - 0.0001))
        self.dot = Entity(parent=camera.ui, model="quad", color=ucolor.Color(1.0, 0.15, 0.1, 1), scale=0.012,
                          position=(self.cx, self.cy))

    def set_visible(self, v):
        for e in (self.frame, self.map, self.dot):
            e.enabled = v

    @property
    def visible(self):
        return self.frame.enabled

    def update(self, x, z):
        k = self.SIZE / (2 * REGION)
        self.dot.position = (self.cx + max(-REGION, min(REGION, x)) * k, self.cy + max(-REGION, min(REGION, z)) * k)
