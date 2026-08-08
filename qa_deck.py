"""
Deck QA: geometry checks plus real slide renders.

Two passes:

1. Geometry - every shape checked against the slide bounds and against its
   siblings for overlap. Catches the defects that make a deck look
   machine-generated: text spilling off the canvas, boxes sitting on top of
   each other, margins narrower than the design allows.

2. Render - PowerPoint itself exports PNGs, so the visual check sees exactly
   what the audience will. (LibreOffice is not installed here, and it would
   substitute fonts anyway.)

Usage:
    python qa_deck.py CUAS_Layered_Sensing_Pitch.pptx
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

MIN_MARGIN_IN = 0.5
MIN_GAP_IN = 0.0          # report only true overlaps, not tight spacing


def safe(s: str) -> str:
    """Windows consoles here are cp1252; strip anything it cannot encode."""
    return s.encode("ascii", "replace").decode("ascii")


def to_in(v) -> float:
    return Emu(v).inches if v is not None else 0.0


def rect(sh):
    return (to_in(sh.left), to_in(sh.top),
            to_in(sh.left) + to_in(sh.width),
            to_in(sh.top) + to_in(sh.height))


def overlap_area(a, b) -> float:
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def has_text(sh) -> bool:
    return sh.has_text_frame and sh.text_frame.text.strip() != ""


def table_bottom_in(sh) -> float:
    """Estimated rendered bottom of a table.

    A table's declared row heights are a minimum: PowerPoint grows each row to
    fit its text, so the declared frame height under-reports the rendered one.
    Checking the declared value alone let a table overrun the footer without
    the geometry pass noticing, so rows are re-estimated from their font size.
    """
    tbl = sh.table
    total = 0.0
    for row in tbl.rows:
        declared = to_in(row.height)
        pts = []
        for cell in row.cells:
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    if run.font.size is not None:
                        pts.append(run.font.size.pt)
        pt = max(pts) if pts else 12.0
        total += max(declared, pt / 72.0 * 1.35 + 0.08)
    return to_in(sh.top) + total


def geometry_report(path: Path) -> list[str]:
    prs = Presentation(str(path))
    sw, sh_in = to_in(prs.slide_width), to_in(prs.slide_height)
    problems: list[str] = []
    print(f"slide size {sw:.2f} x {sh_in:.2f} in, {len(prs.slides)} slides\n")

    for i, slide in enumerate(prs.slides, start=1):
        shapes = list(slide.shapes)
        boxes = [(sh, rect(sh)) for sh in shapes]

        for sh in shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                bot = table_bottom_in(sh)
                if bot > sh_in - 0.42:
                    problems.append(
                        f"slide {i}: TABLE too tall - estimated bottom "
                        f"{bot:.2f} in, collides with the footer band "
                        f"(safe limit {sh_in - 0.42:.2f})")

        for sh, r in boxes:
            name = sh.shape_type
            label = (sh.text_frame.text.strip().splitlines()[0][:42]
                     if has_text(sh) else f"<{name}>")
            # Off-canvas / out of bounds
            if r[0] < -0.05 or r[1] < -0.05 or r[2] > sw + 0.05 or r[3] > sh_in + 0.05:
                # Decorative bleed shapes are intentional; only flag text.
                if has_text(sh):
                    problems.append(
                        f"slide {i}: TEXT OUT OF BOUNDS  '{label}'  "
                        f"box=({r[0]:.2f},{r[1]:.2f})-({r[2]:.2f},{r[3]:.2f})")
            # Margin check for text only
            if has_text(sh):
                if r[0] < MIN_MARGIN_IN - 0.02 or r[2] > sw - MIN_MARGIN_IN + 0.02:
                    problems.append(
                        f"slide {i}: MARGIN  '{label}'  x={r[0]:.2f}..{r[2]:.2f} "
                        f"(want {MIN_MARGIN_IN}..{sw-MIN_MARGIN_IN:.2f})")
                if r[3] > sh_in - 0.12:
                    problems.append(
                        f"slide {i}: BOTTOM EDGE  '{label}'  bottom={r[3]:.2f}")

        # Text-on-text overlap (shape-behind-text is by design)
        texts = [(sh, r) for sh, r in boxes if has_text(sh)]
        for a in range(len(texts)):
            for b in range(a + 1, len(texts)):
                sa, ra = texts[a]
                sb, rb = texts[b]
                ov = overlap_area(ra, rb)
                if ov > 0.05:
                    la = sa.text_frame.text.strip().splitlines()[0][:28]
                    lb = sb.text_frame.text.strip().splitlines()[0][:28]
                    problems.append(
                        f"slide {i}: TEXT OVERLAP {ov:.2f} in^2  "
                        f"'{la}' <-> '{lb}'")
    return problems


def render(path: Path, out_dir: Path) -> list[Path]:
    """Export slide PNGs using PowerPoint's own renderer."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.PNG"):
        old.unlink()
    for old in out_dir.glob("*.png"):
        old.unlink()

    ps = f"""
$ErrorActionPreference = 'Stop'
$app = New-Object -ComObject PowerPoint.Application
$deck = $app.Presentations.Open('{path.resolve()}', $true, $false, $false)
$deck.Export('{out_dir.resolve()}', 'PNG', 1600, 900)
$deck.Close()
$app.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
Write-Output 'exported'
"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("render failed:\n" + (r.stderr or r.stdout)[:1500])
        return []
    # Windows globbing is case-insensitive, so *.PNG and *.png match the same
    # files - dedupe on the resolved path.
    seen = {p.resolve(): p for p in
            list(out_dir.glob("*.PNG")) + list(out_dir.glob("*.png"))}
    return sorted(seen.values(),
                  key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))


def main() -> None:
    deck = Path(sys.argv[1] if len(sys.argv) > 1
                else "CUAS_Layered_Sensing_Pitch.pptx").resolve()
    print(f"QA on {deck.name}\n{'='*70}")

    problems = geometry_report(deck)
    if problems:
        print(f"{len(problems)} geometry issue(s):")
        for p in problems:
            print("  " + safe(p))
    else:
        print("geometry: no issues")

    print(f"\n{'='*70}\nrendering slides ...")
    files = render(deck, deck.parent / "reports" / "deck_render")
    for f in files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
