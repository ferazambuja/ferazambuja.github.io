#!/usr/bin/env python3
"""Build the account-level portfolio site from source Markdown.

No study, report, or method prose is tracked in this repository. The technical
repositories remain the single source of truth; this build checks them out and
renders them. Adding a study is a file drop in the content repository. Adding a
project is one entry in ``PROJECTS`` plus a landing page under ``site/``.

Source excerpts are located in the tested sources by content marker and copied
verbatim, so a shown excerpt cannot drift from the code it represents. A
missing marker fails the build rather than emitting stale code.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name

SITE_URL = "https://ferazambuja.github.io"
AUTHOR = "Fernando Voltolini de Azambuja"
COMPARATOR_REPO = "ferazambuja/cam16-hellwig-comparator"
COMPARATOR_URL = f"https://github.com/{COMPARATOR_REPO}"
# The run history rather than one pinned run id: a frozen link keeps claiming
# a pass for a tree that moved on, and this page is rebuilt from that tree.
COMPARATOR_CI_URL = (
    f"{COMPARATOR_URL}/actions/workflows/test.yml?query=branch%3Amain"
)
HDR_ROUTE = "/hdr-platform/"
COMPARATOR_ROUTE = "/imaging/cam16-hellwig-comparator/"
CALCULATOR_PREVIEW = "/assets/social/cam16-calculator.jpg"
CALCULATOR_PREVIEW_ALT = (
    "The calculator with stimulus and adopted-white inputs beside a results "
    "table of CAM16 and 2022-proposal appearance correlates."
)
COMPARATOR_LEGACY_ROUTE = "/imaging/methods/cam16-hellwig-comparator/"

# Inline and render-blocking on purpose. A stored theme has to be on the root
# element before the first paint, so a reader who chose dark is never shown a
# white page first. Deferring this to theme.js would move the work after paint
# and reintroduce exactly that flash.
THEME_BOOTSTRAP = (
    "<script>(function(){try{var t=localStorage.getItem(\"theme\");"
    'if(t==="dark"||t==="light")'
    'document.documentElement.setAttribute("data-theme",t)}catch(e){}})();</script>'
)


# --------------------------------------------------------------------------
# Project registry. One entry per technical area the site publishes.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    blurb: str


@dataclass(frozen=True)
class Project:
    key: str
    title: str
    tagline: str
    repo: str
    sections: tuple[Section, ...]
    excerpts: dict[str, "Excerpt"] = field(default_factory=dict)
    method_excerpt: dict[str, str] = field(default_factory=dict)
    landing_excerpts: tuple[str, ...] = ()
    nav_titles: dict[str, str] = field(default_factory=dict)
    landing_figures: tuple[tuple[str, str, str, str], ...] = ()
    # Preview shown when this landing page is shared. A raster, because link
    # unfurlers do not render SVG, which is what every generated figure here
    # is -- so this is a photograph of the measurement rather than a chart.
    social_image: str = ""
    social_image_alt: str = ""

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.repo}"


@dataclass(frozen=True)
class Excerpt:
    """A verbatim range of a tested C++ source, located by content marker."""

    source: str
    start_contains: str
    end_contains: str
    caption: str
    # Slug of the study whose published result this code produces. An excerpt
    # with no destination is a code sample; with one, it has practical context.
    study: str = ""
    after_heading: str = ""
    language: str = "cpp"
    start_offset: int = 0
    include_end: bool = True
    balance_braces: bool = False


@dataclass(frozen=True)
class HomeSelection:
    slug: str
    figure: str
    alt: str
    summary: str


@dataclass(frozen=True)
class HdrFigure:
    """One published figure on the HDR platform page.

    Screenshots ship as a WebP with a PNG beside it; diagrams are a single
    SVG. Both carry their intrinsic size so the browser reserves the box
    before the bytes arrive, and both link to the full-width file -- the
    page shows them at half size, and interface text at half size is
    readable but not legible.
    """

    stem: str
    width: int
    height: int
    alt: str
    caption: str
    vector: bool = False

    @property
    def display(self) -> str:
        return f"/assets/hdr/{self.stem}.{'svg' if self.vector else 'png'}"


@dataclass(frozen=True)
class ProfileAsset:
    source: str
    filename: str
    alt: str
    caption: str
    css_class: str


HOME_SELECTIONS = (
    HomeSelection(
        "sfr-aperture-and-field",
        "sfr-aperture-field.svg",
        "Line chart comparing Nikon D800 and D810 MTF50 across aperture, with center-to-corner margin bars.",
        "Across 299 accepted regions, a center-only score missed important field behavior in the D800 series.",
    ),
    HomeSelection(
        "gamut-mapping",
        "gamut-mapping.svg",
        "CIELAB color plane showing Display-P3 colors mapped toward sRGB, beside method-comparison plots.",
        "Local MINDE lowered mean CIEDE2000 to 2.323, but no method won across average error, worst case, and hue behavior.",
    ),
    HomeSelection(
        "spectral-sensitivity-and-color-fidelity",
        "spectral-color-fidelity.svg",
        "Dot plot comparing ISO-style color-fidelity scores for five cameras across three chart sets.",
        "Four cameras closed against paired chart captures at 9.5–13.8% RMS per channel; the unpaired fifth remained unscored.",
    ),
    HomeSelection(
        "cfa-flat-field-response",
        "flat-field-response.svg",
        "Heatmaps of center-normalized green response and red-to-green chromatic response, with a screening summary.",
        "Only 3 of 52 sphere frames retained headroom; equal-radius corners still spread by 16.1–20.0%.",
    ),
)


HDR_FIGURES = {
    "STIMULUS_SHOT": HdrFigure(
        "stimulus-authoring",
        1600,
        986,
        "Stimulus editor showing two gray disks on a black field, with a layer "
        "inspector reporting per-layer luminance in cd/m², the size mode, "
        "and the display's extended-range context.",
        "Two circle layers at 60.0 and 95.0 cd/m². The inspector reports a "
        "0.95× extended-range ratio against a 100 cd/m² render white.",
    ),
    "SIGNAL_PATH": HdrFigure(
        "hdr-signal-path",
        1260,
        1040,
        "Six-stage flow from authored stimulus to measured display output, "
        "grouped into requested stimulus state, realized renderer state, and "
        "measured output.",
        "Requested stimulus state, realized renderer state, and measured "
        "output stay separate by construction: a meter reading joins as a "
        "third record rather than as confirmation of the first two.",
        vector=True,
    ),
    "STUDY_AUTHORING": HdrFigure(
        "study-authoring",
        1600,
        1005,
        "Study authoring workspace with the card preview showing two oblique "
        "sinusoidal gratings in circular apertures, a spatial "
        "two-alternative forced-choice binding, and a generated trial "
        "schedule.",
        "200 trials expanded from seed 99999, counterbalanced 100 left and 100 "
        "right. This card is marked Training, so its trials are excluded "
        "from fitting.",
    ),
    "STUDY_LIBRARY": HdrFigure(
        "study-library",
        1600,
        1004,
        "Study library listing four studies with identifiers, schema versions, "
        "perceptual models, and per-study readiness badges.",
        "Three bundled thesis studies and one researcher-authored draft, all "
        "on schema 1.15.0. The draft is the one marked Blocked.",
    ),
    "RUN_READINESS": HdrFigure(
        "run-readiness",
        1600,
        929,
        "Run-readiness evaluation showing study validation state, "
        "luminance-envelope readiness with per-target measurement rows, and a "
        "rehearsal-only posture.",
        "Validation is clear, but the luminance envelope needs calibration: "
        "none of the declared targets has a measurement recorded against "
        "it.",
    ),
    "EDR_CONTRACT": HdrFigure(
        "edr-contract",
        1260,
        940,
        "Reference table of the five surface fields that place a macOS layer "
        "in extended dynamic range, with the value each must hold.",
        "All five fields have to agree. Setting the dynamic-range hint alone "
        "leaves the surface in standard range.",
        vector=True,
    ),
}


PROFILE_ASSETS = {
    "PIPELINE_ART": ProfileAsset(
        "assets/portfolio/imaging-systems/digital-camera-pipeline-composite.jpg",
        "digital-camera-pipeline-composite.jpg",
        "Composite portrait of a cellist layered with saturated color blocks, vertical scan lines, and enlarged hands on a string instrument.",
        "Original photograph and digital composite by Fernando",
        "profile-art profile-art-hero",
    ),
    "SPECTRAL_ART": ProfileAsset(
        "assets/portfolio/imaging-systems/spectral-resolution-composite.jpg",
        "spectral-resolution-composite.jpg",
        "Multiple-exposure cellist portrait over vertical bands shifting from blue and magenta through red, yellow, and green.",
        "Original photograph and digital composite by Fernando",
        "profile-art profile-art-wide",
    ),
    "SPATIAL_ART": ProfileAsset(
        "assets/portfolio/imaging-systems/spatial-resolution-cellist.jpg",
        "spatial-resolution-cellist.jpg",
        "Black-and-white portrait of a cellist leaning into the instrument against a plain dark background.",
        "Original monochrome photograph by Fernando",
        "profile-art profile-art-portrait",
    ),
}


IMAGING = Project(
    key="imaging",
    title="Imaging and color measurement",
    tagline=(
        "Camera image quality, spectral measurement, and deterministic color "
        "models, measured in C++20 against archived captures and instrument data."
    ),
    repo="ferazambuja/imaging-color-measurement",
    sections=(
        Section(
            "studies",
            "Studies",
            "One question each, answered against measured data, with the "
            "limitation that governs the answer stated in the same breath.",
        ),
        Section(
            "reports",
            "Reports",
            "The full numeric record behind each study: inputs, gates, "
            "intermediate values, and every figure the study summarizes.",
        ),
        Section(
            "methods",
            "Methods",
            "Formulas, data flow, and the implementation that computes them.",
        ),
    ),
    excerpts={
        "sfr": Excerpt(
            source="code/src/sfr.cpp",
            start_contains="  std::vector<double> lsf;",
            end_contains="  if (result.mtf_frequency_cy_per_px.empty() ||",
            include_end=False,
            study="sfr-aperture-and-field",
            after_heading="The result",
            caption=(
                "Differentiating the oversampled edge into a line-spread "
                "function, then transforming it. This runs on sensor-linear "
                "green from the black-subtracted mosaic; a demosaic or gamma "
                "step here would be measured as part of the lens."
            ),
        ),
        "ccm": Excerpt(
            source="code/src/colorimetry.cpp",
            study="colorchecker-ccm",
            after_heading="The result the design was built to catch",
            start_contains="CcmFit fit_matrix_only(",
            end_contains="}",
            balance_braces=True,
            caption=(
                "The least-squares matrix fit, kept deliberately separate from "
                "evaluation so a fit can never be scored on the patches that "
                "produced it."
            ),
        ),
        "gamut": Excerpt(
            source="code/src/gamut_mapping.cpp",
            study="gamut-mapping",
            after_heading="What changed",
            start_contains=(
                "      channel_surface_crossings(lightness, hue_radians, space, options);"
            ),
            end_contains="            refinement_iterations, converged};",
            start_offset=-1,
            caption=(
                "Finding the first gamut exit rather than any nearby in-gamut "
                "color. The distinction is what separates a defensible mapping "
                "from one that quietly relocates hues."
            ),
        ),
        "closure": Excerpt(
            source="code/src/spectral_closure.cpp",
            study="spectral-sensitivity-and-color-fidelity",
            after_heading="Results",
            start_contains=(
                "  // Per-patch raw prediction and the global-scale least-squares fit."
            ),
            end_contains="  SpectralClosureChannel* chans[3]",
            include_end=False,
            caption=(
                "One global exposure scale across every patch and channel. "
                "Fitting per patch would hide exactly the disagreement the "
                "closure test exists to expose."
            ),
        ),
        "cam16": Excerpt(
            source="code/src/cam16_equation_audit.cpp",
            study="color-model-equation-audit",
            after_heading="What the audit found",
            start_contains="double cam16_relative_chroma_fixed_adapted_response(",
            end_contains="}",
            balance_braces=True,
            caption=(
                "The coupled CAM16 response used in the audit. Keeping the "
                "background, chroma, and lightness terms together is what "
                "shows why the isolated 2.595× term is neither a bound nor "
                "the complete model response."
            ),
        ),
        "flat": Excerpt(
            source="code/src/shading.cpp",
            study="cfa-flat-field-response",
            after_heading="What the accepted frames show",
            start_contains="std::optional<ShadingGeometry> make_shading_geometry(",
            end_contains="}",
            balance_braces=True,
            caption=(
                "The geometry contract behind the equal-radius comparison. "
                "It accepts only even, CFA-balanced rectangles and refuses a "
                "layout that would break the symmetry requirement."
            ),
        ),
        "spectral_compare": Excerpt(
            source="code/src/spectral_compare.cpp",
            study="spectral-measurement-crosscheck",
            after_heading="What the spectra establish",
            start_contains="std::vector<SpectralComparisonBand> comparison_bands(",
            end_contains="}",
            balance_braces=True,
            caption=(
                "The residual is kept signed while each wavelength receives "
                "a normalized share of the squared error. That separation "
                "locates the two dominant bands without assigning them a cause."
            ),
        ),
        "spectro_group": Excerpt(
            source="code/src/spectro_analysis.cpp",
            study="spectroradiometer-recovery",
            after_heading="The result",
            start_contains="SpectroGroupAnalysis analyze_spectro_group(",
            end_contains="}",
            balance_braces=True,
            caption=(
                "Repeated readings are reduced along three separate axes: "
                "integrated level, normalized spectral shape, and recorded "
                "chromaticity. A level shift therefore cannot masquerade as "
                "a shape change."
            ),
        ),
    },
    method_excerpt={
        "cam16-equation-audit": "cam16",
        "slanted-edge-sfr": "sfr",
        "color-correction-matrix": "ccm",
        "flat-field-response": "flat",
        "gamut-mapping": "gamut",
        "spectral-comparison": "spectral_compare",
        "spectral-fidelity": "closure",
        "spectral-group-analysis": "spectro_group",
    },
    # One representative listing. The implementations themselves live on the
    # studies whose results they produce; the landing indexes all eight rather
    # than reprinting two of them.
    landing_excerpts=("sfr",),
    # Navigation labels. Study titles are questions, which make poor sidebar
    # entries; report and method titles are often too long. Anything absent
    # here falls back to the document's own H1, never to a prettified slug.
    nav_titles={
        "studies/cfa-flat-field-response": "CFA flat-field response",
        "studies/color-model-equation-audit": "Color-model equation audit",
        "studies/colorchecker-ccm": "ColorChecker CCM validation",
        "studies/gamut-mapping": "Display-P3 to sRGB mapping",
        "studies/sfr-aperture-and-field": "SFR across aperture and field",
        "studies/spectral-measurement-crosscheck": "Spectral cross-check",
        "studies/spectral-sensitivity-and-color-fidelity": (
            "Spectral sensitivity and fidelity"
        ),
        "studies/spectroradiometer-recovery": "Spectroradiometer recovery",
        "reports/cam16-equation-audit": "CAM16 equation audit",
        "reports/ccm-fit": "CCM fit and evaluation",
        "reports/flat-field-response": "CFA flat-field response",
        "reports/gamut-mapping": "Gamut-mapping comparison",
        "reports/patch-extraction": "Patch extraction",
        "reports/reference-provenance": "Reference provenance",
        "reports/sfr-mtf": "Slanted-edge SFR",
        "reports/spectral-measurement-crosscheck": "Spectral cross-check",
        "reports/spectral-sensitivity": "Spectral sensitivity",
        "reports/spectroradiometer-recovery": "Spectroradiometer recovery",
        "methods/cam16-equation-audit": "CAM16 equation audit",
        "methods/color-correction-matrix": "Color-correction matrix",
        "methods/flat-field-response": "Flat-field response",
        "methods/gamut-mapping": "Gamut mapping",
        "methods/slanted-edge-sfr": "Slanted-edge SFR",
        "methods/spectral-comparison": "Spectral comparison",
        "methods/spectral-fidelity": "Spectral fidelity",
        "methods/spectral-group-analysis": "Spectral group analysis",
    },
    # Figures shown at full reading width on the landing page. Thumbnails of
    # dense multi-panel plots are decoration at card size, not useful previews.
    # Deliberately disjoint from HOME_SELECTIONS. The home page carries four
    # results; this page adds two legible figures rather than repeating the
    # same plots or turning the overview into a figure inventory.
    social_image="/assets/figures/context/colorchecker-sg-patch-grid.jpg",
    social_image_alt=(
        "Grid of matte color patches on a dark ground from a ColorChecker "
        "Digital SG chart, including neutral ramps, skin-tone rows, and "
        "saturated primaries."
    ),
    landing_figures=(
        (
            "ccm-validation.svg",
            "colorchecker-ccm",
            "Per-patch color-difference chart comparing training and held-out "
            "error for the fitted matrix, beside a patch-selection comparison.",
            "Training against held-out error for the fitted matrix, and the "
            "patch-selection comparison that explains the better-looking "
            "headline.",
        ),
        (
            "spectroradiometer-group-variation.svg",
            "spectroradiometer-recovery",
            "Bar chart of level variation per measurement group beside a "
            "scatter of level against chromaticity separation.",
            "Level, spectral shape, and chromaticity variation across 37 "
            "repeated groups, kept on separate axes because their maxima fall "
            "on different groups.",
        ),
    ),
)

PROJECTS: tuple[Project, ...] = (IMAGING,)


# --------------------------------------------------------------------------
# Excerpt extraction
# --------------------------------------------------------------------------


def _find_line(lines: list[str], needle: str, begin: int = 0) -> int:
    for index in range(begin, len(lines)):
        if needle in lines[index]:
            return index
    raise SystemExit(f"excerpt marker not found: {needle!r}")


def _closing_brace(lines: list[str], start: int) -> int:
    depth = 0
    opened = False
    for index in range(start, len(lines)):
        depth += lines[index].count("{")
        if "{" in lines[index]:
            opened = True
        depth -= lines[index].count("}")
        if opened and depth == 0:
            return index
    raise SystemExit(f"unbalanced braces from line {start + 1}")


def extract_excerpt(
    content_root: Path,
    project: Project,
    name: str,
    study_index: dict[str, dict] | None = None,
) -> dict:
    spec = project.excerpts[name]
    lines = (content_root / spec.source).read_text(encoding="utf-8").splitlines()
    start = _find_line(lines, spec.start_contains) + spec.start_offset
    if start < 0:
        raise SystemExit(f"excerpt {name!r} starts before its source file")
    if spec.balance_braces:
        end = _closing_brace(lines, start)
    else:
        marker = _find_line(lines, spec.end_contains, start)
        end = marker if spec.include_end else marker - 1
    if end < start:
        raise SystemExit(f"excerpt {name!r} has an empty range")
    used_in = None
    if spec.study:
        if study_index is None or spec.study not in study_index:
            raise SystemExit(
                f"excerpt {name!r} names an unknown study: {spec.study!r}"
            )
        used_in = study_index[spec.study]
    return {
        "used_in": used_in,
        "code": "\n".join(lines[start : end + 1]),
        "source": spec.source,
        "first": start + 1,
        "last": end + 1,
        "caption": spec.caption,
        "language": spec.language,
        "url": f"{project.repo_url}/blob/main/{spec.source}#L{start + 1}-L{end + 1}",
    }


# --------------------------------------------------------------------------
# Markdown rendering and link rewriting
# --------------------------------------------------------------------------

MD_EXTENSIONS = ["extra", "codehilite", "sane_lists", "smarty", "toc"]
MD_CONFIG = {
    "codehilite": {"guess_lang": False, "css_class": "highlight"},
    "toc": {"permalink": False},
}

_ATTR = re.compile(r'(?P<attr>\bhref|\bsrc)="(?P<value>[^"]*)"')
_SECTION_KEYS = {"studies", "reports", "methods"}


def rewrite_target(raw: str, *, doc_dir: PurePosixPath, project: Project) -> str:
    """Map one repository-relative link onto a site route or a GitHub URL.

    Unknown shapes raise. A silent pass-through would ship a dead link, and a
    dead link on the page a resume points at costs more than a failed build.
    """

    if raw.startswith(("http://", "https://", "mailto:", "#", "/")):
        return raw
    path_part, sep, fragment = raw.partition("#")
    fragment = f"{sep}{fragment}" if sep else ""
    if not path_part:
        return raw

    trailing = path_part.endswith("/")
    resolved = PurePosixPath(*(doc_dir / path_part).parts)
    parts: list[str] = []
    for part in resolved.parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    target = "/".join(parts)

    if target.startswith("figures/"):
        return f"/assets/{target}{fragment}"

    head = parts[0] if parts else ""
    if head in _SECTION_KEYS and target.endswith(".md"):
        slug = parts[-1][: -len(".md")]
        # GitHub preserves the gap left by punctuation as repeated hyphens in
        # heading fragments; Python-Markdown collapses that gap. Normalize only
        # links that become local HTML routes. The verifier checks the resolved
        # heading, so a broader mismatch still fails closed.
        site_fragment = re.sub(r"-{2,}", "-", fragment)
        if slug == "README":
            return f"/{project.key}/{head}/{site_fragment}"
        return f"/{project.key}/{head}/{slug}/{site_fragment}"

    kind = "tree" if trailing else "blob"
    return f"{project.repo_url}/{kind}/main/{target}{fragment}"


_WHOLE_PARAGRAPH_EM = re.compile(r"<p><em>(.*?)</em></p>", re.S)


# Where the pointer belongs on each page, and why the calculator extends that
# page. It sits immediately before the section that states the limits. By then
# the reader has the equations and numbers and is at the moment of wanting
# their own values -- not at the end of the document, where this used to sit.
CALCULATOR_POINTERS = {
    ("studies", "color-model-equation-audit"): (
        "what-this-establishesand-what-it-does-not",
        "This study works from declared <code>J</code> and background values, "
        "not XYZ.",
    ),
    ("reports", "cam16-equation-audit"): (
        "what-this-calculation-cannot-answer",
        "The sweeps above use declared values rather than XYZ inputs.",
    ),
    ("methods", "cam16-equation-audit"): (
        "what-the-tests-establish",
        "This C++ module does not accept XYZ or return a complete appearance "
        "specification.",
    ),
}


def calculator_pointer(lead: str) -> str:
    return (
        f'<aside class="related-tool"><strong>{lead}</strong> '
        f'<a href="{COMPARATOR_ROUTE}">Compare CAM16 and Hellwig\u2013Fairchild '
        "with your own XYZ values and viewing conditions</a>. Its results are "
        "model calculations, not measurements; a difference between the "
        "models is not a color error or perceptual distance.</aside>"
    )


def place_calculator_pointer(
    rendered: str, anchor: str, lead: str, where: str
) -> str:
    """Insert the pointer before a named heading, or fail loudly.

    Appending to the end needs no anchor and never breaks, which is exactly
    why it went unnoticed there. Anchoring means a renamed heading stops the
    build instead of silently sliding the pointer back to the bottom.
    """

    marker = f'<h2 id="{anchor}"'
    index = rendered.find(marker)
    if index < 0:
        raise SystemExit(
            f"calculator pointer for {where} has no heading {anchor!r}; "
            "the document's headings changed"
        )
    return rendered[:index] + calculator_pointer(lead) + rendered[index:]


def render_markdown(text: str, *, doc_dir: PurePosixPath, project: Project) -> str:
    converter = markdown.Markdown(
        extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG
    )
    body = converter.convert(text)

    def replace(match: re.Match[str]) -> str:
        value = html.unescape(match.group("value"))
        new = rewrite_target(value, doc_dir=doc_dir, project=project)
        return f'{match.group("attr")}="{html.escape(new, quote=True)}"'

    body = _ATTR.sub(replace, body)
    # A whole-paragraph italic is a caption and is set as one. Marking it here
    # rather than in CSS is the difference that matters: ":only-child" ignores
    # text nodes, so "Material marked <em>Training</em> is excluded" also
    # matched, and a mid-sentence emphasis became a block that broke the
    # sentence across three lines.
    return _WHOLE_PARAGRAPH_EM.sub(r'<p class="caption"><em>\1</em></p>', body)


def strip_front_links(text: str) -> tuple[str, str]:
    """Split a document's title from its body.

    Study pages open with an H1 and, in some files, a navigation line of links
    to the report and method. The site puts both in furniture, so they are
    lifted out of the prose rather than rendered twice.
    """

    lines = text.splitlines()
    title = ""
    start = 0
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            start = index + 1
            break
    rest = lines[start:]
    while rest and not rest[0].strip():
        rest.pop(0)
    # Drop a leading link-only paragraph (the in-repo breadcrumb).
    block: list[str] = []
    cursor = 0
    while cursor < len(rest) and rest[cursor].strip():
        block.append(rest[cursor])
        cursor += 1
    joined = " ".join(block)
    if block and re.fullmatch(r"(?:\[[^\]]+\]\([^)]+\)|\s|·|\|)+", joined):
        rest = rest[cursor:]
        while rest and not rest[0].strip():
            rest.pop(0)
    return title, "\n".join(rest)


_MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
_RESOURCE_KINDS = (
    ("../reports/", "Report"),
    ("../methods/", "Method"),
    ("../data/", "Data"),
    ("../code/", "Source"),
)


def split_study_intro(text: str) -> tuple[str, str]:
    """Keep the result-bearing lead separate from the long study body."""

    match = re.search(r"(?m)^##\s+", text)
    if match is None:
        raise SystemExit("study has no section after its opening result")
    return text[: match.start()].rstrip(), text[match.start() :].lstrip()


def split_after_heading(text: str, heading: str) -> tuple[str, str]:
    """Split after one complete H2 section chosen for code placement."""

    selected = re.search(
        rf"(?m)^##\s+{re.escape(heading)}\s*$",
        text,
    )
    if selected is None:
        raise SystemExit(f"study implementation heading disappeared: {heading!r}")
    following = re.search(r"(?m)^##\s+", text[selected.end() :])
    if following is None:
        return text.rstrip(), ""
    split = selected.end() + following.start()
    return text[:split].rstrip(), text[split:].lstrip()


def study_resource_bar(text: str, project: Project) -> str:
    """Lift the useful routes out of a study before the reader has to hunt."""

    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    kept_by_kind: dict[str, int] = {}
    for label, target in _MARKDOWN_LINK.findall(text):
        for prefix, kind in _RESOURCE_KINDS:
            if not target.startswith(prefix):
                continue
            # Keep every report because some studies have distinct extraction,
            # fit, and reference records. One method, data entry, and source
            # are enough for the early navigation bar; the full study retains
            # every source link later in the page.
            if kind != "Report" and kept_by_kind.get(kind, 0) >= 1:
                break
            route = rewrite_target(
                target, doc_dir=PurePosixPath("studies"), project=project
            )
            key = (kind, route)
            if key not in seen:
                found.append((kind, re.sub(r"[`*_]", "", label), route))
                seen.add(key)
                kept_by_kind[kind] = kept_by_kind.get(kind, 0) + 1
            break

    kinds = {kind for kind, _, _ in found}
    if "Method" not in kinds or "Source" not in kinds:
        raise SystemExit("study resource bar requires a method and source link")

    items = "".join(
        '<li><span class="resource-kind">'
        f"{html.escape(kind)}</span> "
        f'<a href="{html.escape(route, quote=True)}">{html.escape(label)}</a></li>'
        for kind, label, route in found
    )
    return (
        '<nav class="study-resources" aria-label="Study resources and implementation">'
        "<strong>Study resources</strong>"
        f"<ul>{items}</ul></nav>"
    )


# --------------------------------------------------------------------------
# Study card parsing (the imaging landing page)
# --------------------------------------------------------------------------


@dataclass
class Card:
    group: str
    title: str
    slug: str
    blurb: str = ""
    result: str = ""
    figure: str = ""
    links: str = ""


def parse_cards(readme: str) -> list[Card]:
    """Read the curated study index into structured cards.

    The prose stays in the content repository. Nothing here is a second copy;
    if a summary changes there, the landing page changes with it.
    """

    cards: list[Card] = []
    group = ""
    current: Card | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is None:
            return
        text = "\n".join(buffer).strip()
        if not text:
            return
        if text.startswith("!["):
            if not current.figure:
                match = re.search(r"\((\.\./figures/[^)]+)\)", text)
                if match:
                    current.figure = match.group(1)
        elif re.match(r"^\[(Study|study)\]", text):
            current.links = text
        elif text.startswith("*") and text.endswith("*"):
            pass  # figure caption; the landing page uses its own
        elif not current.blurb:
            current.blurb = text
        elif not current.result:
            current.result = text

    for line in readme.splitlines():
        if line.startswith("## "):
            flush()
            buffer = []
            group = line[3:].strip()
            continue
        if line.startswith("### "):
            flush()
            buffer = []
            match = re.match(r"###\s+\[(?P<title>.+?)\]\((?P<href>[^)]+)\)", line)
            if not match:
                raise SystemExit(f"unparsable study heading: {line!r}")
            current = Card(
                group=group,
                title=match.group("title"),
                slug=match.group("href").removesuffix(".md"),
            )
            cards.append(current)
            continue
        if not line.strip():
            flush()
            buffer = []
            continue
        buffer.append(line)
    flush()
    if not cards:
        raise SystemExit("no studies parsed from the index")
    return cards


# --------------------------------------------------------------------------
# HTML shell
# --------------------------------------------------------------------------


def page(
    *,
    title: str,
    description: str,
    body: str,
    canonical: str,
    nav_active: str = "",
    sidebar: str = "",
    depth_class: str = "",
    social_image: str = "",
    social_image_alt: str = "",
) -> str:
    nav_items = [
        ("/", "Home", "home"),
        (f"/{IMAGING.key}/", "Imaging", "imaging"),
        (HDR_ROUTE, "HDR platform", "hdr"),
    ]
    nav_links = []
    for href, label, key in nav_items:
        active = key == nav_active
        current = (
            ' aria-current="page"'
            if href == canonical and not sidebar
            else (' aria-current="location"' if active else "")
        )
        nav_links.append(
            f'<a href="{href}"{" class=\"active\"" if active else ""}'
            f"{current}>{label}</a>"
        )
    nav = "".join(nav_links)
    layout = "layout-with-sidebar" if sidebar else "layout-plain"
    aside = f'<aside class="sidebar">{sidebar}</aside>' if sidebar else ""
    social_meta = ""
    twitter_card = "summary"
    if social_image:
        if not social_image_alt.strip():
            raise ValueError("a social preview image needs descriptive alt text")
        image_url = f"{SITE_URL}{social_image}"
        image_alt = html.escape(social_image_alt, quote=True)
        social_meta = (
            f'<meta property="og:image" content="{image_url}">\n'
            f'<meta property="og:image:alt" content="{image_alt}">\n'
            f'<meta name="twitter:image" content="{image_url}">\n'
            f'<meta name="twitter:image:alt" content="{image_alt}">\n'
        )
        twitter_card = "summary_large_image"
    elif social_image_alt:
        raise ValueError("social preview alt text has no image")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{SITE_URL}{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{SITE_URL}{canonical}">
{social_meta}<meta name="twitter:card" content="{twitter_card}">
<link rel="stylesheet" href="/assets/site.css">
<link rel="stylesheet" href="/assets/highlight.css">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{THEME_BOOTSTRAP}
<script src="/assets/theme.js" defer></script>
</head>
<body class="{depth_class}">
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <div class="topbar-inner">
    <a class="wordmark" href="/">{AUTHOR}</a>
    <nav class="topnav">{nav}</nav>
  </div>
</header>
<div class="{layout}">
{aside}
<main id="main">
{body}
</main>
</div>
<footer class="sitefoot">
  <p>{AUTHOR} · <a href="https://github.com/ferazambuja">GitHub</a> · <a href="https://www.linkedin.com/in/fernando-voltolini-de-azambuja">LinkedIn</a></p>
</footer>
</body>
</html>
"""


def redirect_page(*, title: str, target: str, canonical: str) -> str:
    """Keep a retired public URL useful without adding another content page."""

    body = (
        f"<h1>{html.escape(title)}</h1>"
        '<p class="lede">This page moved.</p>'
        f'<p><a href="{target}">Open the current calculator</a>.</p>'
    )
    rendered = page(
        title=f"{title} · {AUTHOR}",
        description="Redirect to the current CAM16 and Hellwig comparison.",
        body=body,
        canonical=canonical,
        nav_active="imaging",
        depth_class="redirect",
    )
    redirect_meta = (
        '<meta name="robots" content="noindex,follow">\n'
        f'<meta http-equiv="refresh" content="0; url={target}">\n'
        f'<script>location.replace("{target}");</script>\n'
    )
    return rendered.replace("</head>", f"{redirect_meta}</head>")


def sidebar_html(project: Project, docs: dict, active: str) -> str:
    blocks = [f'<p class="side-title">{html.escape(project.title)}</p>']
    overview_active = f"/{project.key}/" == active
    overview_class = ' class="active"' if overview_active else ""
    overview_current = ' aria-current="page"' if overview_active else ""
    blocks.append(
        f'<p class="side-overview"><a href="/{project.key}/"{overview_class}'
        f"{overview_current}>Overview</a></p>"
    )
    for section in project.sections:
        entries = docs[section.key]
        items = []
        for entry in entries:
            route = entry["route"]
            is_active = route == active
            cls = ' class="active"' if is_active else ""
            current = ' aria-current="page"' if is_active else ""
            items.append(
                f'<li><a href="{route}"{cls}{current}>'
                f'{html.escape(entry["nav_title"])}</a></li>'
            )
        section_route = f"/{project.key}/{section.key}/"
        index_active = section_route == active
        index_cls = ' class="active"' if index_active else ""
        index_current = ' aria-current="page"' if index_active else ""
        heading = (
            f'<a href="{section_route}"{index_cls}{index_current}>'
            f"{html.escape(section.title)}</a>"
        )
        if section.key == "studies":
            blocks.append(
                f'<p class="side-group">{heading}</p><ul>{"".join(items)}</ul>'
            )
        else:
            section_active = active.startswith(section_route)
            opened = " open" if section_active else ""
            blocks.append(
                f'<details class="side-details"{opened}>'
                f"<summary>{html.escape(section.title)}</summary>"
                f'<p class="side-index">{heading}</p><ul>{"".join(items)}</ul>'
                "</details>"
            )

    # The calculator is the one thing in this sidebar a reader can operate
    # rather than read, and it was sitting below a rule in the same style as
    # a repository link -- a list of documents with a tool filed among them.
    # It gets its own affordance and leaves the secondary list to references.
    on_calculator = active == COMPARATOR_ROUTE
    blocks.append(
        '<p class="side-tool">'
        f'<a href="{COMPARATOR_ROUTE}"'
        f'{" class=\"active\"" if on_calculator else ""}'
        f'{" aria-current=\"page\"" if on_calculator else ""}>'
        "Open the CAM16 calculator</a></p>"
        '<div class="side-secondary">'
        f'<a href="{project.repo_url}">Technical repository</a>'
        "</div>"
    )
    return "".join(blocks)


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


def nav_title(project: Project, section: str, slug: str, title: str) -> str:
    """Sidebar label for one document.

    A curated label wins; otherwise the document's own title is used verbatim.
    A prettified slug is never produced -- "Sfr mtf" next to a real title reads
    as a build artifact, which is exactly what it is.
    """

    return project.nav_titles.get(f"{section}/{slug}", title)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(
    content_roots: dict[str, Path],
    profile_root: Path,
    comparator_root: Path,
    output: Path,
    site_dir: Path,
) -> int:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    pages_written = 0
    cards_by_project: dict[str, list[Card]] = {}

    for project in PROJECTS:
        root = content_roots[project.key]
        if not (root / "studies").is_dir():
            raise SystemExit(f"content checkout missing studies/: {root}")

        # Collect documents per section.
        docs: dict[str, list[dict]] = {}
        for section in project.sections:
            entries = []
            for md_path in sorted((root / section.key).glob("*.md")):
                if md_path.name == "README.md":
                    continue
                raw = md_path.read_text(encoding="utf-8")
                title, body_md = strip_front_links(raw)
                slug = md_path.stem
                entries.append(
                    {
                        "slug": slug,
                        "title": title or slug,
                        "nav_title": nav_title(
                            project, section.key, slug, title or slug
                        ),
                        "raw_md": raw,
                        "body_md": body_md,
                        "route": f"/{project.key}/{section.key}/{slug}/",
                        "source": f"{section.key}/{md_path.name}",
                    }
                )
            docs[section.key] = entries

        # Where each excerpt's result is published. Built from the study pages
        # themselves, so an excerpt cannot point at a study that was not built.
        study_index = {
            entry["slug"]: {"label": entry["nav_title"], "route": entry["route"]}
            for entry in docs["studies"]
        }
        study_excerpts: dict[str, str] = {}
        for name, spec in project.excerpts.items():
            if not spec.study:
                continue
            if spec.study in study_excerpts:
                raise SystemExit(
                    f"study {spec.study!r} has more than one primary excerpt"
                )
            study_excerpts[spec.study] = name
        missing_study_excerpts = set(study_index) - set(study_excerpts)
        if missing_study_excerpts:
            raise SystemExit(
                "studies without a primary implementation excerpt: "
                + ", ".join(sorted(missing_study_excerpts))
            )

        # Document pages.
        for section in project.sections:
            for entry in docs[section.key]:
                doc_dir = PurePosixPath(section.key)
                if section.key == "studies":
                    intro_md, details_md = split_study_intro(entry["body_md"])
                    intro = render_markdown(
                        intro_md, doc_dir=doc_dir, project=project
                    )
                    excerpt_name = study_excerpts[entry["slug"]]
                    spec = project.excerpts[excerpt_name]
                    before_code_md, after_code_md = split_after_heading(
                        details_md, spec.after_heading
                    )
                    before_code = render_markdown(
                        before_code_md, doc_dir=doc_dir, project=project
                    )
                    after_code = render_markdown(
                        after_code_md, doc_dir=doc_dir, project=project
                    )
                    data = extract_excerpt(
                        root,
                        project,
                        excerpt_name,
                        study_index,
                    )
                    content_html = (
                        f'<div class="prose study-lead">{intro}</div>'
                        f'{study_resource_bar(entry["raw_md"], project)}'
                        f'<div class="prose">{before_code}</div>'
                        '<section class="study-implementation" id="implementation">'
                        "<h2>Implementation used in this study</h2>"
                        '<p class="study-code-intro">A tested source excerpt, '
                        "shown where its result is discussed.</p>"
                        f"{excerpt_block(data, show_destination=False)}</section>"
                        f'<div class="prose">{after_code}</div>'
                    )
                else:
                    rendered = render_markdown(
                        entry["body_md"], doc_dir=doc_dir, project=project
                    )
                    name = project.method_excerpt.get(entry["slug"])
                    if section.key == "methods" and name:
                        data = extract_excerpt(root, project, name, study_index)
                        if data.get("used_in"):
                            content_html = (
                                f"{method_excerpt_pointer(data)}"
                                f'<div class="prose">{rendered}</div>'
                            )
                        else:
                            content_html = (
                                f'<div class="prose">{rendered}</div>'
                                f"{excerpt_block(data)}"
                            )
                    else:
                        content_html = f'<div class="prose">{rendered}</div>'
                pointer = CALCULATOR_POINTERS.get((section.key, entry["slug"]))
                if pointer:
                    content_html = place_calculator_pointer(
                        content_html, *pointer, f"{section.key}/{entry['slug']}"
                    )
                source_url = (
                    f"{project.repo_url}/blob/main/{entry['source']}"
                )
                body = (
                    f'<p class="crumb"><a href="/{project.key}/">'
                    f"{html.escape(project.title)}</a> · "
                    f'<a href="/{project.key}/{section.key}/">'
                    f"{html.escape(section.title)}</a></p>"
                    f"<h1>{html.escape(entry['title'])}</h1>"
                    f"{content_html}"
                    f'<p class="docfoot">Source file: '
                    f'<a href="{source_url}">{html.escape(entry["source"])}</a></p>'
                )
                write(
                    output / entry["route"].strip("/") / "index.html",
                    page(
                        title=f"{entry['title']} · {AUTHOR}",
                        description=entry["title"],
                        body=body,
                        canonical=entry["route"],
                        nav_active=project.key,
                        sidebar=sidebar_html(project, docs, entry["route"]),
                        depth_class="doc",
                    ),
                )
                pages_written += 1

        # Section index pages.
        for section in project.sections:
            items = "".join(
                f'<li><a href="{e["route"]}"><span class="idx-title">'
                f"{html.escape(e['title'])}</span></a></li>"
                for e in docs[section.key]
            )
            route = f"/{project.key}/{section.key}/"
            body = (
                f'<p class="crumb"><a href="/{project.key}/">'
                f"{html.escape(project.title)}</a></p>"
                f"<h1>{html.escape(section.title)}</h1>"
                f'<p class="lede">{html.escape(section.blurb)}</p>'
                f'<ul class="indexlist">{items}</ul>'
            )
            write(
                output / route.strip("/") / "index.html",
                page(
                    title=f"{section.title} · {project.title}",
                    description=section.blurb,
                    body=body,
                    canonical=route,
                    nav_active=project.key,
                    sidebar=sidebar_html(project, docs, route),
                    depth_class="doc",
                ),
            )
            pages_written += 1

        # Project landing page.
        cards = parse_cards((root / "studies" / "README.md").read_text(encoding="utf-8"))
        cards_by_project[project.key] = cards
        excerpts = {
            name: extract_excerpt(root, project, name, study_index)
            for name in project.landing_excerpts
        }
        # Every study's implementation, indexed. A section headed "How it is
        # computed" that showed two of eight described a quarter of the work.
        implementations = sorted(
            (
                extract_excerpt(root, project, name, study_index)
                for name in study_excerpts.values()
            ),
            key=lambda data: data["used_in"]["label"],
        )
        write(
            output / project.key / "index.html",
            project_landing(
                project,
                cards,
                excerpts,
                implementations,
                docs,
                site_dir,
                comparator_root,
            ),
        )
        pages_written += 1
        if project.key == IMAGING.key:
            write(
                output / COMPARATOR_ROUTE.strip("/") / "index.html",
                comparator_page(comparator_root, docs),
            )
            pages_written += 1

        # Figures.
        figures_src = root / "figures"
        if figures_src.is_dir():
            shutil.copytree(figures_src, output / "assets" / "figures")

    # Site-owned pages and profile assets.
    profile_output = output / "assets" / "profile"
    profile_output.mkdir(parents=True, exist_ok=True)
    for asset in PROFILE_ASSETS.values():
        source = profile_root / asset.source
        if not source.is_file():
            raise SystemExit(f"profile asset missing: {source}")
        shutil.copy2(source, profile_output / asset.filename)

    write(
        output / "index.html",
        home_page(site_dir, cards_by_project[IMAGING.key]),
    )
    pages_written += 1
    write(output / HDR_ROUTE.strip("/") / "index.html", hdr_page(site_dir))
    pages_written += 1
    hdr_output = output / "assets" / "hdr"
    shutil.copytree(site_dir / "hdr", hdr_output)
    # The digest list controls the build and is not published as a site asset.
    (hdr_output / "manifest.sha256").unlink()
    write(
        output / COMPARATOR_LEGACY_ROUTE.strip("/") / "index.html",
        redirect_page(
            title="CAM16 and Hellwig–Fairchild comparator",
            target=COMPARATOR_ROUTE,
            canonical=COMPARATOR_ROUTE,
        ),
    )
    pages_written += 1
    shutil.copy2(site_dir / "site.css", output / "assets" / "site.css")
    shutil.copy2(site_dir / "theme.js", output / "assets" / "theme.js")
    shutil.copytree(site_dir / "social", output / "assets" / "social")
    shutil.copy2(site_dir / "favicon.svg", output / "assets" / "favicon.svg")
    shutil.copy2(
        comparator_root / "cam16_compare.mjs",
        output / "assets" / "cam16_compare.mjs",
    )
    shutil.copy2(
        site_dir / "cam16-calculator.mjs",
        output / "assets" / "cam16-calculator.mjs",
    )
    (output / "assets" / "highlight.css").write_text(
        pygments_css(), encoding="utf-8"
    )
    (output / ".nojekyll").write_text("", encoding="utf-8")
    write(output / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    write(output / "sitemap.xml", sitemap(output))
    return pages_written


def excerpt_block(data: dict, *, show_destination: bool = True) -> str:
    code = highlight(
        data["code"],
        get_lexer_by_name(data["language"]),
        HtmlFormatter(nowrap=True),
    ).rstrip("\n")
    trailing_newlines = len(data["code"]) - len(data["code"].rstrip("\n"))
    code += "\n" * trailing_newlines
    used_in = data.get("used_in")
    destination = (
        '<p class="excerpt-use">Produces the result in '
        f'<a href="{used_in["route"]}">{html.escape(used_in["label"])}</a></p>'
        if used_in and show_destination
        else ""
    )
    return (
        '<figure class="excerpt">'
        f'<figcaption>{html.escape(data["caption"])}</figcaption>'
        f"{destination}"
        f'<pre class="code highlight"><code>{code}</code></pre>'
        f'<p class="excerpt-src"><a href="{data["url"]}">{html.escape(data["source"])}</a>'
        f' · lines {data["first"]}–{data["last"]} · extracted from the tested source '
        "at build time</p>"
        "</figure>"
    )


def method_excerpt_pointer(data: dict) -> str:
    used_in = data["used_in"]
    return (
        '<aside class="method-code-pointer">'
        "<strong>See the implementation in context.</strong> "
        f'<a href="{used_in["route"]}#implementation">'
        f'{html.escape(used_in["label"])}</a> shows the tested excerpt beside '
        f'its result. <a href="{data["url"]}">Open source lines '
        f'{data["first"]}–{data["last"]}</a>.</aside>'
    )


def pygments_css() -> str:
    """Emit the same three theme states the site stylesheet declares.

    Pygments prefixes each selector for us, so the dark rules are written flat
    rather than nested inside a wrapper block -- flat selectors need no CSS
    nesting support, and the longer prefix already outranks the light rules.
    """

    light = HtmlFormatter(style="default").get_style_defs(".highlight")
    dark = HtmlFormatter(style="github-dark")
    by_system = dark.get_style_defs(':root:not([data-theme="light"]) .highlight')
    by_choice = dark.get_style_defs(':root[data-theme="dark"] .highlight')
    return (
        f"{light}\n"
        f"@media (prefers-color-scheme: dark) {{\n{by_system}\n}}\n"
        f"{by_choice}\n"
    )


def implementation_index(implementations: list[dict]) -> str:
    """Name every study's implementation, with its exact source range.

    The landing page shows one listing in full. This says what the other seven
    are and where each is read in context, so the section covers the work
    instead of sampling it.
    """

    rows = "".join(
        '<li><a href="{route}#implementation">{label}</a>'
        '<span class="impl-src">{source} · lines {first}–{last}</span></li>'.format(
            route=data["used_in"]["route"],
            label=html.escape(data["used_in"]["label"]),
            source=html.escape(data["source"]),
            first=data["first"],
            last=data["last"],
        )
        for data in implementations
    )
    return (
        '<div class="impl-index"><h3>Every study\'s implementation</h3>'
        "<p>Each study carries the tested excerpt that produced its result, "
        "beside the result itself.</p>"
        f"<ul>{rows}</ul></div>"
    )


def comparator_payload(comparator_root: Path) -> dict:
    """Calculate the shared example with the released Python implementation."""

    script = comparator_root / "cam16_compare.py"
    module = comparator_root / "cam16_compare.mjs"
    readme = comparator_root / "README.md"
    if not script.is_file() or not module.is_file() or not readme.is_file():
        raise SystemExit(
            "CAM16/Hellwig checkout is missing its Python script, browser "
            "module, or README"
        )
    process = subprocess.run(
        [
            sys.executable,
            str(script),
            "--xyz",
            "45",
            "36",
            "12",
            "--white",
            "95.05",
            "100",
            "108.88",
            "--la",
            "318.31",
            "--yb",
            "20",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        # A build step that shells out should fail, not hang the deployment.
        timeout=120,
    )
    payload: dict = json.loads(process.stdout)
    result = payload["results"][0]
    cam16 = result["models"]["cam16"]
    hellwig = result["models"]["hellwig2022"]
    if cam16["J"] != hellwig["J"] or cam16["h"] != hellwig["h"]:
        raise SystemExit("comparator no longer shares J and h between the models")
    return payload


def comparator_table(payload: dict, *, interactive: bool = False) -> str:
    """Render the build-time reference result, optionally with live targets."""

    result = payload["results"][0]
    cam16 = result["models"]["cam16"]
    hellwig = result["models"]["hellwig2022"]

    def shown(value: float) -> str:
        return f"{value:.6g}"

    rows = []
    for name, label, status in (
        ("J", "Lightness", "shared"),
        ("Q", "Brightness", "changed"),
        ("C", "Chroma", "changed"),
        ("M", "Colorfulness", "changed"),
        ("s", "Saturation", "changed"),
        ("h", "Hue angle", "shared"),
    ):
        values = []
        for model, correlates in (("cam16", cam16), ("hellwig2022", hellwig)):
            value = shown(correlates[name])
            if interactive:
                values.append(
                    f'<td><span data-model="{model}" data-correlate="{name}" '
                    f'data-reference="{value}">{value}</span></td>'
                )
            else:
                values.append(f"<td>{value}</td>")
        rows.append(
            f'<tr class="model-{status}">'
            f'<th scope="row">{label} <code>{name}</code></th>'
            f'{"".join(values)}</tr>'
        )
    return (
        '<div class="model-table"><table><thead><tr><th>Correlate</th>'
        '<th>CAM16</th><th>2022 proposal</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def comparator_feature(comparator_root: Path) -> str:
    """Build a compact overview that leads to the interactive calculator."""

    payload = comparator_payload(comparator_root)
    version = html.escape(str(payload["implementation_version"]))
    return (
        '<section class="tool-feature" id="cam16-hellwig-comparator">'
        '<div class="tool-copy">'
        '<p class="eyebrow">Browser calculator and source code</p>'
        '<h2>One XYZ sample, two appearance models</h2>'
        '<p>Enter a stimulus and its viewing conditions to compare standard CAM16 '
        'with the Hellwig–Fairchild 2022 proposal. Both report <code>J Q C M s h</code>; '
        'the proposal keeps <code>J</code> and <code>h</code> and redefines the other '
        'four correlates.</p>'
        '<p>The published fits improve for brightness and chroma but become worse '
        'for colorfulness, so the change is a tradeoff rather than a universal win.</p>'
        '<p class="tool-actions">'
        f'<a class="tool-button" href="{COMPARATOR_ROUTE}">Open the calculator</a>'
        f'<a href="{COMPARATOR_URL}">Python and JavaScript source</a>'
        '<a href="/imaging/studies/color-model-equation-audit/">Equation study</a>'
        '</p>'
        f'<p class="tool-platform">Every push <a href="{COMPARATOR_CI_URL}">runs '
        'the suite on Windows, macOS, and Linux</a> and checks both forward '
        'models against an independent implementation.</p>'
        '</div>'
        '<div class="model-example">'
        '<p class="example-kicker">One declared condition</p>'
        '<h3>Same XYZ and viewing conditions, two formulations</h3>'
        '<p class="example-input"><code>XYZ = 45, 36, 12</code><br>'
        '<code>white = 95.05, 100, 108.88</code> (D65)<br>'
        '<code>L_A = 318.31 cd/m²; Y_b = 20; average surround</code></p>'
        f'{comparator_table(payload)}'
        '<p class="model-key">Shaded rows are the four correlates the proposal '
        'redefines. The columns use different scales; a smaller number is not '
        'automatically a dimmer or duller prediction.</p>'
        '<p class="model-limit">These are model calculations, not measurements '
        'or observer validation. Neither model outputs display RGB.</p>'
        f'<p class="model-version">Generated with public tool version {version}</p>'
        '</div>'
        '</section>'
    )


def calculator_number_field(
    name: str, label: str, value: str, *, minimum: str | None = None
) -> str:
    minimum_attribute = f' min="{minimum}"' if minimum is not None else ""
    return (
        f'<label for="calculator-{name}"><span>{html.escape(label)}</span>'
        f'<input id="calculator-{name}" name="{name}" type="number" step="any" '
        f'inputmode="decimal" value="{value}"{minimum_attribute} required></label>'
    )


def comparator_page(comparator_root: Path, docs: dict) -> str:
    """Build the interactive page around the tested browser module."""

    payload = comparator_payload(comparator_root)
    version = html.escape(str(payload["implementation_version"]))
    stimulus_fields = "".join(
        calculator_number_field(name, label, value, minimum="0")
        for name, label, value in (
            ("x", "X", "45"),
            ("y", "Y", "36"),
            ("z", "Z", "12"),
        )
    )
    white_fields = "".join(
        calculator_number_field(name, label, value, minimum="0.000000000001")
        for name, label, value in (
            ("white_x", "X", "95.05"),
            ("white_y", "Y", "100"),
            ("white_z", "Z", "108.88"),
        )
    )
    body = (
        '<p class="crumb"><a href="/imaging/">Imaging and color measurement</a></p>'
        '<h1>CAM16 and Hellwig–Fairchild calculator</h1>'
        '<p class="lede">Compare what standard CAM16 and the 2022 '
        'Hellwig–Fairchild proposal predict for the same XYZ stimulus and '
        'viewing conditions. The calculation runs in your browser.</p>'
        '<div class="calculator-grid">'
        '<form id="cam16-calculator" class="calculator-form">'
        '<h2>Inputs</h2>'
        '<p>Values are never guessed. Use one scale for the stimulus, adopted '
        'white, and background; adapting luminance remains absolute.</p>'
        '<fieldset><legend>Stimulus XYZ</legend>'
        f'<div class="calculator-triple">{stimulus_fields}</div></fieldset>'
        '<fieldset><legend>Adopted white XYZ</legend>'
        f'<div class="calculator-triple">{white_fields}</div></fieldset>'
        '<div class="calculator-pair">'
        f'{calculator_number_field("la", "Adapting luminance L_A (cd/m²)", "318.31", minimum="0.000000000001")}'
        f'{calculator_number_field("yb", "Background Y_b", "20", minimum="0.000000000001")}'
        '</div>'
        '<label for="calculator-surround"><span>Surround</span>'
        '<select id="calculator-surround" name="surround">'
        '<option value="average">Average</option><option value="dim">Dim</option>'
        '<option value="dark">Dark</option></select></label>'
        '<label class="calculator-check" for="calculator-normalize">'
        '<input id="calculator-normalize" name="normalize" type="checkbox">'
        '<span>Scale XYZ, white, and background together so white Y = 100</span>'
        '</label>'
        '<p class="calculator-note">Normalization never changes '
        '<code>L_A</code>; it is an absolute luminance in cd/m².</p>'
        '<div class="calculator-actions"><button type="submit">Calculate</button>'
        '<button type="reset" class="secondary">Reset example</button></div>'
        '</form>'
        '<section class="calculator-results" aria-labelledby="calculator-results-title">'
        '<p class="example-kicker">Results</p>'
        '<h2 id="calculator-results-title">Appearance correlates</h2>'
        '<p id="calculator-status" class="calculator-status" aria-live="polite">'
        'Reference result for the example inputs.</p>'
        '<noscript><p class="calculator-noscript">JavaScript is off, so the form '
        'cannot recalculate. The table still shows the build-verified example.</p></noscript>'
        f'{comparator_table(payload, interactive=True)}'
        '<p class="model-key">Shaded rows are redefined by the proposal. The '
        'columns use different scales, so their raw magnitudes are not a color '
        'difference and are not directly rankable.</p>'
        '<p id="calculator-hue-note" class="model-limit">Hue is shown only when '
        'the opponent response is large enough to distinguish a direction from '
        'floating-point cancellation.</p>'
        f'<p class="model-version" data-implementation-version="{version}">'
        f'Model implementation {version}</p>'
        '</section></div>'
        '<div class="calculator-explanation">'
        '<section><h2>What the models report</h2>'
        '<p>Both models describe appearance with lightness <code>J</code>, '
        'brightness <code>Q</code>, chroma <code>C</code>, colorfulness '
        '<code>M</code>, saturation <code>s</code>, and hue angle <code>h</code>. '
        'The proposal preserves <code>J</code> and <code>h</code> while changing '
        'the definitions and scales of the other four correlates.</p>'
        '<p>These outputs are not display RGB, a color-difference score, a '
        'measurement, or a verdict about which model predicts observers better.</p>'
        '</section>'
        '<section><h2>Why viewing conditions matter</h2>'
        '<p>The same XYZ can appear different as the adopted white, background, '
        'surround, or adapting luminance changes. A plausible-looking result '
        'under the wrong condition is still the wrong calculation, so every '
        'condition stays visible and editable.</p>'
        '</section>'
        '<section><h2>Why compare the formulations</h2>'
        '<p>The 2022 proposal revisits linked brightness, chroma, colorfulness, '
        'and saturation relations in CAM16. Its published fits improve for '
        'brightness and chroma but decline for colorfulness—a mixed result, not '
        'a universal replacement. <a href="/imaging/studies/color-model-equation-audit/">'
        'See the equation study</a> or '
        f'<a href="{COMPARATOR_URL}">use the Python and JavaScript source</a>.</p>'
        f'<p>The public suite <a href="{COMPARATOR_CI_URL}">runs on Windows, '
        'macOS, and Linux</a> and compares both models against an independent '
        'implementation over 1,512 declared conditions.</p>'
        '</section></div>'
        '<script type="module" src="/assets/cam16-calculator.mjs"></script>'
    )
    return page(
        title=f"CAM16 and Hellwig–Fairchild calculator · {AUTHOR}",
        description=(
            "Calculate and compare CAM16 and Hellwig–Fairchild 2022 appearance "
            "correlates for declared XYZ values and viewing conditions."
        ),
        body=body,
        canonical=COMPARATOR_ROUTE,
        nav_active="imaging",
        sidebar=sidebar_html(IMAGING, docs, COMPARATOR_ROUTE),
        depth_class="calculator-page",
        # The one page here a reader can use rather than read, so the one
        # most likely to be sent to someone. It shows its own result.
        social_image=CALCULATOR_PREVIEW,
        social_image_alt=CALCULATOR_PREVIEW_ALT,
    )


def project_landing(
    project: Project,
    cards: list[Card],
    excerpts: dict[str, dict],
    implementations: list[dict],
    docs: dict,
    site_dir: Path,
    comparator_root: Path,
) -> str:
    intro_path = site_dir / f"{project.key}.md"
    intro_md = intro_path.read_text(encoding="utf-8") if intro_path.exists() else ""
    intro = render_markdown(
        intro_md, doc_dir=PurePosixPath("."), project=project
    )

    groups: list[tuple[str, list[Card]]] = []
    for card in cards:
        if not groups or groups[-1][0] != card.group:
            groups.append((card.group, []))
        groups[-1][1].append(card)

    sections_html = []
    for group, group_cards in groups:
        items = []
        for card in group_cards:
            result = render_markdown(
                card.result, doc_dir=PurePosixPath("studies"), project=project
            )
            items.append(
                '<article class="card">'
                f'<h3><a href="/{project.key}/studies/{card.slug}/">'
                f"{html.escape(card.title)}</a></h3>"
                f'<div class="card-result">{result}</div>'
                f'<p class="card-more"><a href="/{project.key}/studies/{card.slug}/">'
                "Read the study</a></p>"
                "</article>"
            )
        sections_html.append(
            f'<section class="cardgroup"><h2>{html.escape(group)}</h2>'
            f'<div class="cards">{"".join(items)}</div></section>'
        )

    excerpt_html = "".join(
        excerpt_block(excerpts[name]) for name in project.landing_excerpts
    )

    by_slug = {card.slug: card for card in cards}
    figure_items = []
    for filename, slug, alt_text, caption in project.landing_figures:
        card = by_slug.get(slug)
        if card is None:
            raise SystemExit(f"landing figure references unknown study: {slug!r}")
        figure_items.append(
            '<figure class="landing-figure">'
            f'<img src="/assets/figures/{filename}" '
            f'alt="{html.escape(alt_text, quote=True)}" loading="lazy">'
            f"<figcaption>{html.escape(caption)} "
            f'<a href="/{project.key}/studies/{slug}/">'
            f"{html.escape(card.title)}</a></figcaption>"
            "</figure>"
        )
    figures_section = (
        '<section class="figures"><h2>Selected figures</h2>'
        f'{"".join(figure_items)}</section>'
        if figure_items
        else ""
    )

    body = (
        f'<h1>{html.escape(project.title)}</h1>'
        f'<p class="lede">{html.escape(project.tagline)}</p>'
        '<p class="jumpline"><a href="#how-it-is-computed">'
        "Skip to the implementation</a></p>"
        f'<div class="prose">{intro}</div>'
        f"{''.join(sections_html)}"
        f"{comparator_feature(comparator_root)}"
        '<section class="codeblock" id="how-it-is-computed">'
        "<h2>How it is computed</h2>"
        '<p class="lede">Excerpts are lifted from the tested source at build '
        "time and linked to their exact line range. None of it is retyped.</p>"
        f"{excerpt_html}"
        f"{implementation_index(implementations)}</section>"
        f"{figures_section}"
        '<section class="deeper"><h2>Explore further</h2>'
        f'<p><a href="/{project.key}/reports/">Reports</a> hold the complete numeric '
        f'record. <a href="/{project.key}/methods/">Methods</a> give the formulas and '
        f'the implementation. <a href="{project.repo_url}">The repository</a> holds '
        "the C++20 sources, the published data, and the tests.</p></section>"
    )
    return page(
        title=f"{project.title} · {AUTHOR}",
        description=project.tagline,
        body=body,
        canonical=f"/{project.key}/",
        nav_active=project.key,
        sidebar=sidebar_html(project, docs, f"/{project.key}/"),
        depth_class="landing",
        social_image=project.social_image,
        social_image_alt=project.social_image_alt,
    )


def profile_art(asset: ProfileAsset) -> str:
    return (
        f'<figure class="{asset.css_class}">'
        f'<img src="/assets/profile/{asset.filename}" '
        f'alt="{html.escape(asset.alt, quote=True)}">'
        f"<figcaption>{html.escape(asset.caption)}</figcaption>"
        "</figure>"
    )


def selected_work(cards: list[Card]) -> str:
    by_slug = {card.slug: card for card in cards}
    items = []
    for selection in HOME_SELECTIONS:
        card = by_slug.get(selection.slug)
        if card is None:
            raise SystemExit(
                f"home selection references unknown study: {selection.slug!r}"
            )
        study_result = re.sub(r"[*_`]", "", card.result)
        for number in re.findall(
            r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?![A-Za-z0-9])",
            selection.summary,
        ):
            if number not in study_result:
                raise SystemExit(
                    f"home selection {selection.slug!r} uses {number} outside "
                    "its study-index result"
                )
        route = f"/imaging/studies/{selection.slug}/"
        items.append(
            '<article class="home-work-card">'
            f'<a class="home-work-figure" href="{route}">'
            f'<img src="/assets/figures/{selection.figure}" '
            f'alt="{html.escape(selection.alt, quote=True)}"></a>'
            f'<div><h3><a href="{route}">{html.escape(card.title)}</a></h3>'
            f"<p>{html.escape(selection.summary)}</p></div>"
            "</article>"
        )
    # The platform leads: it is the only application and the only Swift/Metal
    # work here, so it is what distinguishes this portfolio from a folder of
    # studies. Full width because a dark application window inside a
    # half-width card built for light chart artwork reads as the odd one out,
    # and because five cards in two columns strand the fifth beside a hole.
    hero = HDR_FIGURES["STIMULUS_SHOT"]
    feature = (
        '<article class="home-work-card home-work-feature">'
        f'<a class="home-work-figure" href="{HDR_ROUTE}">'
        "<picture>"
        f'<source srcset="/assets/hdr/{hero.stem}.webp" type="image/webp">'
        f'<img src="{hero.display}" alt="{html.escape(hero.alt, quote=True)}" '
        f'width="{hero.width}" height="{hero.height}">'
        "</picture></a>"
        f'<div><h3><a href="{HDR_ROUTE}">HDR psychophysics platform</a></h3>'
        "<p>A macOS platform for authoring and running HDR and SDR "
        "psychophysics studies, built to keep requested stimulus state, "
        "realized renderer state, and measured output as three separate "
        "records.</p></div>"
        "</article>"
    )
    # The two things here a reader can use rather than read lead the section
    # together, then the four investigations follow. Their shared visual
    # treatment separates products from studies without turning each product
    # into a full-width row before the investigations.
    calculator = (
        '<article class="home-work-card home-work-feature">'
        f'<a class="home-work-figure" href="{COMPARATOR_ROUTE}">'
        f'<img src="{CALCULATOR_PREVIEW}" '
        f'alt="{html.escape(CALCULATOR_PREVIEW_ALT, quote=True)}" '
        'width="1200" height="630"></a>'
        f'<div><h3><a href="{COMPARATOR_ROUTE}">CAM16 and Hellwig\u2013Fairchild '
        "calculator</a></h3>"
        "<p>Enter an XYZ value and viewing conditions, then compare what CAM16 "
        "and the 2022 proposal predict. The model runs in the browser, from "
        "the same tested source as the standalone tool.</p></div>"
        "</article>"
    )
    return (
        '<div class="home-work-grid">'
        + feature
        + calculator
        + "".join(items)
        + "</div>"
    )


def hdr_figure(figure: HdrFigure) -> str:
    """Render one figure, WebP first with the PNG as the served fallback."""

    alt = html.escape(figure.alt, quote=True)
    dimensions = f'width="{figure.width}" height="{figure.height}"'
    if figure.vector:
        media = (
            f'<img src="{figure.display}" alt="{alt}" {dimensions} loading="lazy">'
        )
    else:
        media = (
            "<picture>"
            f'<source srcset="/assets/hdr/{figure.stem}.webp" type="image/webp">'
            f'<img src="{figure.display}" alt="{alt}" {dimensions} loading="lazy">'
            "</picture>"
        )
    kind = "hdr-diagram" if figure.vector else "hdr-shot"
    return (
        f'<figure class="{kind}">'
        f'<a href="{figure.display}">{media}</a>'
        f"<figcaption>{html.escape(figure.caption)}</figcaption>"
        "</figure>"
    )


def hdr_page(site_dir: Path) -> str:
    body_html = render_markdown(
        (site_dir / "hdr-platform.md").read_text(encoding="utf-8"),
        doc_dir=PurePosixPath("."),
        project=IMAGING,
    )
    for marker, figure in HDR_FIGURES.items():
        placeholder = f"<!-- {marker} -->"
        if placeholder not in body_html:
            raise SystemExit(f"HDR page placement marker disappeared: {marker}")
        rendered = hdr_figure(figure)
        if marker == "EDR_CONTRACT":
            # Correct and useful, but five fields of surface configuration is
            # not the main reading path. Behind a summary it stays available
            # to the reader who wants it and out of the way of the one who
            # came for the instrument.
            rendered = (
                '<details class="hdr-detail"><summary>How the macOS HDR '
                "surface is configured</summary>"
                "<p>Extended range needs <code>rgba16Float</code>, "
                "<code>extendedLinearDisplayP3</code>, "
                "<code>preferredDynamicRange .high</code>, a "
                "<code>contentsHeadroom</code> above 1.0, and "
                "<code>toneMapMode .never</code>.</p>"
                f"{rendered}</details>"
            )
        body_html = body_html.replace(placeholder, rendered)
    return page(
        title=f"HDR psychophysics platform · {AUTHOR}",
        description=(
            "A macOS platform for authoring and running HDR and SDR "
            "psychophysics studies, keeping requested stimulus state, renderer "
            "state, and measured output separate."
        ),
        body=(
            "<h1>HDR psychophysics platform</h1>"
            f'<div class="prose hdr">{body_html}</div>'
        ),
        canonical=HDR_ROUTE,
        nav_active="hdr",
        depth_class="hdr-page",
        # This is the route most likely to be pasted into a message or a
        # resume, and a link with no preview image renders as a bare text
        # card next to whatever else is in the feed. PNG rather than the
        # WebP beside it: link unfurlers are much less consistent about WebP.
        social_image=f"/assets/hdr/{HDR_FIGURES['STIMULUS_SHOT'].stem}.png",
        social_image_alt=HDR_FIGURES["STIMULUS_SHOT"].alt,
    )


def home_page(site_dir: Path, cards: list[Card]) -> str:
    home_md = (site_dir / "home.md").read_text(encoding="utf-8")
    body_html = render_markdown(
        home_md, doc_dir=PurePosixPath("."), project=IMAGING
    )
    replacements = {
        "<!-- PIPELINE_ART -->": profile_art(PROFILE_ASSETS["PIPELINE_ART"]),
        "<!-- SELECTED_WORK -->": selected_work(cards),
        "<!-- SPECTRAL_ART -->": profile_art(PROFILE_ASSETS["SPECTRAL_ART"]),
        "<!-- SPATIAL_ART -->": profile_art(PROFILE_ASSETS["SPATIAL_ART"]),
    }
    for marker, replacement in replacements.items():
        if marker not in body_html:
            raise SystemExit(f"home-page placement marker disappeared: {marker}")
        body_html = body_html.replace(marker, replacement)
    return page(
        title=f"{AUTHOR} · Imaging Engineering & Color Science",
        description=(
            "Camera image quality, color science, HDR/SDR research, and "
            "photographic systems work by Fernando Voltolini de Azambuja."
        ),
        body=f'<div class="prose home">{body_html}</div>',
        canonical="/",
        nav_active="home",
        depth_class="home",
        social_image="/assets/profile/digital-camera-pipeline-composite.jpg",
        social_image_alt=PROFILE_ASSETS["PIPELINE_ART"].alt,
    )


def sitemap(output: Path) -> str:
    urls = []
    for path in sorted(output.rglob("index.html")):
        route = "/" + str(path.parent.relative_to(output)).replace(".", "").strip("/")
        route = "/" if route in ("/", "//") else route.rstrip("/") + "/"
        if route == COMPARATOR_LEGACY_ROUTE:
            continue
        urls.append(f"  <url><loc>{SITE_URL}{route}</loc></url>")
    joined = "\n".join(urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{joined}\n</urlset>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--imaging",
        type=Path,
        required=True,
        help="checkout of ferazambuja/imaging-color-measurement",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="checkout of the public ferazambuja profile repository",
    )
    parser.add_argument(
        "--comparator",
        type=Path,
        required=True,
        help="checkout of ferazambuja/cam16-hellwig-comparator",
    )
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "site",
    )
    args = parser.parse_args()
    count = build(
        {"imaging": args.imaging.resolve()},
        args.profile.resolve(),
        args.comparator.resolve(),
        args.output.resolve(),
        args.site_dir.resolve(),
    )
    print(f"site build: {count} pages written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
