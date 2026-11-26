"""GameManager: owns the world, the player car, camera and HUD, and runs the per-frame loop.

Frame order: input -> physics (sub-stepped, with per-sub-step collision) -> visuals -> camera -> HUD.
"""
import math
import time

from ursina import Entity, Vec3, application, camera

from core.asset_manager import AssetManager
from core.camera_rig import CameraRig
from core.settings import SETTINGS
from environment.test_track import TestTrack
from ui.hud import HUD
from utilities.collision import CollisionWorld
from vehicles.car import Car
from vehicles.vehicle_controller import KeyboardController
from vehicles.vehicle_specs import VEHICLE_ORDER, VEHICLE_SPECS


class GameManager(Entity):
    def __init__(self):
        super().__init__()
        g = SETTINGS.graphics
        camera.clip_plane_near = g.camera_near
        self.assets = AssetManager(g.texture_size)
        self.world = CollisionWorld()
        self.track = TestTrack(self.world, self.assets)
        self.controller = KeyboardController()
        self.camera_rig = CameraRig(self.world, g.fov)
        self.hud = HUD()
        self.paused = False
        self.car = None
        self.vehicle_index = 0
        self._spawn(VEHICLE_ORDER[0])

    # ------------------------------------------------------------------ spawning
    def _spawn(self, key):
        traction = self.car.physics.traction_control if self.car else True
        if self.car:
            self.car.destroy()
        x, z, heading = self.track.spawn
        self.car = Car(VEHICLE_SPECS[key], self.world, x, z, heading, settings=SETTINGS)
        self.car.physics.traction_control = traction
        self.controller.reset()
        self.camera_rig.snap(self.car.physics)
        self.hud.reset_timer()
        self.hud.flash(self.car.spec.name)

    def _reset_car(self):
        x, z, heading = self.track.spawn
        self.car.reset(x, z, heading)
        self.controller.reset()
        self.camera_rig.snap(self.car.physics)
        self.hud.reset_timer()

    # --------------------------------------------------------------------- input
    def input(self, key):
        if key == "escape":
            self.paused = not self.paused
            self.hud.set_paused(self.paused)
            return
        if self.paused:
            if key == "q":
                application.quit()
            return
        if key == "c":
            self.hud.flash("Camera: " + self.camera_rig.cycle_mode())
        elif key == "r":
            self._reset_car()
        elif key == "t":
            p = self.car.physics
            p.traction_control = not p.traction_control
            self.hud.flash("Traction control " + ("ON" if p.traction_control else "OFF"))
        elif key in ("1", "2"):
            idx = int(key) - 1
            if idx < len(VEHICLE_ORDER):
                self.vehicle_index = idx
                self._spawn(VEHICLE_ORDER[idx])
        elif key == "tab":
            self.vehicle_index = (self.vehicle_index + 1) % len(VEHICLE_ORDER)
            self._spawn(VEHICLE_ORDER[self.vehicle_index])
        elif key == "h":
            self.hud.flash("Horn: audio is added in Phase 5")
        elif key == "f":
            self.hud.flash("Enter/exit vehicle: not implemented yet (Phase 4)")
        elif key == "f1":
            self.hud.toggle_help()

    # --------------------------------------------------------------------- frame
    def update(self):
        if self.paused or self.car is None:
            return
        dt = min(time.dt, SETTINGS.physics.max_frame_dt)
        if dt <= 0.0:
            return
        self.car.step(self.controller.poll(dt), dt)
        self.car.sync_visuals()
        pose = self.camera_rig.update(dt, self.car.physics)
        camera.world_position = Vec3(pose.x, pose.y, pose.z)
        camera.world_rotation = Vec3(pose.pitch_deg, pose.yaw_deg, pose.roll_deg)
        camera.fov = pose.fov
        p = self.car.physics
        if p.impact_events:
            speed = max(e[0] for e in p.impact_events)
            p.impact_events.clear()
            self.hud.flash(f"Impact {speed * 3.6:.0f} km/h", 1.2)
        self.hud.update(self.car, self.camera_rig.mode, dt)
