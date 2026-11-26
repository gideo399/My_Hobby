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
