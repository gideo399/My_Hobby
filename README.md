# Realistic 3D Open-World Driving Simulator — Phase 1 (core driving prototype)

## Install & run
```
python -m venv venv && venv\Scripts\activate      (Windows)   |   source venv/bin/activate (macOS/Linux)
pip install -r requirements.txt                    # ursina (pulls in panda3d), numpy, Pillow
python main.py
```
Python 3.10-3.12 recommended. Optional checks (no GPU needed): `python -m tests.test_phase1` and `python -m tests.smoke_headless`.

## Controls
W/Up accelerate · S/Down brake then reverse · A,D/Left,Right steer · Space handbrake · C camera (chase/hood/cinematic) ·
R reset · T traction control · 1/2 or TAB swap car · F1 hide help · ESC pause (Q quits from pause).
H (horn) and F (enter/exit) are wired but only show a message: audio is Phase 5, enter/exit is Phase 4.

## Architecture
```
main.py                     window + Sky + GameManager
core/        settings.py (configurable), asset_manager.py (cache, procedural textures, mesh conversion),
             camera_rig.py (pure-maths chase/hood/cinematic camera), game_manager.py (frame loop, input)
vehicles/    vehicle_specs.py (data-driven cars), vehicle_physics.py (pure-Python dynamics),
             procedural_car.py (lofted bodies + wheels), car.py (physics + collision + Ursina entities),
             vehicle_controller.py (key smoothing)
environment/ test_track.py (Phase 1 road, skid pad, cones, barriers, walls)
utilities/   collision.py (OBB SAT, grid broad-phase, ray cast), mesh_builder.py, helpers.py
ui/          hud.py (speed, gear, RPM bar, drift/TCS, 0-100 timer, controls, pause)
tests/       unit tests + headless smoke test
traffic/ gameplay/           empty packages reserved for Phases 3-4
```
Design rule: everything that can be engine-independent *is* (physics, collision, camera, mesh generation), so it is
unit-tested and later phases can reuse it.

## World coordinates and scale
Ursina convention: **1 unit = 1 metre, +X right, +Y up, +Z forward** (left-handed). Heading `psi` (radians) gives
forward = (sin psi, cos psi); it equals Ursina's `rotation_y` in degrees. Road lanes are 3.6 m, the sports car is
4.5 x 1.92 x 1.21 m, the sedan 4.8 x 1.86 x 1.46 m. Speeds are m/s internally, km/h on the HUD.

## Vehicle physics (what is real and what is not)
Planar dynamic bicycle model at 120 Hz sub-steps (frame-rate independent): per-axle simplified Pacejka tyre curves,
friction-circle coupling of traction/braking with cornering, longitudinal load transfer, engine torque curve,
automatic gearbox with clutch slip and rev limiter, drag/downforce/rolling resistance, handbrake that unloads the rears,
speed-sensitive steering derived from the grip limit, and impulse collision response with yaw. Body pitch/roll are a
2-DOF spring-damper driven by the real accelerations (visual suspension). Drift, power-oversteer and brake-lock behaviour
emerge from the model. **Not in Phase 1:** per-wheel suspension travel, terrain/hills (the world is flat), Bullet.
Bullet's raycast vehicle becomes worthwhile when terrain arrives; the pure-Python model is easier to tune and test.

## Which library does what
| Concern | Phase 1 uses |
|---|---|
| Window, entities, input, UI text/quads, camera, textures | Ursina |
| Rendering, scene graph (under the hood) | Panda3D |
| Vehicle dynamics, collision, camera maths, mesh generation | own pure Python (no engine) |
| Procedural textures | numpy + Pillow |
| Real lighting/shadows, Bullet, audio, particles | later phases (Panda3D directly where Ursina is not enough) |

## Honest status / limitations
* Verified here: physics, collision, camera, mesh geometry and the whole game loop (against an Ursina stub).
* **Not verified here:** actual rendering and Ursina API calls, because Ursina/Panda3D could not be installed in my
  environment. Please run it and send me any traceback.
* Visuals are stylised procedural low-poly (lofted bodies, no external models). Lighting is baked into vertex colours;
  real lights/shadows are Phase 5. Cars have no interior. Cones and barriers are static (knock-over physics: Phase 4).

## Troubleshooting
* Car looks inside-out / invisible: set `FLIP_WINDING = True` in `utilities/mesh_builder.py`.
* Road markings flicker far away: raise `camera_near` in `core/settings.py`.
* Low FPS: lower `texture_size` in settings, set `vsync` False.
