#!/usr/bin/env python3
"""
Builds "Phase 2 Kickoff Tracker.html" as a single self-contained file.

The tracker gets emailed around and opened off a desktop, so it cannot rely on
sitting next to an assets folder. This script inlines the official FORSEC logo
and regenerates the topographic background and conifer treeline (the same
artwork the Meeting Action Sync UI uses, at lighter settings so the inlined
data URIs stay small), then substitutes all three into template.html.

    python3 build.py

The logo is pulled from the forsec-document-standards skill so the tracker
always carries the current official mark rather than a copy that can drift.
"""

import base64
import math
import os
import random
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "Phase 2 Kickoff Tracker.html")

# Dark Green from the FORSEC palette. The background artwork is a low-opacity
# texture, so it uses the secondary green rather than competing with the
# primary #338A57 used for headers and accents.
GREEN = "#3B6E4D"

LOGO_CANDIDATES = [
    os.path.expanduser(
        "~/.claude/skills/synced/forsec-document-standards/assets/"
        "Forestry_Sector_Council_Full_Colour_Logo_RGB.png"),
    os.path.expanduser(
        "~/.claude/skills/forsec-document-standards/assets/"
        "Forestry_Sector_Council_Full_Colour_Logo_RGB.png"),
    os.path.join(HERE, "Forestry_Sector_Council_Full_Colour_Logo_RGB.png"),
]


def logo_uri():
    """Base64 data URI for the full-colour logo (light backgrounds)."""
    for path in LOGO_CANDIDATES:
        if os.path.exists(path):
            with open(path, "rb") as fh:
                encoded = base64.b64encode(fh.read()).decode("ascii")
            return "data:image/png;base64," + encoded
    raise SystemExit(
        "Could not find Forestry_Sector_Council_Full_Colour_Logo_RGB.png.\n"
        "Looked in:\n  " + "\n  ".join(LOGO_CANDIDATES))


# --------------------------------------------------------------------------
# Topographic contours
#
# A periodic height field (sine terms with integer frequencies, so it repeats
# exactly over the tile) run through marching squares. Because the field is
# genuinely periodic and the grid includes the wrap-around row/column, the
# contours meet at the tile edges and repeat seamlessly.
# --------------------------------------------------------------------------

TILE = 800.0
GRID = 96          # lower than the web UI's 150 - keeps the data URI small
LEVELS = 18
INDEX_EVERY = 4
SEED = 11


def build_terms(seed=SEED):
    rng = random.Random(seed)
    terms = []
    for fx, fy in [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1),
                   (2, 3), (3, 2), (4, 1), (1, 4), (3, 3), (4, 3),
                   (5, 2), (2, 5), (5, 4), (4, 5)]:
        amp = 1.0 / (math.hypot(fx, fy) ** 1.78)
        terms.append((rng.choice([1, -1]) * fx,
                      rng.choice([1, -1]) * fy,
                      amp,
                      rng.uniform(0, 2 * math.pi)))
    return terms


TERMS = build_terms()


def height(x, y):
    return sum(amp * math.sin(2 * math.pi * (nx * x + ny * y) / TILE + phase)
               for nx, ny, amp, phase in TERMS)


def sample_field():
    step = TILE / GRID
    return [[height(i * step, j * step) for j in range(GRID + 1)]
            for i in range(GRID + 1)]


def interp(p1, p2, v1, v2, level):
    if abs(v2 - v1) < 1e-12:
        return p1
    t = (level - v1) / (v2 - v1)
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def marching_squares(field, level):
    step = TILE / GRID
    segments = []
    for i in range(GRID):
        for j in range(GRID):
            x0, y0 = i * step, j * step
            x1, y1 = x0 + step, y0 + step
            v00, v10 = field[i][j], field[i + 1][j]
            v11, v01 = field[i + 1][j + 1], field[i][j + 1]

            code = 0
            if v00 >= level: code |= 1
            if v10 >= level: code |= 2
            if v11 >= level: code |= 4
            if v01 >= level: code |= 8
            if code in (0, 15):
                continue

            bottom = interp((x0, y0), (x1, y0), v00, v10, level)
            right = interp((x1, y0), (x1, y1), v10, v11, level)
            top = interp((x1, y1), (x0, y1), v11, v01, level)
            left = interp((x0, y1), (x0, y0), v01, v00, level)

            if code in (1, 14):
                segments.append((left, bottom))
            elif code in (2, 13):
                segments.append((bottom, right))
            elif code in (3, 12):
                segments.append((left, right))
            elif code in (4, 11):
                segments.append((right, top))
            elif code in (6, 9):
                segments.append((bottom, top))
            elif code in (7, 8):
                segments.append((left, top))
            elif code in (5, 10):
                # Saddle: resolve with the cell average so the two branches
                # connect the way the underlying surface actually does.
                avg = (v00 + v10 + v11 + v01) / 4.0
                if (code == 5) == (avg >= level):
                    segments.append((left, top))
                    segments.append((bottom, right))
                else:
                    segments.append((left, bottom))
                    segments.append((right, top))
    return segments


def key(pt):
    return (round(pt[0], 3), round(pt[1], 3))


def join_segments(segments):
    adjacency = {}
    for idx, (a, b) in enumerate(segments):
        adjacency.setdefault(key(a), []).append((idx, b))
        adjacency.setdefault(key(b), []).append((idx, a))

    used = [False] * len(segments)
    polylines = []
    for start, (a, b) in enumerate(segments):
        if used[start]:
            continue
        used[start] = True
        chain = [a, b]
        for direction in (0, 1):
            if direction == 1:
                chain.reverse()
            while True:
                nxt = None
                for idx, other in adjacency.get(key(chain[-1]), []):
                    if not used[idx]:
                        nxt = (idx, other)
                        break
                if nxt is None:
                    break
                used[nxt[0]] = True
                chain.append(nxt[1])
        if len(chain) >= 3:
            polylines.append(chain)
    return polylines


def path_data(points):
    parts = [f"M{points[0][0]:.0f},{points[0][1]:.0f}"]
    parts.extend(f"L{x:.0f},{y:.0f}" for x, y in points[1:])
    return "".join(parts)


def topo_svg():
    field = sample_field()
    flat = [v for row in field for v in row]
    lo, hi = min(flat), max(flat)
    span = hi - lo

    regular, index = [], []
    for n in range(1, LEVELS):
        level = lo + span * n / LEVELS
        polylines = join_segments(marching_squares(field, level))
        target = index if n % INDEX_EVERY == 0 else regular
        target.extend(path_data(p) for p in polylines)

    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{TILE:.0f}' "
        f"height='{TILE:.0f}' viewBox='0 0 {TILE:.0f} {TILE:.0f}'>",
        f"<g fill='none' stroke='{GREEN}' stroke-linecap='round' "
        "stroke-linejoin='round'>",
        "<g stroke-width='1' opacity='0.15'>",
    ]
    out.extend(f"<path d='{d}'/>" for d in regular)
    out.append("</g><g stroke-width='1.8' opacity='0.24'>")
    out.extend(f"<path d='{d}'/>" for d in index)
    out.append("</g></g></svg>")
    return "".join(out)


# --------------------------------------------------------------------------
# Conifer treeline
#
# Each tree is one silhouette path built tier by tier: from the apex the
# outline steps out to a drooping branch tip, tucks back toward the trunk,
# then steps out further on the next tier down. That notched profile is what
# reads as spruce/fir rather than a stack of triangles.
# --------------------------------------------------------------------------

STRIP_W = 900.0
STRIP_H = 120.0
TREE_SEED = 5


def conifer(cx, height_, width, tiers, rng):
    apex_y = STRIP_H - height_
    trunk_w = width * 0.055
    trunk_h = height_ * 0.10
    canopy_h = height_ - trunk_h

    right = []
    for k in range(tiers):
        t0, t1 = k / tiers, (k + 1) / tiers
        # Tier width grows toward the base slightly faster than linear, so the
        # crown stays narrow and the skirt spreads out.
        tip_w = (width / 2) * (t1 ** 1.25) * rng.uniform(0.93, 1.07)
        tuck_w = tip_w * rng.uniform(0.40, 0.52)
        tip_y = apex_y + canopy_h * t1
        tuck_y = apex_y + canopy_h * (t0 + (t1 - t0) * 0.30)
        droop = canopy_h * 0.035
        right.append((cx + tuck_w, tuck_y))
        right.append((cx + tip_w, tip_y + droop))

    parts = [f"M{cx:.1f},{apex_y:.1f}"]
    parts.extend(f"L{x:.1f},{y:.1f}" for x, y in right)
    parts.append(f"L{cx + trunk_w:.1f},{STRIP_H - trunk_h:.1f}")
    parts.append(f"L{cx + trunk_w:.1f},{STRIP_H:.1f}")
    parts.append(f"L{cx - trunk_w:.1f},{STRIP_H:.1f}")
    parts.append(f"L{cx - trunk_w:.1f},{STRIP_H - trunk_h:.1f}")
    parts.extend(f"L{2 * cx - x:.1f},{y:.1f}" for x, y in reversed(right))
    parts.append("Z")
    return "".join(parts)


def trees_svg():
    rng = random.Random(TREE_SEED)
    back, front = [], []

    x = -10.0
    while x < STRIP_W + 20:
        h = rng.uniform(38, 58)
        back.append(conifer(x, h, h * rng.uniform(0.52, 0.66),
                            rng.randint(4, 5), rng))
        x += rng.uniform(26, 40)

    x = -14.0
    while x < STRIP_W + 24:
        h = rng.uniform(58, 92)
        front.append(conifer(x, h, h * rng.uniform(0.50, 0.62),
                             rng.randint(5, 6), rng))
        x += rng.uniform(38, 62)

    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{STRIP_W:.0f}' "
        f"height='{STRIP_H:.0f}' viewBox='0 0 {STRIP_W:.0f} {STRIP_H:.0f}'>",
        f"<g fill='{GREEN}' opacity='0.18'>",
    ]
    out.extend(f"<path d='{d}'/>" for d in back)
    out.append(f"</g><g fill='{GREEN}' opacity='0.30'>")
    out.extend(f"<path d='{d}'/>" for d in front)
    out.append("</g></svg>")
    return "".join(out)


def data_uri(svg):
    # utf8 rather than base64: SVG is mostly ASCII path data, so percent
    # encoding comes out smaller and stays diffable.
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg, safe="")


def main():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        html = fh.read()

    html = html.replace("__LOGO_URI__", logo_uri())
    html = html.replace("__TOPO_URI__", data_uri(topo_svg()))
    html = html.replace("__TREES_URI__", data_uri(trees_svg()))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"wrote {os.path.normpath(OUT)} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
