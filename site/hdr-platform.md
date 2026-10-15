A macOS application for authoring and running visual psychophysics studies on
HDR and SDR displays, built as the instrument for an MS thesis in color
science.

I built tools for designing stimuli, arranging participant tasks and generating
repeatable trial sequences. Researchers can specify stimulus luminance, color
and size, prepare a study, and inspect the display and measurement settings
needed to run it.

A study may request a stimulus in cd/m², CIE xy and degrees of visual angle,
while the display accepts pixels. The working color space, GPU composition and
OS tone mapping can change the light an observer sees. The app keeps the
requested settings, renderer state and instrument measurements identifiable
through that process so they can be compared.

## Authoring a stimulus in physical units

<!-- STIMULUS_SHOT -->

Each layer has a requested luminance in cd/m²: 60.0 and 95.0 for the two disks
shown here. The inspector also exposes the size mode (normalized, degVA, or
mm), the associated study card and the display context. This example's 95.0
cd/m² request is 0.95× a 100 cd/m² render white; the panel reports a 1,600-nit
estimated cap. These are authored settings and reported display information,
not measured light output or participant results.

For an HDR study, the renderer must enable extended range and control tone
mapping so the OS does not reshape the intended luminance relationships. The
app configures the five related surface fields together; their exact settings
are shown in the technical detail below.

## From authored units to pixels

<!-- SIGNAL_PATH -->

Color and luminance need separate control when a study changes one while
holding the other fixed. The renderer normalizes chromaticity ratios in
Display P3 and carries them separately from luminance through the GPU, combining
them at final composition. A CR-250 spot measurement can then be compared with
the requested stimulus and renderer state as its own run-linked observation.

## Design and repeat a trial sequence

<!-- STUDY_AUTHORING -->

A study combines stimulus cards with a participant task. The spatial-frequency
example uses a two-alternative forced-choice task, or 2AFC: the participant
responds by clicking one of two stimuli. The app expands the cards into a
schedule of 200 trials, balanced at 100 left and 100 right assignments.

Saving the generated schedule and its random seed makes the trial sequence
reconstructable from the run record. The example uses seed 99999. Trials marked
*Training* are excluded from fitting participant responses, keeping practice
separate from the analysis.

<!-- STUDY_LIBRARY -->

The study library includes three bundled thesis studies and a researcher-authored
draft. Each study declares its perceptual model: CIELAB for the SDR color and
spatial studies, JzCzHz for the HDR contrast study. New studies use the same
validation as the bundled ones, so their authoring and readiness checks remain
part of the workflow.

## Check stimulus calibration before a study

<!-- RUN_READINESS -->

Before formal capture, the app checks that the study's requested luminances
have corresponding measurements. The example reads *Needs calibration*: it
declares nine measurement targets, eight at 1000 cd/m², with no measured rows
recorded yet. Formal capture remains blocked until those measurements are
captured or imported. Preview and Pilot provide rehearsal without archiving a
formal bundle.

The measurement footprint (aperture and working distance), measurement method
and spatial-frequency resolution are supplied at capture. These describe how
the instrument samples the stimulus and whether it can resolve the intended
target, so the preparation view leaves them for the measurement setup.

<!-- EDR_CONTRACT -->
