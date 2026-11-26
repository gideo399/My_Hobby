# Realistic 3D Open-World Driving Simulator — Phase 2 (environment and city)

## Install & run
```
python -m venv venv && venv\Scripts\activate      (Windows)   |   source venv/bin/activate (macOS/Linux)
pip install -r requirements.txt                    # ursina (pulls in panda3d), numpy, Pillow
python main.py                     # Phase 2 city (default)
python main.py --world test_track  # Phase 1 test road, unchanged
python main.py --draw-distance 350 # lower = faster on weak GPUs; --seed N = different city
```
Python 3.10-3.12 recommended. Checks (no GPU needed): `python -m tests.test_phase1` (physics), `python -m tests.test_city` (city), `python -m tests.smoke_headless` (whole game loop vs an Ursina stub). `python -m tests.preview_render` writes software preview images of the city to /tmp.

## Controls
W/Up accelerate · S/Down brake then reverse · A,D/Left,Right steer · Space handbrake · C camera (chase/hood/cinematic) ·
M minimap · R reset · T traction control · 1/2 or TAB swap car · F1 hide help · ESC pause (Q quits from pause).
H (horn) and F (enter/exit) are wired but only show a message: audio is Phase 5, enter/exit is Phase 4.

## Architecture
```
main.py                     window + Sky + GameManager
core/        settings.py (configurable), asset_manager.py (cache, procedural textures, mesh conversion),
             camera_rig.py (pure-maths chase/hood/cinematic camera), game_manager.py (frame loop, input)
vehicles/    vehicle_specs.py (data-driven cars), vehicle_physics.py (pure-Python dynamics),
             procedural_car.py (lofted bodies + wheels), car.py (physics + collision + Ursina entities),
             vehicle_controller.py (key smoothing)
environment/ layout.py (grid constants, SurfaceMap), roads.py (road network, markings, crossings, roundabout,
             signals/signs, lane graph), buildings.py (towers/offices/apartments/shops/houses, parks, parking lots),
             props.py (lamps, trees, benches, bus stops, billboards, fences, parked cars), terrain.py (perimeter,
             tree belt, backdrop hills), city.py (generator + time-sliced loader + distance culling),
             test_track.py (Phase 1 road, kept)
utilities/   collision.py (OBB SAT, grid broad-phase, ray cast), mesh_builder.py, helpers.py
ui/          hud.py (speed, gear, RPM bar, drift/TCS, 0-100 timer, controls, pause), minimap.py
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

## Phase 2: the city
* **Layout:** 9x9 road grid (880 m across, 8x8 blocks), 4-lane avenues with painted medians alternating with 2-lane streets
  with parking lanes, a roundabout at the centre, T/corner junctions at the edge. Lanes are 3.5-3.6 m, sidewalks 3.5-4 m,
  right-hand traffic. Downtown towers (up to ~40 floors) in the middle, mixed commercial ring, houses outside, 4 parks, 2 parking lots.
* **Roads:** lane dividers, double yellow, edge lines, zebra crossings, stop/yield lines, curbs, signal poles at avenue
  junctions, stop/yield/speed signs.
* **Buildings:** textured facades (windows tile on whole bays/floors) with podiums, setbacks, parapets, rooftop plant, awnings,
  balconies, gabled roofs, chimneys, garages, fences. **Nothing is a plain cube city**, but they are stylised low-poly.
* **Props:** ~660 streetlights, ~1600 trees, benches, bins, bus shelters, billboards, parked cars (static solids).
* **Collision:** ~4,500 solids (buildings, trees, poles, signs, fences, island, perimeter wall) in a grid broad-phase.
* **Surfaces:** grass has 55% grip and extra rolling resistance, sidewalks ~95%; curbs are drawn at +12 cm and the car eases up/down.
* **Performance:** the world is split into 220 m chunks (about 300 entities); chunks beyond `draw_distance` are hidden, geometry
  is generated in ~1 s and meshes are created one per frame behind a progress message. ~333k triangles in total.
* **Lane graph** (`CityBuilder.lanes/nodes/signal_sites/stop_lines`) is generated now for the Phase 3 traffic AI.

## Phase 2 honest limitations
* Rendering/Ursina calls are still unverified on a real GPU (not installable here). The software preview shows geometry only,
  not textures or real engine behaviour.
* **Hills/terrain variation:** only a non-drivable backdrop beyond the perimeter wall. Drivable slopes need height-field physics.
* **Traffic lights** have poles, heads and dim static lamps. Cycling logic and AI obeying them is Phase 3.
* Signs are shapes without lettering (no text in 3D yet). Windows are textures; night-time glow comes with Phase 5 lighting.
* Parked cars, cones and fences are static (knock-over/damage physics is Phase 4). Pedestrians/animals: Phase 3-4.
* Lighting is still baked vertex shading; real lights/shadows/LOD are Phases 5-6.
