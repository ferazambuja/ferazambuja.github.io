# Reflective-display case study

This directory contains the curated source for the reflective color-display
portfolio project. The overview introduces the full story; the topic pages
provide progressively deeper explanations and representative figures.

## Content map

| Route | Purpose |
| --- | --- |
| `/reflective-color-display/` | Visual overview of the display, ICC experiment, pattern findings, renderer and prediction limits |
| `pattern-behavior/` | Tested pixel constructions, instrument checks, reading order, spectra and methods |
| `prediction/` | Defined forecast tests, transfer limits and prediction versus requested color |
| `renderer/` | Offline image-to-native-state pipeline and software comparisons |
| `icc/` | Experimental profile method, artwork examples and measured 133-color comparison |

## Editing and generated files

- Edit the narrative HTML files and shared `story.css` / `story.js` here.
- Do not hand-edit measurement JSON or `snapshot.json`.
- The retired `measurements/` explorer and its data stay in source history but
  are excluded from the published snapshot. The shared
  `measurement-investigation.json` remains an input to the curated pattern charts.
- `fragment-routes.json` preserves useful bookmarks from the earlier
  single-page version.
- Build into a separate output directory. `_site/` is generated output, not an
  editorial source.
- Run `tools/refresh_reflective_snapshot.py --write` after reviewing narrative
  changes. The tool updates only its editorial allowlist and refuses changes to
  pinned measurement or image files.

The Great Wave comparison is generated from two already-selected 800 × 480
native-state planes. Both are visualized with the same measured-media-relative
six-color palette; this changes only the preview colors, not a single logical
state. To verify the current previews, or deliberately regenerate them after
reviewing the selected inputs:

```sh
.venv/bin/python tools/render_reflective_renderer_previews.py \
  --comparison-dir /path/to/retained-comparison
.venv/bin/python tools/render_reflective_renderer_previews.py \
  --comparison-dir /path/to/retained-comparison --write
```

The Coffee and Chelsea gallery uses the interpreted source frames and matched
Floyd–Steinberg outputs from the existing eight-image comparison, with the same
visualization palette. To include it in either verification or regeneration,
add `--gallery-completion-dir /path/to/completion` and
`--gallery-analysis-dir /path/to/analysis`. The tool verifies the saved reports
and input files before exporting the images; it does not rerun the renderers.

## Local verification

From the repository root:

```sh
.venv/bin/python tools/refresh_reflective_snapshot.py
.venv/bin/python tools/test_reflective_color.py

preview_dir=$(mktemp -d /tmp/reflective-portfolio-review.XXXXXX)
.venv/bin/python tools/build_site.py \
  --imaging ../imaging-color-measurement \
  --profile ../ferazambuja \
  --comparator ../cam16-hellwig-comparator \
  --output "$preview_dir/site"
.venv/bin/python tools/serve_site.py --site "$preview_dir/site" --port 8012
```

Open `http://127.0.0.1:8012/reflective-color-display/` and check the overview,
topic navigation, renderer images, pattern charts, desktop layout and phone
layout.
