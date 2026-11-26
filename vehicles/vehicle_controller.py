"""Turns raw key state into smoothed DriveInput. The smoothing class is pure Python (testable);
KeyboardController reads Ursina's held_keys lazily."""
from utilities.helpers import approach
from vehicles.vehicle_physics import DriveInput


class InputSmoother:
    """Keyboards are digital: ramp pedals and steering so the car behaves like it has analog input."""
    def __init__(self, throttle_rise=4.5, throttle_fall=9.0, brake_rise=7.0, brake_fall=12.0,
                 steer_rise=2.6, steer_return=5.5, steer_flip=7.0):
        self.cfg = (throttle_rise, throttle_fall, brake_rise, brake_fall, steer_rise, steer_return, steer_flip)
        self.out = DriveInput()

    def reset(self):
        self.out = DriveInput()

    def update(self, raw: DriveInput, dt) -> DriveInput:
        tr, tf, br, bf, sr, sret, sflip = self.cfg
        o = self.out
        o.throttle = approach(o.throttle, raw.throttle, (tr if raw.throttle > o.throttle else tf) * dt)
        o.brake = approach(o.brake, raw.brake, (br if raw.brake > o.brake else bf) * dt)
        if raw.steer == 0.0:
            rate = sret
        elif o.steer * raw.steer < 0.0:
            rate = sflip                      # counter-steering must be quick (drifting)
        else:
            rate = sr
        o.steer = approach(o.steer, raw.steer, rate * dt)
        o.handbrake = raw.handbrake
        return o


class KeyboardController:
    def __init__(self):
        self.smoother = InputSmoother()

    def raw(self):
        from ursina import held_keys
        k = held_keys
        throttle = 1.0 if (k["w"] or k["up arrow"]) else 0.0
        brake = 1.0 if (k["s"] or k["down arrow"]) else 0.0
        steer = (1.0 if (k["d"] or k["right arrow"]) else 0.0) - (1.0 if (k["a"] or k["left arrow"]) else 0.0)
        return DriveInput(throttle, brake, steer, 1.0 if k["space"] else 0.0)

    def poll(self, dt) -> DriveInput:
        return self.smoother.update(self.raw(), dt)

    def reset(self):
        self.smoother.reset()
