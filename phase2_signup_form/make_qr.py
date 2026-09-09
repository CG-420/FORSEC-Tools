#!/usr/bin/env python3
"""
Generates the sign-up QR codes.

Error correction is set to H (30% recovery) deliberately. The code gets
scanned off a projector screen in a hotel function room, which is about the
worst case there is: low contrast, keystone distortion, and people shooting
it at an angle from three tables back. The extra redundancy costs nothing
here because the URL is short.

    pip install segno
    python3 make_qr.py
"""

import segno

URL = "https://wkf.ms/3UIP6nj"   # Sign-Up form, Contractor Directory (Phase 2)

qr = segno.make(URL, error="h")

# Black on white for the slide. Scanning off a projection is already marginal,
# so contrast is not the place to spend the brand budget.
qr.save("QR_SignUp_Black.png", scale=40, border=4, dark="#000000", light="#FFFFFF")
qr.save("QR_SignUp_Black.svg", scale=10, border=4, dark="#000000", light="#FFFFFF")

# FORSEC green, for print, where the lighting is controlled.
qr.save("QR_SignUp_Green.png", scale=40, border=4, dark="#338A57", light="#FFFFFF")

print(f"{URL}  version {qr.version}, EC H, {qr.symbol_size(1)[0] - 2} modules")
