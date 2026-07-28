#!/usr/bin/env python3
"""
Generates the seamless topographic-contour background used by the web UI.

This draws a *real* contour map rather than decorative squiggles: it builds
a periodic height field (a sum of sine waves with integer frequencies, so
it repeats exactly over the tile), then extracts iso-elevation contours
from it with marching squares. Because the field is genuinely periodic and
the grid includes the wrap-around row/column, the resulting lines meet
exactly at the tile edges and repeat seamlessly.

Run this only when the artwork needs regenerating:
    python3 generate_topo.py > topo.svg
"""

import math
import random

TILE = 800.0          # tile size in SVG user units
GRID = 150            # sampling resolution (GRID x GRID cells)
LEVELS = 26           # number of elevation contours
INDEX_EVERY = 5       # every Nth contour is an "index contour" (heavier line)
SEED = 11


def build_terms(seed=SEED):
    """Sine terms with integer frequencies -> exactly periodic over TILE."""
    rng = random.Random(seed)
    terms = []
    # Low frequencies carry the big landforms; higher ones add detail.
    for freq_x, freq_y in [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1),
                           (2, 3), (3, 2), (4, 1), (1, 4), (3, 3), (4, 3),
                           (5, 2), (2, 5), (5, 4), (4, 5), (6, 3), (3, 6)]:
        f = math.hypot(freq_x, freq_y)
        amp = 1.0 / (f ** 1.78)
        phase = rng.uniform(0, 2 * math.pi)
        sign_x = rng.choice([1, -1])
        sign_y = rng.choice([1, -1])
        terms.append((sign_x * freq_x, sign_y * freq_y, amp, phase))
    return terms


TERMS = build_terms()


def height(x, y):
    total = 0.0
    for nx, ny, amp, phase in TERMS:
        total += amp * math.sin(2 * math.pi * (nx * x + ny * y) / TILE + phase)
    return total


def sample_field():
    """(GRID+1)^2 samples; last row/col duplicate the first (periodic)."""
    step = TILE / GRID
    return [[height(i * step, j * step) for j in range(GRID + 1)]
            for i in range(GRID + 1)]


def interp(p1, p2, v1, v2, level):
    if abs(v2 - v1) < 1e-12:
        return p1
    t = (level - v1) / (v2 - v1)
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def marching_squares(field, level):
    """Returns line segments tracing `level` through the scalar field."""
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

            # Midpoints on each cell edge, where the contour crosses.
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
    return (round(pt[0], 4), round(pt[1], 4))


def join_segments(segments):
    """Chains segments end-to-end into polylines (fewer, smoother paths)."""
    adjacency = {}
    for idx, (a, b) in enumerate(segments):
        adjacency.setdefault(key(a), []).append((idx, b))
        adjacency.setdefault(key(b), []).append((idx, a))

    used = [False] * len(segments)
    polylines = []

    for start_idx, (a, b) in enumerate(segments):
        if used[start_idx]:
            continue
        used[start_idx] = True
        chain = [a, b]

        # Walk forward from b, then backward from a.
        for direction in (0, 1):
            if direction == 1:
                chain.reverse()
            while True:
                tail = chain[-1]
                nxt = None
                for idx, other in adjacency.get(key(tail), []):
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
    parts = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for x, y in points[1:]:
        parts.append(f"L{x:.1f},{y:.1f}")
    return "".join(parts)


def main():
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
        "<g fill='none' stroke='#3B6E4D' stroke-linecap='round' "
        "stroke-linejoin='round'>",
        "<g stroke-width='1' opacity='0.16'>",
    ]
    out.extend(f"<path d='{d}'/>" for d in regular)
    out.append("</g><g stroke-width='1.9' opacity='0.26'>")
    out.extend(f"<path d='{d}'/>" for d in index)
    out.append("</g></g></svg>")
    print("".join(out))


if __name__ == "__main__":
    main()
