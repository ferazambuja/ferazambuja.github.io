# Fernando Voltolini de Azambuja — portfolio site

Source for [ferazambuja.github.io](https://ferazambuja.github.io), a portfolio
of imaging engineering, color science, photography, and research-tool work.

The site presents technical studies from
[imaging-color-measurement](https://github.com/ferazambuja/imaging-color-measurement),
the interactive [CAM16 and Hellwig–Fairchild comparator](https://github.com/ferazambuja/cam16-hellwig-comparator),
and selected owner-authored photography from the public profile repository.

## Build locally

```sh
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

git clone https://github.com/ferazambuja/imaging-color-measurement ../imaging-color-measurement
git clone https://github.com/ferazambuja/cam16-hellwig-comparator ../cam16-hellwig-comparator

./.venv/bin/python tools/build_site.py \
  --imaging ../imaging-color-measurement \
  --profile ../ferazambuja \
  --comparator ../cam16-hellwig-comparator \
  --output _site
./.venv/bin/python tools/test_site.py \
  --site _site \
  --imaging ../imaging-color-measurement \
  --profile ../ferazambuja \
  --comparator ../cam16-hellwig-comparator
```

Serve the result with `python3 -m http.server -d _site 8000` and open
<http://localhost:8000>.
