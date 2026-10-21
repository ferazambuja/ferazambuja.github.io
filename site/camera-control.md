I built Capture Control to connect photographic capture with the work that
comes after it: inspecting original pixels, comparing images, choosing an
analysis and explaining the result. The Mac app works with compatible saved
images on its own. CameraPilot, its optional iPhone companion, adds remote
camera control and capture sequences.

<!-- ANALYSIS_APP_SHOT -->

## Inspect the image behind the number

Open compatible saved images without connecting a phone. Inspect individual
pixels, register readings and define exact regions. Histograms, channel
statistics, row and column profiles, line profiles, block maps and field
measurements help locate a difference within the image.

The app identifies the image representation used for each measurement. Decoded
Bayer RAW samples, LinearRAW/Apple ProRAW, and developed RGB have different
meanings and are kept distinct. Changing HDR/SDR viewing does not change the
selected numerical measurement plane.

## Compare images and RAW developments

Side by Side, Blink and Wipe provide visual comparison with linked navigation.
Compare two images, or supported developments of one RAW original. Each side
can have its own HDR/SDR viewing choice. Eligible inputs also support numerical
differences and selected-region comparisons.

These tools connect a visible difference with its source and region. A screen
preview remains a viewing result; it does not establish calibrated brightness
or colour accuracy.

## Choose the analysis that answers the question

| Question | Implemented tools | Inputs matter |
| --- | --- | --- |
| Does the output repeat consistently, or change with exposure? | Repeated Output Series, exposure/ISO response and reference-response views | Compatible repeated images and their exposure information |
| How do Bayer RAW values vary across frames or the field? | Bayer temporal noise, dark signal, flat field and response/PTC | Suitable Bayer RAW sequences and method-specific capture conditions |
| What happens at an edge, or between colours? | Edge/MTF, Lab comparisons and regional colour measurements | Appropriate edges, references and sampling geometry |

The result workspace links plots and tables with the selected inputs, regions
and interpretation. Saved analyses preserve their settings; compatible saved
results can be reopened for review without repeating acquisition.

## Turn results into a report and reusable data

Supported tools offer **Report + Data**, **Report Only** and **Data Only**.
Readable reports bring together images, plots, tables and method context;
numerical exports retain the fuller records and reusable jobs where supported.
Individual tables and plots can also be copied or saved.

Source images are included only when **Include Source Files** is selected and
supported. A report alone does not replace the complete data or original files.

<!-- EXPORT_APP_SHOT -->

## Add iPhone capture when the work needs it

CameraPilot lets the Mac inspect live framing, select a supported physical
lens and set exposure, white balance and focus. Take one photo directly, or
prepare a reusable Capture Sequence with per-step settings, repeats,
instructions and deliberate pauses. Single-photo settings remain separate
from sequence editing.

Prepare Capture can turn a compatible analysis method into an editable
single-photo setup or sequence. Completed originals can return to the
originating analysis draft with its method, regions and references intact.

<!-- SEQUENCE_APP_SHOT -->

Original JPEG, HEIC or DNG files are saved locally with capture metadata.
SHA-256 transfer checks verify the delivered bytes. Stop and interrupted-file
recovery help retain available originals without repeating a photograph to
recover its files.

## Native implementation and development scope

The app uses Swift, SwiftUI and AVFoundation, with native C/C++ components.
RAW support combines [LibRaw](https://www.libraw.org/) decoding with Apple's
[Core Image](https://developer.apple.com/documentation/coreimage) and
[Image I/O](https://developer.apple.com/documentation/imageio) frameworks.
I built the capture, inspection, measurement, comparison and reporting
workflows around those foundations. Format and method support depend on the
actual image representation and selected development route.

Saved-image workflows run locally without Python, a separate LibRaw
installation or an iPhone connection. The app also provides structured
commands and bundled offline help.

Capture Control is a development project with no packaged download currently
provided. The Mac deployment target is **macOS 14 or later**; optional remote
capture needs **iOS 17 or later**. Available camera formats and controls depend
on the phone and physical lens. Screenshots show development UI from build 515,
not qualification of every device, format or OS combination.
