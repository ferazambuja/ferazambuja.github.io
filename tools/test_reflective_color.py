#!/usr/bin/env python3
"""Focused delivery checks for the reflective-display case study."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urljoin, urlparse

from build_site import (
    REFLECTIVE_ROUTE,
    SITE_URL,
    build_reflective_color,
    reflective_feature,
    sitemap,
    topbar,
)
from render_reflective_renderer_previews import MEDIA_RELATIVE_PALETTE, render_state_plane
from refresh_reflective_snapshot import EDITORIAL_FILES, RENDERER_ASSET_PINS, prepare as prepare_snapshot
from serve_site import PreviewHTTPServer, create_preview_server

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site/reflective-color"
NARRATIVE_PAGES = (
    "index.html",
    "pattern-behavior/index.html",
    "prediction/index.html",
    "renderer/index.html",
    "icc/index.html",
)
CASE_STUDY_PAGES = (*NARRATIVE_PAGES, "measurements/index.html")


class PageStructure(HTMLParser):
    """Read actual markup, excluding tag-like text inside script strings."""

    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.links = []
        self.id_references = []
        self.tags = {}
        self.meta = {}
        self.canonicals = []
        self.navs = []
        self.nav_stack = []
        self.details_depth = 0
        self.max_details_depth = 0
        self.in_title = False
        self.title = ""
        self.focusable = []
        self.skip_links = []
        self.mains = []
        self.in_main = False
        self.case_nav_in_main = False
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "main":
            self.mains.append(attrs)
            self.in_main = True
        if tag == "nav" and "case-nav" in attrs.get("class", "").split():
            self.case_nav_in_main = self.in_main
        if tag == "a" and "skip-link" in attrs.get("class", "").split():
            self.skip_links.append(attrs)
        if ((tag == "a" and "href" in attrs)
                or tag in {"button", "select", "textarea", "summary"}
                or (tag == "input" and attrs.get("type") != "hidden")
                or ("tabindex" in attrs and int(attrs["tabindex"]) >= 0)):
            self.focusable.append(attrs)
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("aria-labelledby", "aria-describedby", "aria-controls"):
            self.id_references.extend(attrs.get(key, "").split())
        if tag == "meta":
            key = attrs.get("name", attrs.get("property"))
            self.meta.setdefault(key, []).append(attrs.get("content", ""))
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if tag == "nav":
            self.nav_stack.append([])
        if tag in {"a", "link", "script", "img"}:
            for key in ("href", "src"):
                if key in attrs:
                    self.links.append(attrs[key])
                    if tag == "a" and self.nav_stack:
                        self.nav_stack[-1].append(attrs[key])
        if tag == "details":
            self.details_depth += 1
            self.max_details_depth = max(self.details_depth, self.max_details_depth)
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
        if tag == "details":
            self.details_depth -= 1
        elif tag == "nav" and self.nav_stack:
            self.navs.append(self.nav_stack.pop())
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


class ReflectiveDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        (cls.output / "assets").mkdir()
        cls.page_count = build_reflective_color(ROOT / "site", cls.output)
        cls.project = cls.output / REFLECTIVE_ROUTE.strip("/")
        cls.pages = {name: (cls.project / name).read_text() for name in CASE_STUDY_PAGES}
        cls.structures = {name: PageStructure(text) for name, text in cls.pages.items()}
        cls.article = (cls.project / "index.html").read_text()
        cls.atlas = (cls.project / "measurements/index.html").read_text()
        cls.narrative = "\n".join(cls.pages[name] for name in NARRATIVE_PAGES)
        cls.scripts = "\n".join(path.read_text() for path in cls.project.rglob("*.js"))
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
                if name.endswith(".png") or name in {
                    "measurement-investigation.json", "measurements/atlas-experiments.json"
                }:
                    self.assertEqual(record["sha256"], record["source_sha256"])

    def test_only_selected_delivery_files_are_published(self):
        self.assertEqual({p.relative_to(self.project).as_posix() for p in self.project.rglob("*") if p.is_file()}, set(self.manifest))
        self.assertNotIn("snapshot.json", {p.name for p in self.project.rglob("*")})

    def test_story_keeps_semantic_sections_and_visuals(self):
        for anchor in ("display-primer-title", "first-icc", "featured-measurement", "prediction-result", "measured-prediction-example", "all-pair-explorer"):
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', self.article)
        for anchor in ("metric-comparison", "native-width-overview", "prediction-return-status", "image-context-result", "prediction-transfer"):
            with self.subTest(detail_anchor=anchor):
                self.assertIn(f'id="{anchor}"', self.narrative)
        self.assertIn("<noscript>", self.article)
        self.assertIn("function showDataFailure(readerState)", self.scripts)
        self.assertIn("function forwardAtlasSelection()", self.scripts)
        self.assertIn('new URLSearchParams(location.search)', self.scripts)
        self.assertIn("function captureReaderState()", self.scripts)
        self.assertIn("function realignHashAfterDynamicContent(readerState)", self.scripts)
        self.assertEqual(self.scripts.count("realignHashAfterDynamicContent(readerState);"), 2)
        self.assertIn("function recordHashLanding(", self.scripts)
        self.assertIn("Math.abs(readerState.y-landing.y)>2", self.scripts)
        self.assertIn("readerState.focus!==landing.focus", self.scripts)
        self.assertIn("document.activeElement!==readerState.focus", self.scripts)
        self.assertNotIn("HASH_SCROLL_KEYS", self.scripts)

    def test_result_visuals_and_prediction_map_are_grounded(self):
        self.assertIn('id="measured-prediction-example"', self.article)
        self.assertIn(
            'data-result-sha256="224085c999428cd9476bebee02e764881a40f323910ff2f168eefd2a3d59a748"',
            self.article,
        )
        self.assertIn('data-source-id="RENDERER-BC-WARM-LIGHT-C"', self.article)
        for xyz in (
            "16.48454729033974,15.564632033519056,7.727523807314165",
            "14.10692773053848,12.416873903444351,5.240211235593386",
            "14.29114,12.57847,5.426062",
        ):
            self.assertIn(f'data-xyz-d50="{xyz}"', self.article)
        self.assertGreaterEqual(self.narrative.count("data-fresh-reading="), 4)
        for result in ("ΔE00 0.41", "ΔE00 5.96", "0.38–0.47", "5.81–5.96"):
            self.assertIn(result, self.article)
        for fabricated in ("--example-color", "#d5b849", "#647e79", "#687e77", "Conceptual illustration"):
            self.assertNotIn(fabricated, self.article)

        patterns = self.pages["pattern-behavior/index.html"]
        self.assertIn('id="prediction-domain-map"', patterns)
        for domain in (
            "equal-count-stripes",
            "two-color-layout",
            "three-color-arrangement",
            "error-diffused-organization",
            "patterned-extent",
            "image-region-context",
            "return-condition",
        ):
            self.assertIn(f'data-prediction-domain="{domain}"', patterns)
        for anchor in ("pattern-findings", "renderer-check", "instrument-check", "patterns-to-prediction"):
            self.assertIn(f'id="{anchor}"', self.narrative)
        self.assertIn('id="unchanged-pattern-returns"', patterns)
        self.assertIn("comparison=return-stability39&amp;pattern=FIXED-RENDERER-NEXT-COVERAGE39-B-PALE-RED-LIGHT", patterns)
        for identifier in ("pair-comparison-table", "other-constructions"):
            self.assertIn(f'id="{identifier}"', patterns)
        for scope in ('data-scope-unit="native-pairs" data-count="15"',
                      'data-scope-unit="native-patterns" data-count="90"',
                      'data-scope-unit="optical-readings" data-count="300"'):
            self.assertIn(scope, patterns)
        questions = re.findall(r'data-construction-result="([^"]+)"', patterns)
        self.assertEqual(len(questions), len(set(questions)))
        self.assertIn(f'data-scope-unit="construction-questions" data-count="{len(questions)}"', patterns)
        self.assertTrue({"organization", "extent"}.issubset(questions))
        self.assertIn('src="/reflective-color-display/assets/cypresses-image.png"', patterns)
        self.assertIn('src="/reflective-color-display/assets/cypresses-control.png"', patterns)

    def test_q3_comparison_and_consolidated_image_example_survive_delivery(self):
        prediction = self.pages["prediction/index.html"]
        self.assertIn('id="fixed-adjustment-example"', prediction)
        for case in ("warm-light", "neutral128"):
            self.assertIn(f'data-correction-case="{case}"', prediction)
        self.assertIn('href="/reflective-color-display/measurements/?experiment=bcd&amp;comparison=bcd"', prediction)
        patterns = self.pages["pattern-behavior/index.html"]
        self.assertEqual(patterns.count('id="context-pixel-examples"'), 1)
        for filename in ("cypresses-image.png", "cypresses-control.png"):
            self.assertEqual(patterns.count(f'src="/reflective-color-display/assets/{filename}"'), 1)
        self.assertIn('href="/reflective-color-display/measurements/?experiment=center-context8&amp;comparison=CYPRESSES_IMAGE_MINUS_CONTROL"', patterns)

    def test_icc_grid_identifies_the_renderer_at_the_result(self):
        # A reader may arrive at this result directly, bypassing the introduction.
        grid = re.search(
            r'<div\b[^>]*aria-labelledby="color-grid-title"[^>]*>(.*?)</div>',
            self.pages["icc/index.html"], re.S,
        ).group(1)
        rows = re.findall(
            r'<tr data-grid-route="([^"]+)"><th[^>]*>(.*?)</th>'
            r'<td>(.*?)</td><td>(.*?)</td></tr>', grid, re.S,
        )
        self.assertEqual(
            {key: (label, mean, largest) for key, label, mean, largest in rows},
            {
                "stock": ("Pimoroni renderer", "19.9922", "42.1941"),
                "sparse": ("Sparse ICC + Pimoroni renderer", "12.2568", "26.4508"),
                "dense": ("Dense ICC + Pimoroni renderer", "11.2006", "23.7069"),
            },
        )
        grid_text = " ".join(re.sub(r"<[^>]+>", " ", grid).split())
        self.assertRegex(grid_text, r"133-color comparison (?:did|does) not evaluate the project renderer")

    def test_skip_link_precedes_navigation_and_targets_focusable_content(self):
        for name, structure in self.structures.items():
            with self.subTest(page=name):
                self.assertEqual(len(structure.skip_links), 1)
                skip = structure.skip_links[0]
                self.assertEqual(structure.focusable[0], skip)
                self.assertEqual(skip["href"], "#main-content")
                self.assertEqual(len(structure.mains), 1)
                self.assertEqual(structure.mains[0].get("id"), "main-content")
                self.assertEqual(structure.mains[0].get("tabindex"), "-1")
                self.assertFalse(structure.case_nav_in_main)

    def test_single_document_landmarks_and_current_navigation(self):
        routes = {REFLECTIVE_ROUTE + name.removesuffix("index.html") for name in CASE_STUDY_PAGES}
        titles = set()
        descriptions = set()
        for name, text in self.pages.items():
            with self.subTest(page=name):
                structure = self.structures[name]
                route = REFLECTIVE_ROUTE + name.removesuffix("index.html")
                self.assertEqual(structure.tags.get("main"), 1)
                self.assertEqual(structure.tags.get("h1"), 1)
                self.assertEqual(structure.tags.get("title"), 1)
                self.assertTrue(structure.title.strip())
                self.assertEqual(len(structure.ids), len(set(structure.ids)), "duplicate HTML IDs")
                self.assertEqual(structure.canonicals, [SITE_URL + route])
                self.assertEqual(structure.meta.get("og:url"), [SITE_URL + route])
                self.assertEqual(structure.meta.get("og:title"), [structure.title])
                self.assertEqual(len(structure.meta.get("description", [])), 1)
                self.assertTrue(structure.meta["description"][0].strip())
                self.assertEqual(len(structure.meta.get("og:description", [])), 1)
                self.assertTrue(structure.meta["og:description"][0].strip())
                self.assertEqual(text.count('aria-current="page"'), 1)
                self.assertTrue(any(routes.issubset(set(nav)) for nav in structure.navs), "local navigation must expose every topic")
                self.assertLessEqual(structure.max_details_depth, 1, "nested disclosures obscure related explanation")
                self.assertEqual(structure.details_depth, 0, "unclosed disclosure")
                titles.add(structure.title)
                descriptions.add(structure.meta["description"][0])
        self.assertEqual(len(titles), len(self.pages), "topic titles must identify their page")
        self.assertEqual(len(descriptions), len(self.pages), "descriptions must identify their topic")
        self.assertEqual(self.page_count, len(self.pages))

    def test_renderer_result_uses_the_settled_assets_and_software_scope(self):
        comparison_sha = "0ba7e1726fc5078cbd488fc922a0bcd8a435b27c9dfb7fa1f7e275ab53624c2e"
        report_sha = "3c80e6c29ce813b0e891a934fee58508e95243c014f63daa2291684ad6e3b714"
        for name in ("index.html", "renderer/index.html"):
            with self.subTest(page=name):
                page = self.pages[name]
                self.assertIn(f'data-comparison-sha256="{comparison_sha}"', page)
                self.assertIn(f'data-report-sha256="{report_sha}"', page)
                for asset, sha in RENDERER_ASSET_PINS.items():
                    self.assertIn(f'src="{REFLECTIVE_ROUTE}{asset}"', page)
                    self.assertEqual(hashlib.sha256((self.project / asset).read_bytes()).hexdigest(), sha)
                self.assertIn('href="https://www.metmuseum.org/art/collection/search/45434"', page)
                text = " ".join(re.sub(r"<[^>]+>", " ", page).split())
                for boundary in ("not panel photographs", "measured native-state colors used for the ICC artwork previews",
                                 "only for comparing pixel choices",
                                 "not the renderer's endpoint-reference table",
                                 "same interpreted, fitted source", "not Pimoroni's untouched image-intake workflow"):
                    self.assertIn(boundary, text)
                self.assertIn("Katsushika Hokusai", text)
        # Readers should encounter the working renderer before the detailed
        # prediction example, while the metric table stays on the deeper page.
        self.assertLess(self.article.index('id="renderer-result"'),
                        self.article.index('id="prediction-result"'))
        self.assertNotIn('id="renderer-decision-table"', self.article)
        renderer = self.pages["renderer/index.html"]
        rows = re.findall(r'<tr data-renderer-kernel="([^"]+)"><th[^>]*>.*?</th><td>(.*?)</td><td>(.*?)</td></tr>', renderer)
        self.assertEqual(dict((key, (baseline, candidate)) for key, baseline, candidate in rows), {
            "serpentine_xyz": ("11.134", "11.243"),
            "serpentine_jjn_xyz": ("11.119", "11.329"),
        })
        self.assertIn("114 software conditions", renderer)
        self.assertIn("not measured screen errors", renderer)
        self.assertIn("not an unseen validation set", renderer)

    def test_renderer_previews_share_one_measured_visualization_palette(self):
        from PIL import Image

        expected = set(MEDIA_RELATIVE_PALETTE)
        for name in (
            "assets/renderer-v1-great-wave-pimoroni.png",
            "assets/renderer-v1-great-wave-project.png",
        ):
            with self.subTest(asset=name):
                image = Image.open(SOURCE / name).convert("RGB")
                colors = {color for _, color in image.getcolors(maxcolors=image.width * image.height)}
                self.assertEqual(colors, expected)

        synthetic = render_state_plane(bytes(range(6)), width=6, height=1)
        self.assertEqual(list(synthetic.get_flattened_data()), list(MEDIA_RELATIVE_PALETTE))

    def test_pale_red_return_is_presented_as_the_stable_counterexample(self):
        patterns = self.pages["pattern-behavior/index.html"]
        for page in (self.article, patterns):
            with self.subTest(page="overview" if page is self.article else "patterns"):
                self.assertIn("within 0.21 ΔE00", page)
                self.assertIn("Not every pattern showed a large return effect", page)
                self.assertNotIn("did not return to one fixed value", page)
                self.assertNotIn("Absolute color changed across returns", page)

    def test_history_results_are_quantified_without_claiming_a_cause(self):
        patterns = self.pages["pattern-behavior/index.html"]
        prediction = self.pages["prediction/index.html"]

        self.assertIn("0.31–0.60 ΔE00", patterns)
        self.assertIn("0.078–0.092 ΔE00", patterns)
        self.assertEqual(patterns.count("0.31–0.60 ΔE00"), 1)
        self.assertIn("0.78–1.15 ΔE00 after redraw versus 0.12–0.21 while held", patterns)
        self.assertIn("0.29–0.30 ΔE00 while held versus 0.09–0.16 after redraw", patterns)
        self.assertIn("neither waiting nor redrawing acted as a universal reset", patterns)
        self.assertIn("Each hold waited for the recorded duration of the preceding display update", patterns)
        self.assertIn("a practical timing match, not an identical history", patterns)
        self.assertIn("In 20 of 22 refresh-versus-hold comparisons using the same preceding image", patterns)
        self.assertIn("the two reading intervals differed by no more than 0.20 seconds", patterns)
        self.assertIn("After red/blue stripes, the redraw interval was about 1.71 seconds longer", patterns)
        self.assertIn("after white, the hold interval was 1.80 seconds longer", patterns)
        self.assertIn("following the alignment image, was closely time-matched", patterns)
        self.assertIn("Each episode was observed once", patterns)
        self.assertIn("does not identify a universal history rule or a physical cause", patterns)
        self.assertIn("1.44 and 1.56 ΔE00", prediction)
        self.assertIn("0.19–0.26 ΔE00", prediction)
        self.assertIn("six familiar patterns", prediction)
        self.assertIn("later-session means", prediction)
        self.assertIn("the other four patterns were 0.32–0.99 ΔE00 away", prediction)
        self.assertIn("maximum pairwise separation among the cyan maps' six later-session readings", prediction)
        self.assertIn("occurrence sensitivity without identifying its cause", prediction)
        self.assertIn("A separate comparison repeated six familiar patterns", patterns)
        self.assertIn("1.44 and 1.56 ΔE00", patterns)
        self.assertIn("the other four differed by 0.32–0.99 ΔE00", patterns)
        self.assertIn('href="/reflective-color-display/prediction/#prediction-return-status"', patterns)

        overview_start = self.article.index('<section class="story-chapter" id="other-constructions">')
        overview_end = self.article.index('<section class="story-chapter" id="renderer-result">')
        overview = self.article[overview_start:overview_end]
        self.assertIn("Other identical pixel maps did move", overview)
        self.assertIn("blue/green stripes changed by 0.31–0.60 ΔE00 after redraw", overview)
        self.assertIn("black/yellow stripes changed by 0.29–0.30 while held", overview)
        self.assertIn("two near-neutral cyan maps differed from their earlier-session means by 1.44–1.56 ΔE00", overview)
        self.assertIn('href="/reflective-color-display/pattern-behavior/#unchanged-pattern-returns"', overview)
        for overclaim in (
            "presentation history changed readings",
            "presentation history all produced useful comparisons",
            "Holding an image and drawing it again gave different answers",
            "did not return consistent colors across occurrences",
        ):
            with self.subTest(overclaim=overclaim):
                self.assertNotIn(overclaim, self.article + patterns + prediction)

    def test_renderer_copy_separates_image_mean_from_individual_guards(self):
        renderer = self.pages["renderer/index.html"]
        self.assertIn("worsened the equal-weighted mean across the eight development images", renderer)
        self.assertIn("Across the broader 114-condition comparison", renderer)
        self.assertIn("a flat dark-gray field rose from 8.11 to 14.73 ΔE00", renderer)
        self.assertIn("several tone and detail checks worsened", renderer)

    def test_renderer_preview_palette_and_icc_color_terms_are_explicit(self):
        caption = (
            "the measured native-state colors used for the ICC artwork previews, "
            "scaled so the panel's white appears white"
        )
        self.assertIn(caption, self.article)
        self.assertIn(caption, self.pages["renderer/index.html"])
        self.assertIn("not the renderer's endpoint-reference table", self.article)
        self.assertIn("measured native-state colors", self.pages["icc/index.html"])
        self.assertNotIn("measured native-state chromaticities", self.pages["icc/index.html"])

    def test_prediction_summary_interprets_the_average_without_repeating_the_pass_count(self):
        prediction = self.pages["prediction/index.html"]
        match = re.search(r'<div data-question-part="meaning"><dt>What it tells us</dt><dd>(.*?)</dd></div>', prediction)
        self.assertIsNotNone(match)
        meaning = match.group(1)
        self.assertIn("helped on average", meaning)
        self.assertIn("did not translate into reliable predictions for individual readings", meaning)
        self.assertNotIn("2 of 28", meaning)

    def test_color_science_conventions_are_named_where_results_appear(self):
        self.assertIn("nominal perfect-diffuser D50", self.article)
        self.assertIn("panel white as its reference", self.article)
        self.assertIn("percentage points of reflectance factor", self.article)
        self.assertIn("1-pixel-wide black/yellow stripes", self.article)
        self.assertIn("two target colors, a warm tone and a neutral gray", self.article)

        renderer = self.pages["renderer/index.html"]
        self.assertIn("complete 16 × 16 source-image tiles", renderer)
        self.assertIn("not comparable with the 11.20 measured on the ICC grid", renderer)
        self.assertIn("packed file the display controller accepts", renderer)
        self.assertIn("The implementation is currently in a private development repository", renderer)

        prediction = self.pages["prediction/index.html"]
        self.assertIn("Alternative renderings of two target colors", prediction)
        self.assertIn("Desired colors are image colors scaled to the panel's measured white", prediction)

    def test_public_copy_avoids_internal_workflow_language_and_completes_credits(self):
        readme = (SOURCE / "README.md").read_text()
        private_home_fragment = "/" + "Users" + "/"
        for leak in (private_home_fragment, "Do not push", "source commit"):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, readme)
        self.assertNotRegex(readme.lower(), r"\bhandoff(?:s|ed|ing)?\b")

        for name in NARRATIVE_PAGES:
            page = self.pages[name]
            for alt in re.findall(r'\balt="([^"]*)"', page):
                with self.subTest(page=name, alt=alt):
                    self.assertNotRegex(alt.lower(), r"\b(retained|pinned|frozen)\b")

        combined = self.article + self.pages["icc/index.html"] + self.pages["pattern-behavior/index.html"]
        self.assertIn("Vincent van Gogh", combined)
        self.assertIn("Rogers Fund, 1949", combined)
        self.assertIn("Helen Birch Bartlett Memorial Collection", combined)
        self.assertGreaterEqual(combined.count("Public domain"), 3)

    def test_preview_server_handles_parallel_browser_asset_requests(self):
        with create_preview_server(SOURCE, port=0, quiet=True) as server:
            self.assertIsInstance(server, PreviewHTTPServer)
            self.assertGreaterEqual(server.request_queue_size, 128)
            self.assertTrue(server.daemon_threads)

    def test_heading_repairs_and_home_card_keep_the_reader_facing_story(self):
        patterns = self.pages["pattern-behavior/index.html"]
        self.assertNotIn("<h4>How each reading stays connected to its pixels</h4>", patterns)
        self.assertNotIn("<h4>Why waiting, redrawing, and changing the previous image are separate tests</h4>", patterns)
        card = " ".join(re.sub(r"<[^>]+>", " ", reflective_feature()).split())
        for result in ("133-color", "pixel arrangement", "offline renderer"):
            self.assertIn(result, card)

    def test_markup_detector_distinguishes_script_text_and_nested_disclosures(self):
        parsed = PageStructure(
            '<main id="real-anchor" data-source-id="not-an-anchor" '
            'data-comparison-id="not-an-anchor-either"><h1>Example</h1>'
            '<script>const x="<h1 id=\'script-text\'>not markup</h1>"</script>'
            '<details><details></details></details></main>'
        )
        self.assertEqual(parsed.tags["h1"], 1)
        self.assertEqual(parsed.max_details_depth, 2)
        self.assertEqual(parsed.ids, ["real-anchor"])

    def test_topic_links_assets_and_accessible_labels_resolve(self):
        for name, structure in self.structures.items():
            with self.subTest(page=name):
                self.assertTrue(set(structure.id_references).issubset(set(structure.ids)),
                                f"missing label/control targets: {set(structure.id_references) - set(structure.ids)}")
            base = SITE_URL + REFLECTIVE_ROUTE + name
            for link in structure.links:
                resolved = urlparse(urljoin(base, link))
                if resolved.netloc != urlparse(SITE_URL).netloc or not resolved.path.startswith(REFLECTIVE_ROUTE):
                    continue
                with self.subTest(page=name, link=link):
                    relative = unquote(resolved.path.removeprefix(REFLECTIVE_ROUTE))
                    if not relative or relative.endswith("/"):
                        relative += "index.html"
                    self.assertTrue((self.project / relative).is_file(), "missing selected project file")
                    if resolved.fragment and relative.endswith(".html"):
                        self.assertIn(unquote(resolved.fragment), self.structures[relative].ids,
                                      "fragment target is missing from destination page")

    def test_legacy_fragments_route_to_preserved_content(self):
        mapping = json.loads((self.project / "fragment-routes.json").read_text())
        self.assertTrue(mapping)
        self.assertIn("fragment-routes.json", self.scripts)
        for anchor, target in mapping.items():
            with self.subTest(anchor=anchor, target=target):
                resolved = urlparse(urljoin(SITE_URL + REFLECTIVE_ROUTE, target))
                self.assertEqual(resolved.scheme, urlparse(SITE_URL).scheme)
                self.assertEqual(resolved.netloc, urlparse(SITE_URL).netloc)
                self.assertTrue(resolved.path.startswith(REFLECTIVE_ROUTE))
                relative = unquote(resolved.path.removeprefix(REFLECTIVE_ROUTE))
                if not relative or relative.endswith("/"):
                    relative += "index.html"
                self.assertIn(relative, self.structures)
                # Editorial consolidation may intentionally send an old ID to
                # a new section or the topic's introduction, not a namesake ID.
                if resolved.fragment:
                    self.assertIn(unquote(resolved.fragment), self.structures[relative].ids)

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
        returns = next(e for e in data["experiments"] if e["id"] == "return-stability39")
        self.assertIn(
            "Patterns were selected using earlier results, so this was not a test on new inputs "
            "and does not demonstrate a general learning curve.", returns["condition"])

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

    def test_public_case_study_is_indexable_while_atlas_stays_unlisted(self):
        self.assertIn('content="noindex,nofollow"', self.atlas)
        site_map = sitemap(self.output)
        for name in NARRATIVE_PAGES:
            with self.subTest(page=name):
                self.assertNotIn('content="noindex', self.pages[name])
                route = REFLECTIVE_ROUTE + name.removesuffix("index.html")
                self.assertIn(f"<loc>{SITE_URL}{route}</loc>", site_map)
        self.assertNotIn(f"{REFLECTIVE_ROUTE}measurements/", site_map)

    def test_modified_delivery_fails_before_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(SOURCE, root / "site/reflective-color")
            (root / "site/reflective-color/measurement-investigation.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "selected project file changed"):
                build_reflective_color(root / "site", root / "output")
            self.assertFalse((root / "output").exists())


class ReflectiveRouteBuilderTests(unittest.TestCase):
    def test_actual_page_count_and_route_metadata(self):
        # A small synthetic delivery checks the builder independently of the
        # current six-page inventory. Neither a constant two nor six is valid.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "site/reflective-color"
            files = {}
            for name in ("index.html", "renderer/index.html", "example.html"):
                selected = source / name
                selected.parent.mkdir(parents=True, exist_ok=True)
                selected.write_text(
                    '<!doctype html><html><head><title>Example</title>'
                    '<link rel="canonical" href="https://old.example/">'
                    '<meta property="og:url" content="https://old.example/">'
                    '</head><body><main><h1>Example</h1></main></body></html>'
                )
                files[name] = {"sha256": hashlib.sha256(selected.read_bytes()).hexdigest()}
            (source / "shell.css").write_text(":root{}")
            (source / "snapshot.json").write_text(json.dumps({"files": files}))
            count = build_reflective_color(root / "site", root / "output")
            self.assertEqual(count, 3)
            for name in files:
                with self.subTest(page=name):
                    delivered = PageStructure((root / "output" / REFLECTIVE_ROUTE.strip("/") / name).read_text())
                    route = REFLECTIVE_ROUTE + name.removesuffix("index.html")
                    self.assertEqual(delivered.canonicals, [SITE_URL + route])
                    self.assertEqual(delivered.meta["og:url"], delivered.canonicals)


class ReflectiveSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        self.pinned = {
            "measurement-investigation.json": b'{"retained":true}',
            "measurements/atlas-experiments.json": b'{"experiments":[]}',
            "assets/measurement.png": b"retained-image-payload",
        }
        self.pinned.update({name: (SOURCE / name).read_bytes() for name in RENDERER_ASSET_PINS})
        files = {}
        for name, payload in self.pinned.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            sha = hashlib.sha256(payload).hexdigest()
            files[name] = {"sha256": sha, "source_sha256": sha}
        for name in EDITORIAL_FILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Revised editorial content")
        self.manifest = {"files": files}
        self.snapshot = self.source / "snapshot.json"
        self.snapshot.write_text(json.dumps(self.manifest))
        self.original_snapshot = self.snapshot.read_bytes()

    def test_editorial_refresh_preserves_measurement_and_image_pins(self):
        prepared = json.loads(prepare_snapshot(self.source))
        self.assertEqual(prepared["presentation_source"], "portfolio-owned")
        for name in EDITORIAL_FILES:
            with self.subTest(editorial=name):
                self.assertEqual(prepared["files"][name]["sha256"],
                                 hashlib.sha256((self.source / name).read_bytes()).hexdigest())
        for name, payload in self.pinned.items():
            with self.subTest(retained=name):
                self.assertEqual(prepared["files"][name], self.manifest["files"][name])
                self.assertEqual((self.source / name).read_bytes(), payload)
        self.assertEqual(self.snapshot.read_bytes(), self.original_snapshot)

    def test_editorial_refresh_refuses_changed_measurements_and_images(self):
        for name, payload in self.pinned.items():
            with self.subTest(file=name):
                path = self.source / name
                path.write_bytes(payload + b"changed")
                if name in RENDERER_ASSET_PINS:
                    expected = f"renderer asset differs from reviewed delivery: {re.escape(name)}"
                else:
                    expected = f"non-editorial delivery changed: {re.escape(name)}"
                with self.assertRaisesRegex(ValueError, expected):
                    prepare_snapshot(self.source)
                self.assertEqual(self.snapshot.read_bytes(), self.original_snapshot)
                path.write_bytes(payload)


    def test_new_renderer_asset_admission_requires_the_reviewed_digest(self):
        name = next(iter(RENDERER_ASSET_PINS))
        del self.manifest["files"][name]
        self.snapshot.write_text(json.dumps(self.manifest))
        prepared = json.loads(prepare_snapshot(self.source))
        self.assertEqual(prepared["files"][name]["source_sha256"], RENDERER_ASSET_PINS[name])
        (self.source / name).write_bytes(b"unreviewed replacement")
        with self.assertRaisesRegex(ValueError, "renderer asset differs from reviewed delivery"):
            prepare_snapshot(self.source)


class ReflectiveFragmentNavigationTests(unittest.TestCase):
    def test_delayed_fragment_lookup_respects_newer_reader_navigation(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the fragment-navigation runtime check")
        probe = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('async function followMovedFragment(){');
const end = source.indexOf('\nfollowMovedFragment();', start);
assert.ok(start >= 0 && end > start, 'compatibility function must be present');
const implementation = source.slice(start, end);
function deferred(){
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
async function run(changedWhile){
  const initial = 'https://ferazambuja.github.io/reflective-color-display/?pair=BLUE_GREEN&width=1&order=ABBA#metric-comparison';
  const location = new URL(initial);
  const redirects = [];
  location.replace = href => redirects.push(href);
  const response = deferred(), json = deferred(), jsonStarted = deferred();
  const context = vm.createContext({
    URL, location,
    document: { getElementById: id => id === 'first-icc' ? {} : null },
    fetch: () => response.promise,
  });
  vm.runInContext(implementation, context);
  const pending = vm.runInContext('followMovedFragment()', context);
  if(changedWhile === 'fetch') location.href = initial.replace('#metric-comparison', '#first-icc');
  response.resolve({ ok: true, json: () => { jsonStarted.resolve(); return json.promise; } });
  await jsonStarted.promise;
  if(changedWhile === 'json') location.href = initial.replace('#metric-comparison', '#first-icc');
  json.resolve({ 'metric-comparison': '/reflective-color-display/prediction/#metric-comparison' });
  await pending;
  if(changedWhile){
    assert.deepEqual(redirects, [], 'stale lookup must not redirect after navigation during ' + changedWhile);
    assert.equal(location.hash, '#first-icc');
  }else{
    assert.deepEqual(redirects, [
      'https://ferazambuja.github.io/reflective-color-display/prediction/?pair=BLUE_GREEN&width=1&order=ABBA#metric-comparison'
    ], 'unchanged lookup must retain the original measurement selection');
  }
}
(async () => {
  await run('fetch');
  await run('json');
  await run(null);
  console.log('fragment navigation checks completed');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            [node, "-", str(SOURCE / "story.js")], input=probe,
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("fragment navigation checks completed", result.stdout)


if __name__ == "__main__":
    unittest.main()
