"""Data-driven vehicle definitions. Every number is SI (metres, kg, N, Nm, rad/s unless noted)."""
import math
from dataclasses import dataclass, field


@dataclass
class VehicleSpec:
    name: str
    style: str                      # selects the procedural body profile
    default_paint: tuple            # (r, g, b, a) 0..1

    # --- geometry -------------------------------------------------------
    length: float
    width: float                    # overall, including tyres
    height: float
    wheelbase: float
    track: float                    # centre-to-centre distance between left/right wheels
    weight_front: float             # static front weight fraction (0..1)
    cg_height: float
    wheel_radius: float
    wheel_width: float

    # --- mass -----------------------------------------------------------
    mass: float
    inertia_factor: float = 0.95    # Iz = factor * m * a * b (typical road car ~0.9-1.2)

    # --- tyres (simplified Pacejka "magic formula": Fy = D sin(C atan(B alpha))) ----
    mu_front: float = 1.0
    mu_rear: float = 1.0
    B_front: float = 9.0
    B_rear: float = 9.5
    C: float = 1.4

    # --- drivetrain -------------------------------------------------------
    drive: str = "RWD"              # RWD | FWD | AWD
    torque_curve: list = field(default_factory=list)   # (rpm, Nm) at wide-open throttle
    idle_rpm: float = 900.0
    clutch_rpm: float = 3000.0      # engine speed while the clutch slips at launch
    redline_rpm: float = 7000.0
    gear_ratios: list = field(default_factory=list)
    reverse_ratio: float = 3.4
    final_drive: float = 3.9
    drivetrain_eff: float = 0.9
    shift_up_frac: float = 0.88     # of redline
    shift_down_frac: float = 0.32
    shift_time: float = 0.22
    reverse_speed_limit: float = 9.0
    engine_brake: float = 0.035     # fraction of weight decelerating when off-throttle

    # --- brakes -----------------------------------------------------------
    brake_g: float = 1.1            # maximum brake force as multiple of weight
    brake_bias_front: float = 0.65

    # --- aero / rolling -----------------------------------------------------
    cd_a: float = 0.65              # drag coefficient * frontal area (m^2)
    downforce: float = 0.0          # N per (m/s)^2
    crr: float = 0.014

    # --- steering -----------------------------------------------------------
    max_steer_deg: float = 34.0
    steer_grip_k: float = 1.25      # how far past the grip limit full steering may demand
    steer_response: float = 14.0    # 1/s

    # --- body motion (visual suspension) -------------------------------------
    pitch_deg_per_ms2: float = 0.4
    roll_deg_per_ms2: float = 0.5
    body_freq_hz: float = 2.0
    body_damping: float = 0.45

    # derived ------------------------------------------------------------------
    @property
    def b(self):                    # CG -> rear axle
        return self.weight_front * self.wheelbase

    @property
    def a(self):                    # CG -> front axle
        return self.wheelbase - self.b

    @property
    def inertia(self):
        return self.inertia_factor * self.mass * self.a * self.b

    @property
    def brake_force(self):
        return self.brake_g * self.mass * 9.81

    @property
    def shift_up_rpm(self):
        return self.shift_up_frac * self.redline_rpm

    @property
    def shift_down_rpm(self):
        return self.shift_down_frac * self.redline_rpm

    @property
    def max_steer(self):
        return math.radians(self.max_steer_deg)


SPORTS_CAR = VehicleSpec(
    name="Apex GT (sports car)", style="sports", default_paint=(0.75, 0.08, 0.06, 1.0),
    length=4.50, width=1.92, height=1.21, wheelbase=2.65, track=1.62,
    weight_front=0.47, cg_height=0.46, wheel_radius=0.34, wheel_width=0.28,
    mass=1500.0, inertia_factor=0.95,
    mu_front=1.20, mu_rear=1.25, B_front=9.5, B_rear=9.5,
    drive="RWD",
    torque_curve=[(1000, 250), (2000, 340), (3000, 400), (4000, 440), (5000, 470),
                  (6000, 480), (7000, 440), (7600, 380)],
    idle_rpm=900, clutch_rpm=3200, redline_rpm=7500,
    gear_ratios=[3.60, 2.35, 1.70, 1.30, 1.05, 0.88], final_drive=3.9,
    brake_g=1.15, brake_bias_front=0.62,
    cd_a=0.64, downforce=0.12, crr=0.013,
    max_steer_deg=34.0, steer_grip_k=1.3,
    pitch_deg_per_ms2=0.30, roll_deg_per_ms2=0.40, body_freq_hz=2.4,
)

SEDAN = VehicleSpec(
    name="Meridian (sedan)", style="sedan", default_paint=(0.10, 0.28, 0.55, 1.0),
    length=4.80, width=1.86, height=1.46, wheelbase=2.80, track=1.62,
    weight_front=0.58, cg_height=0.55, wheel_radius=0.33, wheel_width=0.24,
    mass=1450.0, inertia_factor=1.05,
    mu_front=1.00, mu_rear=1.02, B_front=9.0, B_rear=10.0,
    drive="FWD",
    torque_curve=[(1000, 130), (2000, 200), (3000, 240), (4000, 255), (5000, 240),
                  (6000, 210), (6600, 170)],
    idle_rpm=800, clutch_rpm=2600, redline_rpm=6500,
    gear_ratios=[3.55, 2.05, 1.40, 1.05, 0.85], final_drive=4.2,
    brake_g=1.0, brake_bias_front=0.68,
    cd_a=0.66, downforce=0.0, crr=0.015,
    max_steer_deg=36.0, steer_grip_k=1.2,
    pitch_deg_per_ms2=0.55, roll_deg_per_ms2=0.70, body_freq_hz=1.7, body_damping=0.4,
)

VEHICLE_SPECS = {"sports": SPORTS_CAR, "sedan": SEDAN}
VEHICLE_ORDER = ["sports", "sedan"]
