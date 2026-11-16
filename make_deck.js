/**
 * Pitch deck generator for the C-UAS layered sensing framework.
 *
 * Every number in this deck is produced by run_demo.py / make_slide_figures.py.
 * If a figure is regenerated, re-run this script so the text and the graphics
 * cannot drift apart.
 */
const pptx = new (require("pptxgenjs"))();
const path = require("path");

const R = path.join(__dirname, "reports");
const S = path.join(R, "slides");

// ---------------------------------------------------------------- palette
const MIDNIGHT = "0E2033";
const DEEP = "065A82";
const TEAL = "1C7293";
const AMBER = "E8871E";
const RED = "B23A48";
const GREEN = "2C5F2D";
const INK = "12263A";
const MUTED = "5C7080";
const TINT = "EEF4F8";
const WHITE = "FFFFFF";

const H_FONT = "Cambria";
const B_FONT = "Calibri";

const W = 13.3;
const H = 7.5;
const M = 0.62;
const CW = W - 2 * M;

pptx.layout = "LAYOUT_WIDE";
pptx.author = "C-UAS layered sensing study";
pptx.title = "Layered C-UAS Sensing for Maritime Port Defence";

// ---------------------------------------------------------------- helpers
function darkSlide() {
  const s = pptx.addSlide();
  s.background = { color: MIDNIGHT };
  return s;
}

function lightSlide() {
  const s = pptx.addSlide();
  s.background = { color: WHITE };
  return s;
}

/** Kicker + title block used on every content slide. */
function heading(s, kicker, title, opts) {
  const o = opts || {};
  s.addText(kicker.toUpperCase(), {
    x: M, y: 0.34, w: CW, h: 0.26,
    fontFace: B_FONT, fontSize: 11.5, bold: true, color: AMBER,
    charSpacing: 1.6, margin: 0,
  });
  s.addText(title, {
    x: M, y: 0.62, w: o.tw || CW, h: 0.72,
    fontFace: H_FONT, fontSize: o.size || 30, bold: true, color: INK,
    margin: 0, valign: "top",
  });
}

/** The repeated visual motif: a numbered layer chip. */
function layerChip(s, n, x, y) {
  s.addShape(pptx.ShapeType.ellipse, {
    x: x, y: y, w: 0.46, h: 0.46, fill: { color: DEEP },
  });
  s.addText(String(n), {
    x: x, y: y, w: 0.46, h: 0.46,
    fontFace: B_FONT, fontSize: 17, bold: true, color: WHITE,
    align: "center", valign: "middle", margin: 0,
  });
}

/** Big-number statistic tile. */
function statTile(s, x, y, w, value, label, colour, sub) {
  s.addShape(pptx.ShapeType.roundRect, {
    x: x, y: y, w: w, h: sub ? 1.72 : 1.42,
    fill: { color: TINT }, rectRadius: 0.08,
  });
  s.addText(value, {
    x: x, y: y + 0.12, w: w, h: 0.66,
    fontFace: H_FONT, fontSize: 34, bold: true, color: colour || DEEP,
    align: "center", valign: "middle", margin: 0,
  });
  s.addText(label, {
    x: x + 0.12, y: y + 0.78, w: w - 0.24, h: 0.42,
    fontFace: B_FONT, fontSize: 12, color: INK,
    align: "center", valign: "top", margin: 0,
  });
  if (sub) {
    s.addText(sub, {
      x: x + 0.12, y: y + 1.2, w: w - 0.24, h: 0.42,
      fontFace: B_FONT, fontSize: 10.5, italic: true, color: MUTED,
      align: "center", valign: "top", margin: 0,
    });
  }
}

/** Bulleted body text. */
function bullets(s, items, o) {
  s.addText(
    items.map((t, i) => ({
      text: t,
      options: {
        bullet: true,
        breakLine: i !== items.length - 1,
        paraSpaceAfter: o.gap === undefined ? 7 : o.gap,
      },
    })),
    {
      x: o.x, y: o.y, w: o.w, h: o.h,
      fontFace: B_FONT, fontSize: o.size || 14, color: o.color || INK,
      valign: "top", margin: 0, lineSpacingMultiple: 1.06,
    }
  );
}

function caption(s, text, y) {
  s.addText(text, {
    x: M, y: y, w: CW, h: 0.4,
    fontFace: B_FONT, fontSize: 11.5, italic: true, color: MUTED,
    margin: 0, valign: "top",
  });
}

function footer(s, n) {
  s.addText("Layered C-UAS sensing  ·  simulation & design-analysis framework", {
    x: M, y: H - 0.44, w: CW - 0.6, h: 0.28,
    fontFace: B_FONT, fontSize: 9, color: MUTED, margin: 0,
  });
  s.addText(String(n), {
    x: W - M - 0.5, y: H - 0.44, w: 0.5, h: 0.28,
    fontFace: B_FONT, fontSize: 9, color: MUTED, align: "right", margin: 0,
  });
}

// ================================================================ 1 title
(() => {
  const s = darkSlide();
  s.addShape(pptx.ShapeType.ellipse, {
    x: 9.4, y: -1.9, w: 6.4, h: 6.4,
    fill: { color: DEEP, transparency: 72 },
  });
  s.addShape(pptx.ShapeType.ellipse, {
    x: 10.6, y: -0.7, w: 4.0, h: 4.0,
    fill: { color: TEAL, transparency: 62 },
  });

  s.addText("COUNTER-UAS  ·  MARITIME PORT DEFENCE", {
    x: M, y: 1.62, w: 8.6, h: 0.3,
    fontFace: B_FONT, fontSize: 12.5, bold: true, color: AMBER,
    charSpacing: 2.0, margin: 0,
  });
  s.addText("Layered Sensing Analysis\nfor Port Air Defence", {
    x: M, y: 2.02, w: 8.8, h: 1.85,
    fontFace: H_FONT, fontSize: 42, bold: true, color: WHITE,
    margin: 0, lineSpacingMultiple: 1.0,
  });
  s.addText(
    "A physics-derived simulation framework that turns detection theory into a " +
      "siting decision: where sensors go, and where the coverage gaps are.",
    {
      x: M, y: 4.0, w: 8.4, h: 0.9,
      fontFace: B_FONT, fontSize: 15.5, color: "C9D6E0", margin: 0,
      lineSpacingMultiple: 1.14,
    }
  );

  const chips = [
    ["Detection", "radar range budget"],
    ["Classification", "micro-Doppler"],
    ["Fusion", "IMM tracking"],
    ["System", "coverage & siting"],
  ];
  chips.forEach(([t, d], i) => {
    const x = M + i * 2.28;
    s.addText(`0${i + 1}`, {
      x: x, y: 5.22, w: 2.1, h: 0.3,
      fontFace: H_FONT, fontSize: 15, bold: true, color: AMBER, margin: 0,
    });
    s.addText(t, {
      x: x, y: 5.52, w: 2.1, h: 0.28,
      fontFace: B_FONT, fontSize: 13, bold: true, color: WHITE, margin: 0,
    });
    s.addText(d, {
      x: x, y: 5.79, w: 2.1, h: 0.28,
      fontFace: B_FONT, fontSize: 10.5, color: "8FA6B8", margin: 0,
    });
  });

  s.addText(
    "Scope: sensing, detection, classification and tracking performance. " +
      "No effector, jamming or intercept parameters.",
    {
      x: M, y: 6.62, w: 11.4, h: 0.4,
      fontFace: B_FONT, fontSize: 10.5, italic: true, color: "7E93A5",
      margin: 0,
    }
  );
  s.addNotes(
    "Open by naming the deliverable: this is an engineering analysis tool, not " +
      "a brochure. State the scope boundary up front - sensing only, no " +
      "effector parameters - so nobody has to ask."
  );
})();

// ================================================================ 2 problem
(() => {
  const s = lightSlide();
  heading(s, "The problem", "A port's existing radar cannot see a small quadcopter");

  statTile(s, M, 1.62, 3.86, "0.01 m²",
    "Radar cross section of a small quadcopter",
    DEEP, "100x smaller than a light aircraft");
  statTile(s, M + 4.12, 1.62, 3.86, "2.95 km",
    "Range at which an existing coastal surveillance radar holds Pd = 0.9",
    RED, "far inside the port's own approaches");
  statTile(s, M + 8.24, 1.62, 3.86, "4.9 %",
    "Of the seaward approach sector that radar actually covers",
    RED, "2 of 4 critical assets unprotected");

  s.addText("Why this is not solved by adding power", {
    x: M, y: 3.62, w: 6.0, h: 0.36,
    fontFace: B_FONT, fontSize: 15, bold: true, color: INK, margin: 0,
  });
  bullets(s, [
    "Radar range grows only as the fourth root of SNR. Doubling range needs 12 dB, sixteen times the power-aperture product.",
    "A boat-launched multirotor bypasses every land-side perimeter control the port has.",
    "Over water, sea-surface multipath can cost 20 dB in a null, so the honest coverage figure is worse than a free-space budget suggests.",
    "Birds outnumber drones. A system that cannot reject gulls gets switched off by its operators.",
  ], { x: M, y: 4.06, w: 6.0, h: 2.6, size: 13.5, gap: 9 });

  s.addShape(pptx.ShapeType.roundRect, {
    x: M + 6.5, y: 3.62, w: CW - 6.5, h: 3.0,
    fill: { color: MIDNIGHT }, rectRadius: 0.08,
  });
  s.addText("What the framework answers", {
    x: M + 6.9, y: 3.88, w: CW - 7.3, h: 0.34,
    fontFace: B_FONT, fontSize: 14.5, bold: true, color: AMBER, margin: 0,
  });
  bullets(s, [
    "What detection range is physically available, per sensor and per target?",
    "Which of those detections can be told apart from a bird?",
    "Can the track survive a manoeuvre well enough to be actioned?",
    "Given candidate masts, where do sensors go, and what is still uncovered?",
  ], { x: M + 6.9, y: 4.32, w: CW - 7.3, h: 2.2, size: 13, color: "D8E3EC", gap: 10 });

  footer(s, 2);
  s.addNotes(
    "The three tiles are the problem statement in numbers. The right-hand box " +
      "reframes it as four answerable questions - which is the structure of the " +
      "rest of the deck."
  );
})();

// ================================================================ 3 architecture
(() => {
  const s = lightSlide();
  heading(s, "Architecture", "Four layers, each a physical model, not a fitted curve");

  const rows = [
    [1, "Detection", "Noise-limited radar chain: SNR = PtG²λ²σF⁴n / ((4π)³R⁴kTsB·F·L). Detection probability from the exact square-law detector distribution, Marcum Q and Swerling, not assumed.", "cuas/radar.py\ncuas/propagation.py"],
    [2, "Classification", "Rotor return synthesised from distributed blade scatterers, then interpretable spectrogram features into an SVM. Cross-validated, with a speed-feature ablation.", "cuas/microdoppler.py\ncuas/classify.py"],
    [3, "Fusion", "Kalman and IMM estimators on a shared 6-state model, validated by position RMSE and NEES consistency over Monte-Carlo runs.", "cuas/tracking.py"],
    [4, "System", "Per-sensor Pd fused as 1 − Π(1 − Pdᵢ), mapped over a 2-D grid, then greedy maximum-coverage mast selection against asset stand-off rings.", "cuas/system.py\ncuas/scenarios.py"],
  ];

  let y = 1.58;
  rows.forEach(([n, name, body, mod]) => {
    layerChip(s, n, M, y + 0.04);
    s.addText(name, {
      x: M + 0.66, y: y, w: 2.3, h: 0.32,
      fontFace: B_FONT, fontSize: 15, bold: true, color: INK, margin: 0,
    });
    s.addText(mod, {
      x: M + 0.66, y: y + 0.32, w: 2.6, h: 0.5,
      fontFace: "Courier New", fontSize: 8.5, color: MUTED, margin: 0,
      lineSpacingMultiple: 1.02,
    });
    s.addText(body, {
      x: M + 3.3, y: y - 0.02, w: CW - 3.3, h: 1.0,
      fontFace: B_FONT, fontSize: 13, color: INK, margin: 0,
      valign: "top", lineSpacingMultiple: 1.08,
    });
    y += 1.22;
  });

  s.addShape(pptx.ShapeType.roundRect, {
    x: M, y: 6.28, w: CW, h: 0.56,
    fill: { color: TINT }, rectRadius: 0.06,
  });
  s.addText(
    "One command reproduces every number and figure in this deck:   python run_demo.py   " +
      "(114 s, writes reports/*.png and results.json)",
    {
      x: M + 0.2, y: 6.28, w: CW - 0.4, h: 0.56,
      fontFace: B_FONT, fontSize: 12, color: INK, valign: "middle", margin: 0,
    }
  );
  footer(s, 3);
  s.addNotes(
    "Emphasise the last line: reproducibility is the difference between an " +
      "analysis tool and a slide."
  );
})();

// ================================================================ 4 layer 1
(() => {
  const s = lightSlide();
  heading(s, "Layer 1: detection", "The σ^(1/4) law drives the design", { tw: 8.6 });
  layerChip(s, 1, W - M - 0.5, 0.62);

  s.addImage({ path: path.join(S, "range_vs_rcs.png"), x: M, y: 1.5, w: 7.6, h: 4.72 });

  const bx = M + 7.9;
  const bw = CW - 7.9;
  statTile(s, bx, 1.5, bw, "18.5 dB", "SNR needed for 2.9x the range", AMBER);
  s.addText("How that SNR is bought", {
    x: bx, y: 3.12, w: bw, h: 0.32,
    fontFace: B_FONT, fontSize: 14, bold: true, color: INK, margin: 0,
  });
  bullets(s, [
    "+12 dB two-way from 36 dBi aperture gain instead of 30 dBi",
    "~8 dB from a 512-pulse dwell: a staring array does not spend its time rotating",
    "Neither is exotic; both are ordinary design choices",
  ], { x: bx, y: 3.5, w: bw, h: 1.8, size: 12.5, gap: 9 });

  s.addShape(pptx.ShapeType.roundRect, {
    x: bx, y: 5.34, w: bw, h: 0.9,
    fill: { color: TINT }, rectRadius: 0.06,
  });
  s.addText([
    { text: "Validation:  ", options: { bold: true } },
    { text: "the closed-form range equation and the exact Pd solve agree to 1.2 % (2.99 vs 2.95 km)." },
  ], {
    x: bx + 0.16, y: 5.34, w: bw - 0.32, h: 0.9,
    fontFace: B_FONT, fontSize: 11.5, color: INK, valign: "middle", margin: 0,
  });

  caption(s, "Pfa = 10⁻⁶, Pd = 0.9, non-fluctuating (Swerling 0) target, clear air. Required SNR cross-checked against Albersheim's inversion.", 6.42);
  footer(s, 4);
  s.addNotes(
    "The point to land: because R goes as SNR^(1/4), incremental power is a " +
      "losing strategy and aperture plus dwell is the winning one. The 1.2 % " +
      "cross-check is there to show two independent paths agree."
  );
})();

// ================================================================ 5 propagation
(() => {
  const s = lightSlide();
  heading(s, "Maritime propagation", "Over water, propagation dominates the error", { tw: 9.6 });

  s.addImage({ path: path.join(S, "multipath.png"), x: M, y: 1.52, w: 7.5, h: 4.47 });

  const bx = M + 7.85;
  const bw = CW - 7.85;
  s.addText("Why this matters for a port", {
    x: bx, y: 1.56, w: bw, h: 0.34,
    fontFace: B_FONT, fontSize: 15, bold: true, color: INK, margin: 0,
  });
  bullets(s, [
    "Direct and sea-reflected rays interfere, producing a lobed vertical pattern: F enters SNR as F⁴, so +12 dB at a peak and −20 dB in a null.",
    "Detection is therefore not monotonic in range: a target can be lost as it closes.",
    "Surface roughness suppresses the coherent reflection, so sea state changes the lobe structure. Modelled via the Ament factor.",
    "Also included: ITU-R gaseous and rain attenuation, and the 4/3-Earth radar horizon that hard-limits geometry regardless of power.",
  ], { x: bx, y: 1.98, w: bw, h: 3.16, size: 12.5, gap: 10 });

  s.addShape(pptx.ShapeType.roundRect, {
    x: bx, y: 5.24, w: bw, h: 0.78,
    fill: { color: MIDNIGHT }, rectRadius: 0.06,
  });
  s.addText("This was entirely absent from the first prototype: it was the largest single omission for a maritime study.", {
    x: bx + 0.16, y: 5.24, w: bw - 0.32, h: 0.78,
    fontFace: B_FONT, fontSize: 11.5, color: "D8E3EC", valign: "middle", margin: 0,
  });

  caption(s, "Two-ray model with Ament rough-surface factor and spherical-Earth divergence; radar mast 25 m, sea state 3.", 6.42);
  footer(s, 5);
  s.addNotes(
    "This is the slide that shows domain judgement rather than textbook " +
      "recall: the maritime case has a dominant effect that a generic radar " +
      "model misses completely."
  );
})();

// ================================================================ 6 signatures
(() => {
  const s = lightSlide();
  heading(s, "Layer 2: classification", "A rotor writes a signature a bird cannot", { tw: 8.8 });
  layerChip(s, 2, W - M - 0.5, 0.62);

  s.addImage({ path: path.join(S, "signatures.png"), x: M, y: 1.5, w: 8.5, h: 3.57 });

  const bx = M + 8.8;
  const bw = CW - 8.8;
  bullets(s, [
    "Blades are modelled as distributed point scatterers, so the return has the real structure: body line, symmetric sidebands, periodic flashes.",
    "Blade-tip Doppler 4616 Hz analytic → 8320 Hz measured two-sided extent, 90% of theory.",
    "Bird extent is 352 Hz, a 23x separation.",
  ], { x: bx, y: 1.56, w: bw, h: 3.4, size: 12.5, gap: 10 });

  s.addShape(pptx.ShapeType.roundRect, {
    x: M, y: 5.3, w: CW, h: 0.94,
    fill: { color: TINT }, rectRadius: 0.07,
  });
  s.addText([
    { text: "Bug found and fixed:  ", options: { bold: true, color: RED } },
    { text: "the prototype's phase-modulation term was short by a factor of 2π, which collapsed the spectrogram into static horizontal lines. " },
    { text: "The signature above is what the corrected model produces.", options: { italic: true } },
  ], {
    x: M + 0.2, y: 5.3, w: CW - 0.4, h: 0.94,
    fontFace: B_FONT, fontSize: 12.5, color: INK, valign: "middle", margin: 0,
  });

  caption(s, "X-band, 20 dB SNR, 0.5 s dwell; common 45 dB display scale across both panels.", 6.46);
  footer(s, 6);
  s.addNotes(
    "Say the analytic-vs-measured check out loud - it is the evidence that the " +
      "simulator is right rather than merely plausible."
  );
})();

// ================================================================ 7 classifier
(() => {
  const s = lightSlide();
  heading(s, "Layer 2: measured performance", "0 % false alarms on birds, cross-validated", { tw: 9.0 });
  layerChip(s, 2, W - M - 0.5, 0.62);

  s.addImage({ path: path.join(S, "..", "classifier.png"),
               x: 1.23, y: 1.46, w: 10.85, h: 3.6 });

  statTile(s, M, 5.36, 3.86, "93.3 %",
    "5-fold cross-validated accuracy, speed feature removed", DEEP);
  statTile(s, M + 4.12, 5.36, 3.86, "0.9996",
    "UAS-vs-bird AUC on signature features alone", DEEP);
  statTile(s, M + 8.24, 5.36, 3.86, "100 %",
    "Bird recall, not one bird called a UAS", GREEN);

  footer(s, 7);
  s.addNotes(
    "Two honesty points to make explicitly. First, every prediction comes from " +
      "cross_val_predict, so no number is training accuracy. Second, the " +
      "ablation: permutation importance showed bulk speed carrying part of the " +
      "decision, so the speed feature was removed and re-scored - it costs only " +
      "0.7 points, so the result rests on the signature. Remaining confusion is " +
      "multirotor vs fixed-wing, and both are UAS."
  );
})();

// ================================================================ 8 tracking
(() => {
  const s = lightSlide();
  heading(s, "Layer 3: fusion", "Useful tracks need honest uncertainty", { tw: 9.4 });
  layerChip(s, 3, W - M - 0.5, 0.62);

  s.addImage({ path: path.join(S, "tracking.png"), x: M, y: 1.5, w: 8.2, h: 3.23 });

  const bx = M + 8.5;
  const bw = CW - 8.5;
  s.addText("NEES: the consistency test", {
    x: bx, y: 1.54, w: bw, h: 0.32,
    fontFace: B_FONT, fontSize: 15, bold: true, color: INK, margin: 0,
  });
  bullets(s, [
    "A correctly tuned filter has mean NEES equal to the state dimension, here 6.",
    "The single-model filter scores 107: it is ~18x over-confident during the turn.",
    "That gap, not the RMSE, is how real trackers lose targets: the gate is drawn far too small.",
    "The IMM scores 3.2 and stays consistent.",
  ], { x: bx, y: 1.94, w: bw, h: 2.9, size: 12.5, gap: 10 });

  // Results table
  const rows = [
    [{ text: "Filter", options: { bold: true } }, { text: "Position RMSE", options: { bold: true } }, { text: "Mean NEES", options: { bold: true } }, { text: "Verdict", options: { bold: true } }],
    ["Single-model KF", "4.57 ± 0.26 m", "106.8", "over-confident"],
    ["IMM (CV + CA)", "2.94 ± 0.15 m", "3.21", "consistent"],
  ];
  s.addTable(rows, {
    x: M, y: 4.98, w: 12.06,
    colW: [3.4, 3.2, 2.4, 3.06],
    fontFace: B_FONT, fontSize: 13, color: INK,
    border: { type: "solid", pt: 0.5, color: "D5DEE6" },
    fill: { color: WHITE },
    rowH: 0.3, valign: "middle",
  });

  s.addText("36 % lower position RMSE, and a mode-probability output that doubles as a manoeuvre alarm.", {
    x: M, y: 6.14, w: CW, h: 0.32,
    fontFace: B_FONT, fontSize: 12.5, bold: true, color: DEEP, margin: 0,
  });
  caption(s, "200 Monte-Carlo runs, σ_meas = 4 m, dt = 0.1 s; 18 m/s transit with a 25°/s turn at t = 15–22 s.", 6.5);
  footer(s, 8);
  s.addNotes(
    "The RMSE improvement is the easy number. The NEES argument is the one that " +
      "shows tracking maturity - most people never check filter consistency."
  );
})();

// ================================================================ 9 coverage
(() => {
  const s = lightSlide();
  heading(s, "Layer 4: the answer", "Can the port be covered? Three configurations", { tw: 11.4 });
  layerChip(s, 4, W - M - 0.5, 0.62);

  s.addImage({ path: path.join(R, "coverage_comparison.png"),
               x: 0.91, y: 1.3, w: 11.48, h: 4.3 });

  const rows = [
    [{ text: "Configuration", options: { bold: true } }, { text: "Sector covered at Pd ≥ 0.9", options: { bold: true } }, { text: "Gap area", options: { bold: true } }, { text: "Assets held", options: { bold: true } }],
    ["A: existing surveillance radar, 1 site", "4.9 %", "436 km²", "2 / 4"],
    ["B: dedicated C-UAS radar, 1 site", "30.3 %", "320 km²", "4 / 4"],
    ["C: layered suite, 3 optimised sites", "54.5 %", "209 km²", "4 / 4"],
  ];
  s.addTable(rows, {
    x: M, y: 5.7, w: 12.06,
    colW: [4.9, 3.0, 2.0, 2.16],
    fontFace: B_FONT, fontSize: 11.5, color: INK,
    border: { type: "solid", pt: 0.5, color: "D5DEE6" },
    fill: { color: WHITE },
    rowH: 0.27, valign: "middle",
  });
  footer(s, 9);
  s.addNotes(
    "This is the deck's centre of gravity. Walk left to right: the port's " +
      "existing radar holds 2 of 4 assets; a dedicated sensor on the same mast " +
      "holds all 4 but only 30 % of the sector; three sited nodes reach 54 %. " +
      "The recommendation comes out of the model, not out of a brochure."
  );
})();

// ================================================================ 10 siting
(() => {
  const s = lightSlide();
  heading(s, "Layer 4: siting", "Where the next sensor goes, and when to stop", { tw: 10.4 });
  layerChip(s, 4, W - M - 0.5, 0.62);

  s.addImage({ path: path.join(S, "siting_gain.png"), x: M, y: 1.52, w: 7.5, h: 4.4 });

  const bx = M + 7.85;
  const bw = CW - 7.85;
  bullets(s, [
    "Greedy maximum-coverage selection over 9 candidate masts, each carrying its own height, so the objective trades height (horizon, lobe structure) against position.",
    "Marginal gain falls monotonically: +36.3, +9.3, +8.8, then +1.7, +1.7.",
    "Sites 4 and 5 add 1.7 points each. Three nodes is the value point, and the model says so rather than the vendor.",
    "Maximum coverage is submodular, so greedy carries the standard (1 − 1/e) ≈ 63 % approximation guarantee.",
  ], { x: bx, y: 1.58, w: bw, h: 3.9, size: 12.5, gap: 10 });

  s.addShape(pptx.ShapeType.roundRect, {
    x: bx, y: 5.5, w: bw, h: 0.5,
    fill: { color: TINT }, rectRadius: 0.06,
  });
  s.addText("Selected: channel entrance → east breakwater → west breakwater", {
    x: bx + 0.14, y: 5.5, w: bw - 0.28, h: 0.5,
    fontFace: B_FONT, fontSize: 11, bold: true, color: DEEP,
    valign: "middle", margin: 0,
  });

  caption(s, "Tie-break on minimum Pd over each asset's stand-off ring: a healthy sector average with one exposed asset is not an acceptable answer.", 6.28);
  footer(s, 10);
  s.addNotes(
    "The commercial hook: this tells a customer how many sensors to buy and " +
      "where, including when to stop. That is a procurement decision, not a " +
      "physics result."
  );
})();

// ================================================================ 11 rigour
(() => {
  const s = lightSlide();
  heading(s, "Engineering rigour", "Five defects found and fixed while building this");

  const rows = [
    [{ text: "What was wrong", options: { bold: true } }, { text: "Why it mattered", options: { bold: true } }, { text: "Fix", options: { bold: true } }],
    ["Detection threshold was an assumed constant (Pmin = 10⁻¹³ W)", "No derivation: the range figure could not be defended", "Full receiver noise budget kTsB·F·L; Pd from the exact detector distribution"],
    ["Micro-Doppler phase term short by 2π", "Spectrogram collapsed to static lines; no rotor signature at all", "Scatterer-based rotor model, validated against analytic tip Doppler"],
    ["bw_99 measured the noise floor at low SNR", "The key feature carried no information exactly where classification is hardest", "Robust median floor subtracted first"],
    ["Modulation rate aliased above 130 Hz by the STFT hop", "Multirotor blade rates are 130–450 Hz: the feature was folding them", "Estimated from the full-rate amplitude envelope"],
    ["No validation anywhere", "One track on one noise realisation proves nothing", "Monte-Carlo RMSE + NEES; cross-validated classification with ablation"],
  ];
  s.addTable(rows, {
    x: M, y: 1.56, w: 12.06,
    colW: [3.7, 4.0, 4.36],
    fontFace: B_FONT, fontSize: 11.5, color: INK,
    border: { type: "solid", pt: 0.5, color: "D5DEE6" },
    fill: { color: WHITE },
    valign: "middle", rowH: 0.66,
  });

  s.addShape(pptx.ShapeType.roundRect, {
    x: M, y: 5.76, w: CW, h: 0.82,
    fill: { color: TINT }, rectRadius: 0.07,
  });
  s.addText("Fixing the two classifier bugs moved accuracy from 88 % to 94 %, and the bird false-alarm rate at 95 % detection from 64 % to 0 %.", {
    x: M + 0.2, y: 5.76, w: CW - 0.4, h: 0.82,
    fontFace: B_FONT, fontSize: 13, bold: true, color: DEEP,
    valign: "middle", margin: 0,
  });
  footer(s, 11);
  s.addNotes(
    "This slide is the competence argument. Anyone can run a textbook equation; " +
      "finding a 2π error in your own model and a noise-floor artefact in your " +
      "own feature is the part that is hard to fake."
  );
})();

// ================================================================ 12 limits
(() => {
  const s = lightSlide();
  heading(s, "Stated limits", "What this does not yet claim");

  s.addText(
    "Every limitation below is documented in the repository rather than left for a reviewer to find.",
    {
      x: M, y: 1.5, w: CW, h: 0.32,
      fontFace: B_FONT, fontSize: 13, italic: true, color: MUTED, margin: 0,
    }
  );

  const cards = [
    ["Blade rate is not measured", "Two estimators were built and rejected rather than shipped: a harmonic product spectrum lands on integer multiples, and Doppler-spectrum autocorrelation is right for a 3-blade rotor (230 vs 225 Hz) but off ~2.7x for 2-blade. The classifier uses an honestly-named modulation descriptor instead.", RED],
    ["Synthetic data only", "The classifier has never seen a real radar recording. Randomised parameters and SNR guard against fitting one signature, but accuracy on measured data will be lower.", AMBER],
    ["Geometry is plausible, not surveyed", "A generic Mediterranean container-port layout at the right scale. Substituting surveyed asset and mast positions is a data change, not a code change.", TEAL],
    ["Independence assumed in fusion", "Pd_sys = 1 − Π(1 − Pdᵢ) treats sensors as independent. A correlated bound and weather presets are provided; common-mode failure is not fully modelled.", TEAL],
    ["No clutter or data association", "Sea clutter, false alarms and multi-target association are absent from the tracking layer.", TEAL],
    ["No ducting", "Evaporation ducts over warm sea can extend detection well past the 4/3-Earth horizon. Not modelled.", TEAL],
  ];

  cards.forEach(([t, b, c], i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = M + col * 4.06;
    const y = 2.0 + row * 2.02;
    s.addShape(pptx.ShapeType.roundRect, {
      x: x, y: y, w: 3.82, h: 1.82,
      fill: { color: TINT }, rectRadius: 0.07,
    });
    s.addShape(pptx.ShapeType.ellipse, {
      x: x + 0.22, y: y + 0.24, w: 0.2, h: 0.2, fill: { color: c },
    });
    s.addText(t, {
      x: x + 0.52, y: y + 0.17, w: 3.14, h: 0.34,
      fontFace: B_FONT, fontSize: 12.5, bold: true, color: INK, margin: 0,
    });
    s.addText(b, {
      x: x + 0.24, y: y + 0.56, w: 3.36, h: 1.2,
      fontFace: B_FONT, fontSize: 10.5, color: INK, margin: 0,
      valign: "top", lineSpacingMultiple: 1.04,
    });
  });

  s.addShape(pptx.ShapeType.roundRect, {
    x: M, y: 6.06, w: CW, h: 0.72,
    fill: { color: MIDNIGHT }, rectRadius: 0.07,
  });
  s.addText(
    "None of these blocks the tool's present use: coverage and siting answers hold " +
      "under the stated assumptions. They bound what may be claimed, not what it can do.",
    {
      x: M + 0.22, y: 6.06, w: CW - 0.44, h: 0.72,
      fontFace: B_FONT, fontSize: 12, color: "D8E3EC", valign: "middle",
      margin: 0,
    }
  );

  footer(s, 12);
  s.addNotes(
    "Do not rush this slide. Volunteering the rejected estimators is the " +
      "strongest credibility move in the deck - it shows the difference between " +
      "a result and a number that merely looks like one."
  );
})();

// ================================================================ 13 roadmap
(() => {
  const s = lightSlide();
  heading(s, "Roadmap", "Week 1 delivered. Weeks 2–3 carry the harder work");

  const cols = [
    ["DELIVERED: WEEK 1", DEEP, [
      "Noise-limited detection chain, exact Pd, Albersheim design inversion",
      "Maritime propagation: multipath, ITU-R attenuation, radar horizon",
      "Scatterer-based rotor and bird synthesis, validated against theory",
      "Cross-validated SVM with speed ablation and permutation importance",
      "Kalman + IMM with Monte-Carlo RMSE and NEES consistency",
      "2-D coverage maps, gap analysis, greedy mast siting",
      "One-command reproducible run; documented limitations",
    ]],
    ["WEEKS 2–3", AMBER, [
      "Recover blade rate properly: longer coherent dwell, cepstral / HERM-line analysis",
      "CNN on spectrograms benchmarked against the feature SVM, same folds",
      "Sea clutter, false alarms and nearest-neighbour association in the tracker",
      "Multi-target scenarios: swarm, decoy plus penetrator",
      "Coverage under degraded weather as a first-class case, not a flag",
      "Unit tests on every closed-form path; CI",
      "Literature positioning against published C-UAS coverage studies",
    ]],
    ["BEYOND", TEAL, [
      "Validation against real radar recordings, the single biggest credibility gain available",
      "Surveyed port geometry replacing the generic layout",
      "Cost model alongside coverage, so siting optimises value not just Pd",
      "Elevation / 3-D coverage volumes instead of a single altitude slice",
      "Evaporation-duct propagation for warm-sea conditions",
      "Track-before-detect for targets below the single-dwell threshold",
      "Bistatic and passive-radar geometries, which favour low-RCS detection",
      "Packaging as a reusable siting service rather than a script",
    ]],
  ];

  cols.forEach(([title, colour, items], i) => {
    const x = M + i * 4.14;
    s.addShape(pptx.ShapeType.roundRect, {
      x: x, y: 1.54, w: 3.86, h: 4.9,
      fill: { color: i === 0 ? TINT : WHITE }, rectRadius: 0.07,
      line: i === 0 ? undefined : { color: "DCE5EC", width: 1 },
    });
    s.addShape(pptx.ShapeType.roundRect, {
      x: x + 0.24, y: 1.76, w: 2.5, h: 0.34,
      fill: { color: colour }, rectRadius: 0.05,
    });
    s.addText(title, {
      x: x + 0.24, y: 1.76, w: 2.5, h: 0.34,
      fontFace: B_FONT, fontSize: 10.5, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0,
    });
    bullets(s, items, {
      x: x + 0.26, y: 2.26, w: 3.34, h: 4.0, size: 10.5, gap: 8,
    });
  });

  footer(s, 13);
  s.addNotes(
    "Be explicit that weeks 2-3 include the things week 1 could not close - " +
      "especially blade-rate recovery, which is listed as a limitation earlier " +
      "and reappears here as scheduled work."
  );
})();

// ================================================================ 14 ask
(() => {
  const s = darkSlide();
  s.addShape(pptx.ShapeType.ellipse, {
    x: -2.2, y: 4.2, w: 6.2, h: 6.2,
    fill: { color: DEEP, transparency: 76 },
  });

  s.addText("THE ASK", {
    x: M, y: 1.0, w: CW, h: 0.32,
    fontFace: B_FONT, fontSize: 12.5, bold: true, color: AMBER,
    charSpacing: 2.0, margin: 0,
  });
  s.addText("A working tool, and the data to make it real", {
    x: M, y: 1.36, w: 10.6, h: 0.9,
    fontFace: H_FONT, fontSize: 32, bold: true, color: WHITE, margin: 0,
  });

  const asks = [
    ["Use it", "Apply the framework to a live coverage or feasibility study. It answers sensor count and siting today, under stated assumptions."],
    ["Feed it", "Real radar recordings, or surveyed site geometry. This is the single largest credibility gain available and the one thing I cannot generate."],
    ["Back it", "Supervision and lab access for weeks 2–3: clutter modelling, CNN benchmark, and blade-rate recovery from longer coherent dwells."],
  ];
  asks.forEach(([t, b], i) => {
    const x = M + i * 4.14;
    s.addShape(pptx.ShapeType.roundRect, {
      x: x, y: 2.6, w: 3.86, h: 1.56,
      fill: { color: "16304B" }, rectRadius: 0.08,
    });
    s.addText(String(i + 1), {
      x: x + 0.28, y: 2.82, w: 0.5, h: 0.4,
      fontFace: H_FONT, fontSize: 20, bold: true, color: AMBER, margin: 0,
    });
    s.addText(t, {
      x: x + 0.78, y: 2.84, w: 2.8, h: 0.36,
      fontFace: B_FONT, fontSize: 16, bold: true, color: WHITE, margin: 0,
    });
    s.addText(b, {
      x: x + 0.3, y: 3.3, w: 3.28, h: 1.2,
      fontFace: B_FONT, fontSize: 11.5, color: "C4D3DF", margin: 0,
      valign: "top", lineSpacingMultiple: 1.06,
    });
  });

  s.addShape(pptx.ShapeType.roundRect, {
    x: M, y: 4.54, w: CW, h: 0.86,
    fill: { color: "16304B" }, rectRadius: 0.07,
  });
  s.addText([
    { text: "Reproduce everything in this deck:   ", options: { color: "9FB4C4" } },
    { text: "python run_demo.py", options: { fontFace: "Courier New", bold: true, color: WHITE } },
    { text: "     114 s  ·  writes reports/*.png and results.json", options: { color: "9FB4C4" } },
  ], {
    x: M + 0.24, y: 4.54, w: CW - 0.48, h: 0.86,
    fontFace: B_FONT, fontSize: 13, valign: "middle", margin: 0,
  });

  s.addText(
    "Scope boundary held throughout: sensing, detection, classification and tracking only. " +
      "No effector, jamming or intercept parameters.",
    {
      x: M, y: 5.62, w: 11.6, h: 0.5,
      fontFace: B_FONT, fontSize: 10.5, italic: true, color: "7E93A5", margin: 0,
    }
  );
  s.addNotes(
    "Close on the three asks in order of increasing commitment. The middle one " +
      "- real recordings - is the one to push, because it is the limitation " +
      "named earlier and only they can remove it."
  );
})();

const out = path.join(__dirname, "CUAS_Layered_Sensing_Pitch.pptx");
pptx.writeFile({ fileName: out }).then(() => console.log("wrote " + out));
