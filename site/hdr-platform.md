A macOS application for authoring and running visual psychophysics studies on
HDR and SDR displays, built as the instrument for an MS thesis in color
science.

**The question.** A psychophysics stimulus is specified in physical units —
cd/m², CIE xy, degrees of visual angle — but a display pipeline accepts pixel
values. Working space, extended-range activation, GPU composition, and OS tone
mapping all sit between the two, and any of them can change what an observer
sees while the authored numbers stay put.

**What I built.** A platform that treats requested stimulus state, realized
renderer state, and measured output as three separate objects, and keeps them
separate from study authoring through run preparation.

**The limitation that governs everything below.** Every value in these
screenshots is an authored request value. None is a measurement, a threshold,
or a fitted result.

## Authoring a stimulus in physical units

<!-- STIMULUS_SHOT -->

Each layer carries an explicit luminance in cd/m² rather than a code value —
60.0 and 95.0 for the two disks here. The inspector exposes the size mode
(normalized, degVA, or mm), the layer's study-card binding, and the display's
reported extended-range context: a 0.95× ratio against a 100 cd/m² render
white, on a panel reporting a 1,600-nit estimated cap.

That readout is on screen for a reason. On macOS, extended range is not a
single switch. It takes a coordinated five-field surface contract, and setting
the dynamic-range hint alone does not activate it — while leaving tone mapping
automatic lets the OS reshape the very stimulus under test.

## From authored units to pixels

<!-- SIGNAL_PATH -->

Chromaticity ratios are normalized in Display P3 and packed into the GPU
uniform contract separately from luminance magnitude; the two recombine only at
final composition. Keeping that split intact this far down is what makes a
requested value still identifiable when it reaches the display. A CR-250 spot
measurement enters as a third state — its own run-linked record, not a
confirmation of the first two.

## Studies are data, not code

<!-- STUDY_AUTHORING -->

A study is a deck of cards bound to a participant task. The spatial-frequency
discrimination study shown is a spatial 2AFC: 200 trials expanded
deterministically from seed 99999, side assignment balanced at 100 left and 100
right, responses mapped to clicking a stimulus. The schedule is generated rather
than hand-listed and carries a seed, a schedule ID, and a checksum, so the
sequence a participant saw can be reconstructed from the run record instead of
trusted from a description of it. Material marked *Training* is excluded from
fitting, and that exclusion travels with the data.

<!-- STUDY_LIBRARY -->

Studies are versioned records with a schema version and a declared perceptual
model — CIELAB for the SDR color and spatial studies, JzCzHz for the HDR
contrast study. The `Blocked` badge on a researcher-authored draft is the point
of the shot: the same schema validation governs it and the three bundled thesis
studies. There is no privileged path for the studies the author wrote first.

## Refusing to produce results it cannot back

<!-- RUN_READINESS -->

Readiness is evaluated before a run, not diagnosed after one. Schema and
template integrity are clear here, but the luminance envelope reads *Needs
calibration*: the study declares nine measurement targets, eight of them at
1000 cd/m², and none has a measured row behind it yet.

Three fields below that are deferred to capture rather than authored — the
measurement footprint (aperture and working distance, which decide whether spot
photometry resolves the target), the measurement method, and spatial-frequency
resolution. Each is a property of the measurement, so the platform declines to
let it be asserted in advance. Formal capture stays blocked until envelope
measurements are captured or imported; Preview and Pilot are rehearsal postures
that archive no bundle.

<!-- EDR_CONTRACT -->

## What these screenshots do not show

Every state above is a pre-formal-run state, deliberately — the gates are the
subject. No measured results, thresholds, or fitted psychometric functions
appear here, and none should be inferred from the interface values, which are
requested values throughout. The thesis manuscript's public availability is not
established here and is not claimed.
