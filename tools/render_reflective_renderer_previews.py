#!/usr/bin/env python3
"""Render portfolio previews from already-retained native-state planes.

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
COMPLETION_SHA256 = "3c80e6c29ce813b0e891a934fee58508e95243c014f63daa2291684ad6e3b714"
ANALYSIS_SHA256 = "53f7f1704a5862f4adf05b761f7d4f87253aeaa046a876cc490a593ada400718"
GALLERY_CASES = ("coffee", "chelsea")
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


def read_bound(directory: Path, name: str, report: dict) -> bytes:
    payload = (directory / name).read_bytes()
    if report["files"][name] != {"bytes": len(payload), "sha256": sha256(payload)}:
        raise ValueError(f"retained file differs from its report: {name}")
    return payload


def prepare_gallery(completion_dir: Path, analysis_dir: Path) -> dict[Path, bytes]:
    """Visualize the same source and FS state planes used by the image comparison."""
    completion_raw = (completion_dir / "report.json").read_bytes()
    analysis_raw = (analysis_dir / "analysis.json").read_bytes()
    if sha256(completion_raw) != COMPLETION_SHA256 or sha256(analysis_raw) != ANALYSIS_SHA256:
        raise ValueError("gallery reports differ from the retained image comparison")
    completion, analysis = json.loads(completion_raw), json.loads(analysis_raw)
    prepared: dict[Path, bytes] = {}
    for case in GALLERY_CASES:
        prefix = f"image/{case}/serpentine_xyz/reference-hull"
        receipt = json.loads(read_bound(completion_dir, f"{prefix}/image-receipt.json", completion))
        source = Image.open(io.BytesIO(read_bound(completion_dir, f"inputs/{case}.png", completion)))
        if source.mode != "RGB" or source.size != (WIDTH, HEIGHT):
            raise ValueError(f"{case} interpreted source geometry differs")
        pixels = source.tobytes()
        if sha256(pixels) != receipt["source_interpretation"]["srgb_frame_sha256"]:
            raise ValueError(f"{case} source pixels differ from the renderer input")
        # These pixels are already interpreted sRGB. Rebuild the image without
        # inherited input metadata so browsers cannot apply a source ICC twice.
        prepared[OUTPUT_DIR / "renderer-gallery" / f"{case}-source.png"] = png_bytes(
            Image.frombytes("RGB", source.size, pixels)
        )
        routes = {
            "pimoroni": read_bound(analysis_dir, f"pimoroni/{case}/state-plane.bin", analysis),
            "project": read_bound(completion_dir, f"{prefix}/state-plane.bin", completion),
        }
        for route, plane in routes.items():
            prepared[OUTPUT_DIR / "renderer-gallery" / f"{case}-{route}.png"] = png_bytes(render_state_plane(plane))
    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-dir", type=Path, required=True)
    parser.add_argument("--gallery-completion-dir", type=Path)
    parser.add_argument("--gallery-analysis-dir", type=Path)
    parser.add_argument("--write", action="store_true", help="write the selected portfolio previews")
    args = parser.parse_args()
    if bool(args.gallery_completion_dir) != bool(args.gallery_analysis_dir):
        parser.error("gallery completion and analysis directories must be supplied together")
    prepared = prepare(args.comparison_dir)
    if args.gallery_completion_dir:
        prepared.update(prepare_gallery(args.gallery_completion_dir, args.gallery_analysis_dir))
    if args.write:
        for path, payload in prepared.items():
            if path.is_file() and path.read_bytes() == payload:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
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
