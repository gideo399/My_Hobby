"""Central, configurable settings (graphics / physics). Extended in later phases."""
from dataclasses import dataclass, field


@dataclass
class GraphicsSettings:
    fullscreen: bool = False
    vsync: bool = True
    fov: float = 85.0
    show_fps: bool = True
    texture_size: int = 256          # procedural texture resolution (lower = faster)
    camera_near: float = 0.3         # larger near plane = less z-fighting on road decals


@dataclass
class PhysicsSettings:
    fixed_dt: float = 1.0 / 120.0    # physics sub-step
    max_substeps: int = 8
    max_frame_dt: float = 0.05       # clamp for lag spikes (frame-rate independence)


@dataclass
class Settings:
    graphics: GraphicsSettings = field(default_factory=GraphicsSettings)
    physics: PhysicsSettings = field(default_factory=PhysicsSettings)


SETTINGS = Settings()
