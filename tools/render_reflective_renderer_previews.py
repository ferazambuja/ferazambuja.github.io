#!/usr/bin/env python3
"""Render portfolio previews from two already-retained native-state planes.

This tool changes only how the six logical states are visualized. It does not
rerun either renderer, alter a state plane, or predict measured panel output.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "site/reflective-color/assets"
WIDTH = 800
HEIGHT = 480
COMPARISON_SHA256 = "0ba7e1726fc5078cbd488fc922a0bcd8a435b27c9dfb7fa1f7e275ab53624c2e"
PLANE_INPUTS = {
    "pimoroni": (
        "pimoroni/state-plane.bin",
        "336c82d92fc449f679847669767515772aea3ac80feba9f90dc218d731eb7075",
        "renderer-v1-great-wave-pimoroni.png",
    ),
    "project-b": (
        "project-b/state-plane.bin",
        "eca2d492a82ee2c99a59e2d3df26a8619f3a04d20761ca5318c09cd89f5800fe",
        "renderer-v1-great-wave-project.png",
    ),
}

# Logical state order: black, white, yellow, red, blue, green. These are the
# measured-media-relative display colors already used by the ICC artwork
# previews, scaled so the measured panel white is shown as screen white.
MEDIA_RELATIVE_PALETTE = (
    (64, 39, 70),
    (255, 255, 255),
    (255, 255, 0),
    (202, 36, 33),
    (55, 123, 223),
    (87, 147, 113),
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render_state_plane(payload: bytes, *, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    if len(payload) != width * height:
        raise ValueError(f"state plane has {len(payload)} bytes; expected {width * height}")
    invalid = sorted(set(payload) - set(range(len(MEDIA_RELATIVE_PALETTE))))
    if invalid:
        raise ValueError(f"state plane contains unknown logical states: {invalid}")
    image = Image.new("RGB", (width, height))
    image.putdata([MEDIA_RELATIVE_PALETTE[state] for state in payload])
    return image


def png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()


def prepare(comparison_dir: Path) -> dict[Path, bytes]:
    comparison_path = comparison_dir / "comparison.json"
    comparison_bytes = comparison_path.read_bytes()
    if sha256(comparison_bytes) != COMPARISON_SHA256:
        raise ValueError("comparison.json differs from the retained renderer comparison")
    comparison = json.loads(comparison_bytes)
    prepared: dict[Path, bytes] = {}
    for route, (relative, expected_sha, filename) in PLANE_INPUTS.items():
        plane = (comparison_dir / relative).read_bytes()
        if sha256(plane) != expected_sha:
            raise ValueError(f"{route} state plane differs from the retained comparison")
        record = comparison["planes"][route]
        if record["width"] != WIDTH or record["height"] != HEIGHT:
            raise ValueError(f"{route} dimensions differ from the retained 800 × 480 comparison")
        if record["state_plane_sha256"] != expected_sha:
            raise ValueError(f"{route} comparison metadata does not bind the retained state plane")
        prepared[OUTPUT_DIR / filename] = png_bytes(render_state_plane(plane))
    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-dir", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="write the two reviewed portfolio previews")
    args = parser.parse_args()
    prepared = prepare(args.comparison_dir)
    if args.write:
        for path, payload in prepared.items():
            path.write_bytes(payload)
            print(f"wrote {path.relative_to(ROOT)} · {sha256(payload)}")
        return
    mismatches = [path for path, payload in prepared.items() if not path.is_file() or path.read_bytes() != payload]
    if mismatches:
        joined = ", ".join(str(path.relative_to(ROOT)) for path in mismatches)
        raise SystemExit(f"renderer previews differ: {joined}; review, then rerun with --write")
    print("Renderer previews match the retained state planes and shared measured palette.")


if __name__ == "__main__":
    main()
