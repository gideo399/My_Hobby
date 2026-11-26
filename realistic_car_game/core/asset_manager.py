"""Asset management: caching, procedural textures, mesh conversion, optional external models.

Phase 1 ships with *no* external binary assets; textures are generated procedurally (tileable noise)
and cached. Drop licensed models into assets/models and use load_model() in later phases.
"""
import os

ASSET_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def make_noise_image(base_rgb, variation=10.0, size=256, seed=1, speckle=None):
    """Tileable value noise as a PIL image (wrap-around blur keeps edges seamless)."""
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed)
    n = rng.normal(0.0, 1.0, (size, size))
    for _ in range(3):
        n = (n + np.roll(n, 1, 0) + np.roll(n, -1, 0) + np.roll(n, 1, 1) + np.roll(n, -1, 1)) / 5.0
    n = n / (n.std() + 1e-9)
    fine = rng.normal(0.0, 1.0, (size, size)) * 0.35
    field = (n + fine)[..., None] * variation
    img = np.asarray(base_rgb, dtype=float)[None, None, :] + field
    if speckle:                                         # sparse bright grains (asphalt aggregate)
        mask = rng.random((size, size)) < speckle
        img[mask] += 28.0
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"), "RGB")


def make_sidewalk_image(size=256, seed=2):
    """Concrete slabs: 2x2 slabs per tile (tile = 4 m), darker joints, tileable noise."""
    import numpy as np
    from PIL import Image, ImageDraw
    base = make_noise_image((186, 184, 178), 5.0, size, seed)
    d = ImageDraw.Draw(base)
    half = size // 2
    for k in (0, half):
        d.line([(k, 0), (k, size)], fill=(140, 138, 134), width=2)
        d.line([(0, k), (size, k)], fill=(140, 138, 134), width=2)
    return base


def make_facade_image(style, size=256, seed=0):
    """One tile = 4 bays x 4 floors of a facade (the 'shop' tile is 4 bays x 1 floor)."""
    import random
    import numpy as np
    from PIL import Image, ImageDraw
    rnd = random.Random(seed)
    c = size // 4
    w, h = size, (c if style == "shop" else size)
    img = Image.new("RGB", (w, h), (200, 200, 196))
    d = ImageDraw.Draw(img)
    rows = 1 if style == "shop" else 4

    def jitter(col, a):
        return tuple(max(0, min(255, v + rnd.randint(-a, a))) for v in col)

    if style == "brick":
        d.rectangle([0, 0, w, h], fill=(158, 78, 60))
        bh = max(3, c // 11)
        for ry, y in enumerate(range(0, h, bh)):
            for x in range(-(bh * 2 if ry % 2 else 0), w, bh * 4):
                d.rectangle([x, y, x + bh * 4 - 1, y + bh - 1], fill=jitter((158, 78, 60), 14), outline=(196, 186, 170))
    elif style == "concrete":
        d.rectangle([0, 0, w, h], fill=(172, 172, 168))
    elif style == "siding":
        d.rectangle([0, 0, w, h], fill=(236, 233, 226))
        for y in range(0, h, 5):
            d.line([(0, y), (w, y)], fill=(212, 209, 202), width=1)
    elif style == "office":
        d.rectangle([0, 0, w, h], fill=(204, 204, 199))
    elif style == "glass":
        d.rectangle([0, 0, w, h], fill=(70, 96, 122))
    elif style == "shop":
        d.rectangle([0, 0, w, h], fill=(70, 68, 72))

    for ry in range(rows):
        for cx in range(4):
            x0, y0 = cx * c, ry * c
            if style == "glass":
                base = (rnd.randint(52, 96), rnd.randint(82, 122), rnd.randint(108, 150))
                d.rectangle([x0 + 1, y0 + 1, x0 + c - 2, y0 + int(c * 0.76)], fill=base)
                d.rectangle([x0 + 1, y0 + 1, x0 + c - 2, y0 + int(c * 0.30)], fill=jitter((base[0] + 14, base[1] + 16, base[2] + 18), 3))
                d.rectangle([x0, y0 + int(c * 0.76), x0 + c, y0 + c], fill=(40, 56, 72))
                d.line([(x0, y0), (x0, y0 + c)], fill=(150, 162, 176), width=2)
                d.line([(x0, y0), (x0 + c, y0)], fill=(150, 162, 176), width=2)
            elif style == "office":
                lit = rnd.random() < 0.10
                gl = (214, 196, 142) if lit else (rnd.randint(40, 62), rnd.randint(66, 92), rnd.randint(92, 122))
                d.rectangle([x0 + 3, y0 + int(c * 0.22), x0 + c - 4, y0 + int(c * 0.76)], fill=gl, outline=(90, 94, 98))
                d.line([(x0 + c // 2, y0 + int(c * 0.22)), (x0 + c // 2, y0 + int(c * 0.76))], fill=(90, 94, 98), width=1)
            elif style in ("brick", "siding"):
                curtain = rnd.random() < 0.28
                gl = (226, 214, 188) if curtain else (rnd.randint(36, 56), rnd.randint(52, 72), rnd.randint(70, 92))
                wx0, wx1, wy0, wy1 = x0 + int(c * .30), x0 + int(c * .70), y0 + int(c * .20), y0 + int(c * .72)
                d.rectangle([wx0 - 3, wy0 - 3, wx1 + 3, wy1 + 3], fill=(240, 240, 236))
                d.rectangle([wx0, wy0, wx1, wy1], fill=gl)
                d.line([((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1)], fill=(240, 240, 236), width=2)
                d.rectangle([wx0 - 5, wy1 + 3, wx1 + 5, wy1 + 6], fill=(214, 212, 206))
            elif style == "concrete":
                d.line([(x0, y0 + c - 1), (x0 + c, y0 + c - 1)], fill=(128, 128, 124), width=2)
                d.line([(x0, y0), (x0, y0 + c)], fill=(140, 140, 136), width=1)
            elif style == "shop":
                d.rectangle([x0 + 3, int(c * .20), x0 + c - 4, int(c * .90)], fill=(rnd.randint(92, 120), rnd.randint(128, 152), rnd.randint(140, 166)), outline=(30, 30, 34))
                d.rectangle([x0, 0, x0 + c, int(c * .14)], fill=(214, 214, 208))
                if cx == 1:
                    d.rectangle([x0 + int(c * .25), int(c * .20), x0 + int(c * .75), c - 1], fill=(44, 52, 60), outline=(20, 20, 24))
    arr = np.asarray(img).astype(float)
    arr += np.random.default_rng(seed).normal(0, 3.0, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB")


class AssetManager:
    def __init__(self, texture_size=256):
        self.texture_size = texture_size
        self._textures = {}

    def noise_texture(self, name, base_rgb, variation=10.0, seed=1, speckle=None):
        if name not in self._textures:
            from ursina import Texture
            tex = Texture(make_noise_image(base_rgb, variation, self.texture_size, seed, speckle))
            try:
                tex.filtering = "mipmap"
            except Exception:
                pass
            self._textures[name] = tex
        return self._textures[name]

    def image_texture(self, name, image_fn):
        if name not in self._textures:
            from ursina import Texture
            tex = Texture(image_fn())
            try:
                tex.filtering = "mipmap"
            except Exception:
                pass
            self._textures[name] = tex
        return self._textures[name]

    def city_textures(self):
        """part-name -> Texture for every textured mesh part used by the city."""
        n, ts = self.texture_size, self.texture_size
        t = {"asphalt": self.noise_texture("asphalt", (62, 62, 66), 7, seed=5, speckle=0.012),
             "ground": self.noise_texture("grass", (70, 104, 52), 11, seed=11),
             "sidewalk": self.image_texture("sidewalk", lambda: make_sidewalk_image(ts))}
        for style in ("glass", "office", "brick", "shop", "siding", "concrete"):
            t["f_" + style] = self.image_texture("f_" + style, lambda st=style: make_facade_image(st, ts, seed=hash(st) % 997))
        return t

    def load_model(self, filename):
        """Load assets/models/<filename> if present (CC0/licensed assets), else None."""
        path = os.path.join(ASSET_ROOT, "models", filename)
        if not os.path.exists(path):
            return None
        from ursina import load_model
        return load_model(path)


def to_ursina_mesh(data):
    """MeshData -> ursina.Mesh (vertex colours + uvs; normals are not needed by the unlit pipeline)."""
    from ursina import Mesh
    from ursina import color as ucolor
    return Mesh(vertices=data.vertices, triangles=data.triangles, uvs=data.uvs,
                colors=[ucolor.Color(*c) for c in data.colors], static=True)
