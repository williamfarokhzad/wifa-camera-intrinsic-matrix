"""Project camera-frame points through a cropped and resized pinhole image."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path


def number(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def integer(value: object, name: str, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True)
class Camera:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

    def __post_init__(self) -> None:
        for name in ("width", "height"):
            integer(getattr(self, name), name, 1)
        for name in ("fx", "fy", "cx", "cy"):
            value = number(getattr(self, name), name)
            if name in ("fx", "fy") and value <= 0:
                raise ValueError(f"{name} must be positive")

    def project(self, x: float, y: float, z: float) -> tuple[float, float]:
        x, y, z = (number(value, name) for value, name in zip((x, y, z), "XYZ"))
        if z <= 0:
            raise ValueError("Z must be positive in the camera frame")
        return (number(self.fx * (x / z) + self.cx, "u"),
                number(self.fy * (y / z) + self.cy, "v"))

    def contains(self, u: float, v: float) -> bool:
        # Pixel centers are integers; the outer image edges are half pixels.
        return -0.5 <= u < self.width - 0.5 and -0.5 <= v < self.height - 0.5


@dataclass(frozen=True)
class CropResize:
    left: int
    top: int
    width: int
    height: int
    out_width: int
    out_height: int
    mode: str

    def __post_init__(self) -> None:
        for name in ("left", "top"):
            integer(getattr(self, name), name, 0)
        for name in ("width", "height", "out_width", "out_height"):
            integer(getattr(self, name), name, 1)
        if self.mode not in ("asymmetric", "half_pixel"):
            raise ValueError("mode must be asymmetric or half_pixel")

    @property
    def scales(self) -> tuple[float, float]:
        return self.out_width / self.width, self.out_height / self.height

    def map_pixel(self, u: float, v: float) -> tuple[float, float]:
        sx, sy = self.scales
        center = 0.5 if self.mode == "half_pixel" else 0.0
        return ((u - self.left + center) * sx - center,
                (v - self.top + center) * sy - center)

    def update(self, camera: Camera) -> Camera:
        if self.left + self.width > camera.width or self.top + self.height > camera.height:
            raise ValueError("crop extends past the original image")
        sx, sy = self.scales
        cx, cy = self.map_pixel(camera.cx, camera.cy)
        return Camera(self.out_width, self.out_height, camera.fx * sx, camera.fy * sy, cx, cy)


def evaluate(case: dict) -> dict:
    if not isinstance(case, dict) or set(case) != {"camera", "image", "point_xyz"}:
        raise ValueError("case must contain camera, image, and point_xyz")
    original = Camera(**case["camera"])
    pipeline = CropResize(**case["image"])
    point = case["point_xyz"]
    if not isinstance(point, list) or len(point) != 3:
        raise ValueError("point_xyz must be a list of three coordinates")
    updated = pipeline.update(original)
    before = original.project(*point)
    after = updated.project(*point)
    # The stale projection reuses the original K on the same camera-frame point.
    return {"camera": updated, "before": before, "after": after,
            "inside": updated.contains(*after),
            "stale_error_px": math.dist(before, after)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="JSON input (see examples/)")
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.case.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        parser.error(str(exc))
    k = result["camera"]
    u0, v0 = result["before"]
    u1, v1 = result["after"]
    print(f"K': fx={k.fx:.3f} fy={k.fy:.3f} cx={k.cx:.3f} cy={k.cy:.3f}")
    print(f"original=({u0:.3f}, {v0:.3f}) output=({u1:.3f}, {v1:.3f})")
    print(f"inside_output={str(result['inside']).lower()} stale_K_error_px={result['stale_error_px']:.3f}")


if __name__ == "__main__":
    main()
