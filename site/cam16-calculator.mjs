import {
  BROWSER_API_VERSION,
  IMPLEMENTATION_VERSION,
  compareModelsWithDiagnostics,
} from "/assets/cam16_compare.mjs";

const EXPECTED_API = "cam16-browser-api-v1";
const form = document.querySelector("#cam16-calculator");
const status = document.querySelector("#calculator-status");
const hueNote = document.querySelector("#calculator-hue-note");
const version = document.querySelector("[data-implementation-version]");
const resultTargets = Array.from(document.querySelectorAll("[data-model][data-correlate]"));

if (!form || !status || !hueNote || !version || resultTargets.length !== 12) {
  throw new Error("calculator markup does not match its controller");
}
if (BROWSER_API_VERSION !== EXPECTED_API) {
  throw new Error(`unsupported browser model API: ${BROWSER_API_VERSION}`);
}
if (version.dataset.implementationVersion !== IMPLEMENTATION_VERSION) {
  throw new Error("Python and browser implementation versions do not match");
}

function numberFrom(name) {
  const control = form.elements.namedItem(name);
  const value = control?.valueAsNumber;
  if (!Number.isFinite(value)) {
    throw new TypeError(`${name} must be a finite number`);
  }
  return value;
}

function shown(value) {
  return Number(value.toPrecision(6)).toString();
}

function clearResults() {
  for (const target of resultTargets) {
    target.textContent = "—";
  }
}

function calculate() {
  try {
    const result = compareModelsWithDiagnostics({
      XYZ: [numberFrom("x"), numberFrom("y"), numberFrom("z")],
      XYZ_w: [
        numberFrom("white_x"),
        numberFrom("white_y"),
        numberFrom("white_z"),
      ],
      L_A: numberFrom("la"),
      Y_b: numberFrom("yb"),
      surround: form.elements.namedItem("surround").value,
      normalize: form.elements.namedItem("normalize").checked,
    });
    for (const target of resultTargets) {
      const model = target.dataset.model;
      const correlate = target.dataset.correlate;
      if (!result.hue_diagnostics.hue_resolved && correlate === "h") {
        target.textContent = "n/a";
      } else if (
        !result.hue_diagnostics.hue_resolved &&
        ["C", "M", "s"].includes(correlate)
      ) {
        target.textContent = "~0";
      } else {
        target.textContent = shown(result.models[model][correlate]);
      }
    }
    status.classList.remove("is-error");
    if (result.hue_diagnostics.hue_resolved) {
      status.textContent =
        "Calculated locally in your browser. No input data was sent anywhere.";
      hueNote.textContent =
        "Hue is shown because the opponent response is large enough to resolve a direction.";
    } else {
      status.textContent =
        "Calculated locally. Hue is unresolved for this stimulus and viewing condition.";
      hueNote.textContent =
        "Hue shows n/a and the near-zero C, M, and s values show ~0 because the opponent direction is too close to floating-point cancellation to report reliably.";
    }
  } catch (error) {
    clearResults();
    status.classList.add("is-error");
    status.textContent = `Cannot calculate: ${error.message}`;
    hueNote.textContent = "Correct the inputs and calculate again.";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  calculate();
});
form.addEventListener("reset", () => setTimeout(calculate, 0));

calculate();
