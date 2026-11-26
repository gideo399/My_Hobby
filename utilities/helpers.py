"""Small math helpers shared by every module (pure Python, no engine imports)."""
import math


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def sign(v):
    return (v > 0) - (v < 0)


def smooth_sign(v, width):
    """Sign function with a linear ramp of +-width; avoids chatter around zero."""
    return clamp(v / width, -1.0, 1.0)


def approach(current, target, max_delta):
    if current < target:
        return min(current + max_delta, target)
    return max(current - max_delta, target)


def damp(dt, rate):
    """Frame-rate independent exponential smoothing factor: x += (t - x) * damp(dt, k)."""
    return 1.0 - math.exp(-rate * dt)


def wrap_angle(a):
    """Wrap to (-pi, pi]."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a


def lerp_angle(a, b, t):
    return a + wrap_angle(b - a) * t


def piecewise_linear(points, x):
    """points: sorted list of (x, y)."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def ms_to_kmh(v):
    return v * 3.6
