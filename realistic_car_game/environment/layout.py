"""City layout constants + surface classification map (pure Python/numpy, no engine imports).

World: metres, +X right, +Z forward, ground plane y=0 is the road surface.
The city is a regular grid of roads.  Lines i = -N..N sit at coordinate i*S on each axis.
Even lines are 4-lane avenues (with a painted median), odd lines are 2-lane streets with parking lanes.
The crossing of the two centre avenues (0, 0) is a roundabout.
"""
import numpy as np

S = 110.0                    # spacing between road centre-lines
N = 4                        # lines -N..N  -> 8 x 8 blocks, ~900 m across
AVE_CW, AVE_SW = 7.5, 4.0    # avenue: half carriageway, sidewalk width
ST_CW, ST_SW = 5.7, 3.5      # street
RB_R_OUT, RB_R_ISLAND, RB_SW = 24.5, 14.0, 4.0
CURB_H = 0.12
CHUNK = 220.0                # render chunk size (2x2 blocks)
CITY_HALF = N * S + AVE_CW + AVE_SW      # ~ 451.5 m
WORLD_HALF = 600.0           # ground / perimeter extent
WALL_HALF = 575.0


def pos(i):
    return i * S


def is_avenue(i):
    return i % 2 == 0


def cw(i):
    return AVE_CW if is_avenue(i) else ST_CW


def sw(i):
    return AVE_SW if is_avenue(i) else ST_SW


def row(i):
    return cw(i) + sw(i)


def is_roundabout(i, j):
    return i == 0 and j == 0


def block_rect(i, j):
    """Buildable area of block (i, j) between lines i,i+1 (x) and j,j+1 (z): (x0, z0, x1, z1)."""
    return (pos(i) + row(i), pos(j) + row(j), pos(i + 1) - row(i + 1), pos(j + 1) - row(j + 1))


class SurfaceMap:
    GRASS, ASPHALT, SIDEWALK, PATH = 0, 1, 2, 3
    NAMES = ("grass", "asphalt", "sidewalk", "path")
    GRIP = (0.55, 1.00, 0.95, 0.75)
    ROLL = (0.045, 0.0, 0.0, 0.02)
    HEIGHT = (-0.05, 0.0, CURB_H, 0.0)

    def __init__(self, half=WORLD_HALF, cell=2.0):
        self.half, self.cell = half, cell
        self.n = int(2 * half / cell)
        self.grid = np.zeros((self.n, self.n), dtype=np.uint8)

    def _ix(self, v):
        return int(np.clip((v + self.half) / self.cell, 0, self.n - 1))

    def fill_rect(self, kind, x0, z0, x1, z1):
        a0, a1 = self._ix(min(x0, x1)), self._ix(max(x0, x1))
        b0, b1 = self._ix(min(z0, z1)), self._ix(max(z0, z1))
        self.grid[a0:a1 + 1, b0:b1 + 1] = kind

    def fill_disc(self, kind, cx, cz, r, r_in=0.0):
        a0, a1 = self._ix(cx - r), self._ix(cx + r)
        b0, b1 = self._ix(cz - r), self._ix(cz + r)
        xs = (np.arange(a0, a1 + 1) + 0.5) * self.cell - self.half - cx
        zs = (np.arange(b0, b1 + 1) + 0.5) * self.cell - self.half - cz
        d2 = xs[:, None] ** 2 + zs[None, :] ** 2
        mask = (d2 <= r * r) & (d2 >= r_in * r_in)
        sub = self.grid[a0:a1 + 1, b0:b1 + 1]
        sub[mask] = kind

    def kind_at(self, x, z):
        if abs(x) >= self.half or abs(z) >= self.half:
            return self.GRASS
        return int(self.grid[int((x + self.half) / self.cell), int((z + self.half) / self.cell)])

    def query(self, x, z):
        """(grip multiplier, extra rolling resistance, surface height)"""
        k = self.kind_at(x, z)
        return self.GRIP[k], self.ROLL[k], self.HEIGHT[k]

    def minimap_image(self, size=256, building_rects=()):
        """Top-down RGB PIL image of the whole world for the HUD minimap (north = +Z = up)."""
        from PIL import Image
        step = max(1, self.n // size)
        g = self.grid[::step, ::step].T[::-1]                  # rows = z descending
        pal = np.array([(70, 120, 60), (60, 62, 68), (150, 150, 145), (190, 170, 120)], dtype=np.uint8)
        img = pal[g].copy()
        h, w = g.shape
        for (x0, z0, x1, z1) in building_rects:
            a0, a1 = int((x0 + self.half) / (2 * self.half) * w), int((x1 + self.half) / (2 * self.half) * w)
            b0, b1 = int((z0 + self.half) / (2 * self.half) * h), int((z1 + self.half) / (2 * self.half) * h)
            img[h - b1:h - b0, a0:a1] = (112, 108, 104)
        return Image.fromarray(img, "RGB")
