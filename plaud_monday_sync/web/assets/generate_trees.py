#!/usr/bin/env python3
"""
Generates the conifer treeline strip used along the bottom of the header.

Each tree is a single silhouette path built tier by tier: from the apex the
outline steps out to a drooping branch tip, tucks back toward the trunk,
then steps out further on the next tier down. That notched profile is what
reads as a spruce/fir rather than a stack of triangles. The right side is
generated, then mirrored for the left, with per-tree jitter so no two trees
are identical.

Run this only when the artwork needs regenerating:
    python3 generate_trees.py > trees.svg
"""

import random

STRIP_W = 900.0       # tile width; repeats horizontally
STRIP_H = 120.0       # tile height
BASELINE = STRIP_H    # trees sit on the bottom edge
SEED = 5


def conifer(cx, height, width, tiers, rng):
    """Silhouette path for one tree, apex at (cx, BASELINE - height)."""
    apex_y = BASELINE - height
    trunk_w = width * 0.055
    trunk_h = height * 0.10
    canopy_h = height - trunk_h

    right = []
    for k in range(tiers):
        t0 = k / tiers
        t1 = (k + 1) / tiers
        # Tier width grows toward the base, slightly faster than linear so
        # the crown stays narrow and the skirt spreads out.
        tip_w = (width / 2) * (t1 ** 1.25) * rng.uniform(0.93, 1.07)
        tuck_w = tip_w * rng.uniform(0.40, 0.52)

        tip_y = apex_y + canopy_h * t1
        tuck_y = apex_y + canopy_h * (t0 + (t1 - t0) * 0.30)
        droop = canopy_h * 0.035  # branch tips hang slightly below the joint

        right.append(("tuck", cx + tuck_w, tuck_y))
        right.append(("tip", cx + tip_w, tip_y + droop))

    parts = [f"M{cx:.1f},{apex_y:.1f}"]
    for _, x, y in right:
        parts.append(f"L{x:.1f},{y:.1f}")
    # Down the trunk on the right, across the base, up the left trunk.
    parts.append(f"L{cx + trunk_w:.1f},{BASELINE - trunk_h:.1f}")
    parts.append(f"L{cx + trunk_w:.1f},{BASELINE:.1f}")
    parts.append(f"L{cx - trunk_w:.1f},{BASELINE:.1f}")
    parts.append(f"L{cx - trunk_w:.1f},{BASELINE - trunk_h:.1f}")
    for _, x, y in reversed(right):
        parts.append(f"L{2 * cx - x:.1f},{y:.1f}")
    parts.append("Z")
    return "".join(parts)


def main():
    rng = random.Random(SEED)

    # Two depth layers: a lighter, shorter row behind a slightly darker,
    # taller row in front, so the strip reads as a treeline with depth.
    back, front = [], []

    x = -10.0
    while x < STRIP_W + 20:
        h = rng.uniform(38, 58)
        w = h * rng.uniform(0.52, 0.66)
        back.append(conifer(x, h, w, rng.randint(4, 5), rng))
        x += rng.uniform(26, 40)

    x = -14.0
    while x < STRIP_W + 24:
        h = rng.uniform(58, 92)
        w = h * rng.uniform(0.50, 0.62)
        front.append(conifer(x, h, w, rng.randint(5, 6), rng))
        x += rng.uniform(38, 62)

    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{STRIP_W:.0f}' "
        f"height='{STRIP_H:.0f}' viewBox='0 0 {STRIP_W:.0f} {STRIP_H:.0f}'>",
        "<g fill='#3B6E4D' opacity='0.20'>",
    ]
    out.extend(f"<path d='{d}'/>" for d in back)
    out.append("</g><g fill='#3B6E4D' opacity='0.32'>")
    out.extend(f"<path d='{d}'/>" for d in front)
    out.append("</g></svg>")
    print("".join(out))


if __name__ == "__main__":
    main()
