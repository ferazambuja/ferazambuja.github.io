#!/usr/bin/env python3
"""Refresh explicitly selected portfolio prose/UI, never measurement or image pins.

The public case study is now curated here. Its historical Learning export is
not a source to copy over these pages. Data/asset changes require a separately
reviewed delivery; this command refuses them rather than blessing new hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site/reflective-color"
EDITORIAL_FILES = (
    "index.html", "pattern-behavior/index.html", "prediction/index.html",
    "renderer/index.html", "icc/index.html",
    "story.css", "story.js", "shell.css", "fragment-routes.json",
)
# Exact, separately reviewed renderer-v1 delivery. These are not editable prose.
RENDERER_ASSET_PINS = {
    "assets/renderer-v1-great-wave-source.png": "6aeac27e820325e7c87ce4c80d0d42fe90b49024ab8eaa6cb6a75c4af258e300",
    "assets/renderer-v1-great-wave-pimoroni.png": "f2b081c274145d8ac434b2ca7539c6a4e5d49c848dcbca509cf69ed90dc78b03",
    "assets/renderer-v1-great-wave-project.png": "81a1b4e7df6bb1983c357bd215f306f6fe2164cc660a289656f53d7534e5450b",
    "assets/renderer-gallery/coffee-source.png": "0a90ff20220488705b6d11e25d83d33ea096d35a4da6294240e6b518541c7960",
    "assets/renderer-gallery/coffee-pimoroni.png": "447d9fcf39e29663d7adb738d9c5eff4a38486a923f9e4767c3705a633162df3",
    "assets/renderer-gallery/coffee-project.png": "449f9ce21f6b0d0527f104454187005cd9690b6ffdf2c07d8e27f0539cd33d86",
    "assets/renderer-gallery/chelsea-source.png": "81f4be215b20287ff8aebe7b73a540280d1511980073860ff22f6b0405651122",
    "assets/renderer-gallery/chelsea-pimoroni.png": "f72b8ab27907630e3e5ea56d4be46e02a55cc8aa4b1f043d39ea09d49ae82d60",
    "assets/renderer-gallery/chelsea-project.png": "a186b9dc0c7ffb4698e1be5db25da7d4a6afe4e487a4f013c9e9be26e28a2dbf",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source=SOURCE):
    manifest = json.loads((source / "snapshot.json").read_text())
    files = manifest["files"]
    for name, record in list(files.items()):
        # The public measurement explorer is retired; retain its source files
        # without copying its page, scripts or full experiment records.
        if name.startswith("measurements/") or name == "atlas-site.css":
            del files[name]
            continue
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError("snapshot path escapes the selected project")
        if (name not in EDITORIAL_FILES
                and name not in RENDERER_ASSET_PINS
                and digest(path) != record["sha256"]):
            raise ValueError(f"non-editorial delivery changed: {name}")
    for name in EDITORIAL_FILES:
        sha = digest(source / name)
        files[name] = {"sha256": sha, "source_sha256": sha}
    for name, sha in RENDERER_ASSET_PINS.items():
        if digest(source / name) != sha:
            raise ValueError(f"renderer asset differs from reviewed delivery: {name}")
        files[name] = {"sha256": sha, "source_sha256": sha}
    manifest["presentation_source"] = "portfolio-owned"
    return json.dumps(manifest, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="refresh only the explicit editorial allowlist")
    args = parser.parse_args()
    expected = prepare()
    path = SOURCE / "snapshot.json"
    if args.write:
        path.write_text(expected)
        print("Updated editorial hashes and reviewed renderer-preview pins; measurement pins unchanged.")
    elif path.read_text() != expected:
        raise SystemExit("Editorial snapshot differs. Review the changes, then use --write.")
    else:
        print("Reflective case-study snapshot is exact.")


if __name__ == "__main__":
    main()
