#!/usr/bin/env python3
"""Focused delivery checks for the reflective-display case study."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from urllib.parse import urljoin, urlparse

from build_site import REFLECTIVE_ROUTE, build_reflective_color, sitemap, topbar

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site/reflective-color"


class ReflectiveDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        (cls.output / "assets").mkdir()
        build_reflective_color(ROOT / "site", cls.output)
        cls.project = cls.output / REFLECTIVE_ROUTE.strip("/")
        cls.article = (cls.project / "index.html").read_text()
        cls.atlas = (cls.project / "measurements/index.html").read_text()
        cls.manifest = json.loads((SOURCE / "snapshot.json").read_text())["files"]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_selected_payloads_are_exact(self):
        for name, record in self.manifest.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(), record["sha256"])
                if not name.endswith(".html"):
                    self.assertEqual((SOURCE / name).read_bytes(), (self.project / name).read_bytes())
                if name.endswith((".json", ".png")):
                    self.assertEqual(record["sha256"], record["source_sha256"])

    def test_only_selected_delivery_files_are_published(self):
        self.assertEqual({p.relative_to(self.project).as_posix() for p in self.project.rglob("*") if p.is_file()}, set(self.manifest))
        self.assertNotIn("snapshot.json", {p.name for p in self.project.rglob("*")})

    def test_story_keeps_semantic_sections_and_visuals(self):
        for anchor in ("display-primer-title", "first-icc", "featured-measurement", "metric-comparison", "native-width-overview", "prediction-result", "prediction-return-status", "image-context-result", "prediction-transfer", "all-pair-explorer"):
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', self.article)
        self.assertIn("<noscript>", self.article)
        self.assertIn("function showDataFailure()", self.article)
        self.assertIn("function forwardAtlasSelection()", self.article)
        self.assertIn('new URLSearchParams(location.search)', self.article)

    def test_single_document_landmarks_and_current_navigation(self):
        for text in (self.article, self.atlas):
            self.assertEqual(len(re.findall(r"<main\b", text)), 1)
            self.assertEqual(len(re.findall(r"<h1\b", text)), 1)
            self.assertEqual(text.count('rel="canonical"'), 1)
            self.assertEqual(text.count('aria-current="page"'), 1)
        self.assertIn('aria-current="location"', self.atlas)

    def test_topbar_does_not_depend_on_project_styles(self):
        for route, key in (("/", "home"), ("/imaging/", "imaging"), ("/hdr-platform/", "hdr"), (REFLECTIVE_ROUTE, "reflective")):
            self.assertEqual(topbar(route, key).count('aria-current="page"'), 1)
            self.assertIn(f'href="{REFLECTIVE_ROUTE}"', topbar(route, key))
        self.assertNotIn('href="/assets/site.css"', self.article)
        self.assertIn('href="/assets/reflective-shell.css"', self.article)

    def test_fetches_resolve_without_external_data_services(self):
        positive = 'fetch("/example.json")'
        detector = re.compile(r"fetch\(['\"]([^'\"]+)['\"]\)")
        self.assertEqual(detector.findall(positive), ["/example.json"])
        for path in self.project.rglob("*"):
            if path.suffix not in {".html", ".js"}:
                continue
            base = "https://portfolio.example/" + path.relative_to(self.output).as_posix()
            for url in detector.findall(path.read_text()):
                with self.subTest(file=path.name, url=url):
                    resolved = urlparse(urljoin(base, url))
                    self.assertEqual(resolved.netloc, "portfolio.example")
                    self.assertTrue((self.output / resolved.path.lstrip("/")).is_file())

    def test_all_existing_experiment_choices_stay_available(self):
        data = json.loads((self.project / "measurements/atlas-experiments.json").read_text())
        ids = [e["id"] for e in data["experiments"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({"unseen-images-local12", "return-stability39", "center-context8", "coverage39-complete"}.issubset(ids))
        self.assertIn("atlas-family", self.atlas)
        self.assertIn("atlas-experiment", self.atlas)
        self.assertIn("atlas-reading-pattern", self.atlas)

    def test_photographs_contain_no_exif_xmp_or_iptc(self):
        for path in (self.project / "assets").glob("*.jpeg"):
            payload = path.read_bytes()
            position = 2
            self.assertTrue(payload.startswith(b"\xff\xd8"))
            while position < len(payload):
                self.assertEqual(payload[position], 255)
                while payload[position] == 255:
                    position += 1
                marker = payload[position]
                position += 1
                if marker == 0xDA:
                    break
                self.assertNotIn(marker, {0xE1, 0xED, 0xFE})
                position += int.from_bytes(payload[position:position + 2], "big")
            else:
                self.fail("photograph has no compressed image data")

    def test_local_candidate_stays_out_of_sitemap(self):
        self.assertIn('content="noindex,nofollow"', self.article)
        self.assertNotIn(REFLECTIVE_ROUTE, sitemap(self.output))

    def test_modified_delivery_fails_before_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(SOURCE, root / "site/reflective-color")
            (root / "site/reflective-color/measurement-investigation.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "selected project file changed"):
                build_reflective_color(root / "site", root / "output")
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
