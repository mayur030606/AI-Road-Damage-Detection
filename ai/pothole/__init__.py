"""
Pothole detection module package.
"""

__all__ = ["PotholeDetector"]


def __getattr__(name):
    if name == "PotholeDetector":
        from ai.pothole.detector import PotholeDetector
        return PotholeDetector
    raise AttributeError(name)
