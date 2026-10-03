"""The coat's violet filigree embroidery as relief images (numpy, deterministic),
sampled by the coat material (coat_leather.py) and baked.

Satin stitch: every motif is a column of thread laid across the stroke at a
slant, so each pixel stores the stroke's height profile (a rounded column) and
a thread phase (distance along the stroke plus the slanted offset across it);
the material turns the phase into the threads' ridges and sheen. The leather
puckers into a faint groove around the embroidery.

- `band(length_mm)`: a vertical vine along the outer sleeve, from just above the
  cuff to below the armhole: a sinuous stem with scrolls ending in volutes,
  lancet leaves and tendrils alternating left and right, a pointed crest at the
  bottom (her emblem's shape) and a fleur at the top. BAND_W wide, centered on
  the ornament line; mirror-symmetric pairs read the same on both arms.
- `panel()`: the turned-back cuff's ornament on the back of the wrist, mirror-
  symmetric: a crest with an inner arch, S-scrolls running around the cuff to
  both sides, leaves and dots.

Images are float RGBA, Non-Color: R = height (0..1 ridge, a negative pucker
around it), G = coverage mask, B = thread ridges (0..1, already cosine-shaped).
"""

import math

import bpy
import numpy as np

from filigree import _box_blur, _catmull, scroll

PX_MM = 8.0          # image resolution
PITCH = 1.3          # satin thread spacing along a stroke (mm)
SLANT = 0.55         # thread slant: phase offset per mm across the stroke
BAND_W = 46.0        # band width (mm), centered on the ornament line
PANEL_W = 84.0       # cuff panel (mm): around the cuff x up the arm
PANEL_H = 46.0


class SatinCanvas:
    """Height + thread-phase canvas in mm, origin at `origin_px`, y up the arm."""

    def __init__(self, w_mm, h_mm, origin_mm):
        self.w = int(round(w_mm * PX_MM))
        self.hgt = int(round(h_mm * PX_MM))
        self.h = np.zeros((self.hgt, self.w))
        self.phase = np.zeros((self.hgt, self.w))
        self.origin = (origin_mm[0] * PX_MM, origin_mm[1] * PX_MM)

    def stroke(self, path_mm, w0=2.0, w1=1.0, profile=None, phase0=0.0):
        """Satin column along a polyline (mm). Width tapers w0 -> w1, or `profile(s)` gives
        the width at s = 0..1 (filled leaves)."""
        p = np.asarray(path_mm, dtype=float)
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
        total = seg.sum()
        if total <= 0:
            return
        step = 0.35 / PX_MM
        acc = np.r_[0.0, np.cumsum(seg)]
        ts = np.arange(0.0, total, step)
        xs = np.interp(ts, acc, p[:, 0])
        ys = np.interp(ts, acc, p[:, 1])
        dx, dy = np.gradient(xs), np.gradient(ys)
        nrm = np.hypot(dx, dy) + 1e-12
        tx, ty = dx / nrm, dy / nrm
        s = ts / total
        widths = profile(s) if profile is not None else w0 + (w1 - w0) * s ** 1.3
        for x, y, w, ux, uy, d in zip(xs, ys, widths, tx, ty, ts):
            self._stamp(x, y, max(w, 0.25) * 0.5, -uy, ux, d + phase0)

    def dot(self, center, r):
        self._stamp(center[0], center[1], r, 1.0, 0.0, 0.0)

    def _stamp(self, x_mm, y_mm, r_mm, nx, ny, along):
        H, W = self.h.shape
        cx = self.origin[0] + x_mm * PX_MM
        cy = self.origin[1] + y_mm * PX_MM
        r = max(r_mm * PX_MM, 0.8)
        x0, x1 = max(0, int(math.floor(cx - r - 1))), min(W, int(math.ceil(cx + r + 1)))
        y0, y1 = max(0, int(math.floor(cy - r - 1))), min(H, int(math.ceil(cy + r + 1)))
        if x1 <= x0 or y1 <= y0:
            return
        xs = np.arange(x0, x1)[None, :] + 0.5
        ys = np.arange(y0, y1)[:, None] + 0.5
        d2 = ((xs - cx) ** 2 + (ys - cy) ** 2) / (r * r)
        prof = np.sqrt(np.clip(1.0 - d2, 0.0, 1.0)) ** 0.7  # satin columns are full, round-shouldered
        lat = ((xs - cx) * nx + (ys - cy) * ny) / PX_MM
        ph = along + SLANT * lat
        win = self.h[y0:y1, x0:x1]
        better = prof > win
        win[better] = prof[better]
        self.phase[y0:y1, x0:x1][better] = ph[better]

    def finish(self):
        h = self.h
        mask = np.clip(h * 4.0, 0.0, 1.0)
        thread = 0.5 + 0.5 * np.cos(2.0 * math.pi * self.phase / PITCH)
        thread = np.where(mask > 0.0, thread, 0.0)
        b = _box_blur(_box_blur(mask, 6, False), 6, False)
        pucker = np.clip(b - mask, 0.0, 1.0)
        height = h - 0.30 * pucker
        return height, mask, thread


def _leaf(c, base, tip, width, phase0=0.0):
    """Filled satin leaf from base to tip (mm), slightly curved."""
    base, tip = np.array(base, float), np.array(tip, float)
    d = tip - base
    n = np.array((-d[1], d[0])) / np.linalg.norm(d)
    mid = base + d * 0.5 + n * np.linalg.norm(d) * 0.08
    path = _catmull([base, mid, tip], 12)
    c.stroke(path, profile=lambda s: 0.6 + width * np.sin(np.pi * np.clip(s, 0, 1)) ** 0.75 * (1.0 - 0.35 * s),
             phase0=phase0)


def _mirror_x(path):
    p = np.asarray(path, dtype=float).copy()
    p[:, 0] *= -1.0
    return p


def band(length_mm):
    """The sleeve's vertical vine: x across (-BAND_W/2..BAND_W/2), y from 0 (above the cuff)
    to length_mm (below the armhole)."""
    c = SatinCanvas(BAND_W, length_mm, (BAND_W * 0.5, 0.0))
    L = length_mm
    period = 66.0
    amp = 3.4
    y0, y1 = 30.0, L - 34.0

    def stem_x(y):
        return amp * np.sin(2.0 * np.pi * (y - y0) / period)

    ys = np.linspace(y0, y1, int((y1 - y0) / 1.5))
    c.stroke(np.c_[stem_x(ys), ys], 2.5, 2.5)
    # branches: alternate sides at the stem's swing, each a scroll ending in a volute with a
    # smaller counter-scroll, a leaf from the stem, a bud and a tendril on the other side
    k = 0
    y = y0 + period * 0.25
    while y < y1 - 26.0:
        side = 1.0 if k % 2 == 0 else -1.0
        sx = stem_x(y)
        pts = [(sx, y), (sx + side * 5.5, y + 6.5), (side * 11.5, y + 12.5), (side * 17.0, y + 11.5)]
        path = scroll(pts, (side * 15.2, y + 7.6), 4.2, 0.8, 1.2, -side)
        c.stroke(path, 2.7, 1.0)
        small = scroll([(side * 11.0, y + 12.2), (side * 9.0, y + 17.5), (side * 12.5, y + 21.5)],
                       (side * 14.3, y + 19.4), 2.3, 0.6, 1.0, side)
        c.stroke(small, 1.8, 0.8)
        _leaf(c, (sx + side * 2.6, y + 3.5), (side * 6.5, y + 26.0), 3.4)
        _leaf(c, (side * 13.0, y + 3.8), (side * 20.0, y - 1.5), 2.2)
        t_pts = [(sx, y - 7.0), (sx - side * 4.5, y - 3.5), (-side * 9.0, y + 1.0)]
        c.stroke(scroll(t_pts, (-side * 7.8, y - 1.8), 2.6, 0.6, 1.05, side), 1.9, 0.8)
        for dx, dy, r in ((12.5, 7.5, 1.25), (15.5, 4.0, 0.95), (12.0, 11.5, 0.8)):
            c.dot((-side * dx, y + dy), r)
        k += 1
        y += period * 0.5
    # bottom: a pointed crest (her emblem's lancet arch) with two volutes beside its foot
    crest = _catmull([(0.0, 2.0), (3.6, 7.0), (5.8, 14.0), (4.8, 21.5), (1.8, 27.0), (0.0, 30.0)], 14)
    for p in (crest, _mirror_x(crest)):
        c.stroke(p, 2.8, 1.8)
    inner = _catmull([(0.0, 8.5), (2.1, 12.5), (2.6, 17.5), (1.2, 22.0), (0.0, 23.5)], 12)
    for p in (inner, _mirror_x(inner)):
        c.stroke(p, 1.8, 1.2)
    c.dot((0.0, 15.5), 1.6)
    foot = scroll([(0.0, 2.0), (5.0, 1.0), (10.5, 3.8), (13.5, 9.5)], (10.6, 9.0), 3.0, 0.6, 1.2, 1.0)
    for p in (foot, _mirror_x(foot)):
        c.stroke(p, 2.4, 0.9)
    for s_ in (1.0, -1.0):
        _leaf(c, (s_ * 6.0, 5.0), (s_ * 17.0, 17.0), 2.4)
    c.dot((0.0, -1.0), 1.5)
    # top: a fleur of three leaves and two volutes curling down
    yt = y1
    _leaf(c, (stem_x(yt), yt - 1.0), (0.0, yt + 27.0), 3.8)
    for s_ in (1.0, -1.0):
        _leaf(c, (stem_x(yt) + s_ * 1.0, yt), (s_ * 15.0, yt + 17.0), 3.0)
        v = scroll([(stem_x(yt), yt - 3.0), (s_ * 6.5, yt - 6.5), (s_ * 14.0, yt - 5.0)], (s_ * 12.2, yt - 1.8), 3.3,
                   0.7, 1.2, -s_)
        c.stroke(v, 2.4, 0.9)
    c.dot((0.0, yt + 31.0), 1.4)
    return c.finish()


def panel():
    """The cuff's ornament: x around the cuff (-PANEL_W/2..PANEL_W/2), y up the cuff (0..PANEL_H)."""
    c = SatinCanvas(PANEL_W, PANEL_H, (PANEL_W * 0.5, 0.0))
    strokes = []
    # crest: a lancet arch rising from the bottom center, an inner arch, a dot at its heart
    strokes.append((_catmull([(0.0, 3.0), (4.2, 9.0), (6.4, 18.0), (5.0, 28.0), (2.2, 36.0), (0.0, 40.5)], 14),
                    2.9, 1.8))
    strokes.append((_catmull([(0.0, 10.0), (2.4, 15.0), (3.0, 21.0), (1.6, 27.5), (0.0, 30.0)], 12), 2.0, 1.2))
    # S-scrolls from the crest's foot running around the cuff, ending in volutes
    strokes.append((scroll([(0.0, 3.0), (6.0, 2.6), (13.0, 6.5), (19.0, 13.5), (26.0, 16.0), (31.5, 13.0)],
                           (29.6, 9.4), 4.0, 0.7, 1.2, -1.0), 2.8, 1.0))
    strokes.append((scroll([(6.2, 16.0), (11.0, 24.0), (17.0, 28.5), (23.5, 28.0)], (22.4, 24.3), 3.6, 0.6, 1.15,
                           -1.0), 2.4, 0.9))
    strokes.append((scroll([(19.0, 13.5), (24.0, 8.0), (32.0, 4.5), (38.5, 6.0)], (37.0, 9.0), 2.9, 0.55, 1.1, 1.0),
                    2.1, 0.8))
    for path, w0, w1 in strokes:
        c.stroke(path, w0, w1)
        c.stroke(_mirror_x(path), w0, w1)
    for base, tip, w in (((8.0, 9.0), (13.0, 19.5), 3.0), ((26.5, 18.0), (33.0, 26.5), 2.6),
                         ((3.6, 34.0), (9.5, 41.0), 2.4), ((33.0, 15.5), (40.5, 20.0), 2.0)):
        _leaf(c, base, tip, w)
        _leaf(c, (-base[0], base[1]), (-tip[0], tip[1]), w)
    for (x, y), r in (((0.0, 20.0), 1.9), ((16.0, 3.0), 1.3), ((40.0, 12.0), 1.1), ((0.0, 44.0), 1.4),
                      ((12.0, 36.0), 1.0)):
        c.dot((x, y), r)
        if x:
            c.dot((-x, y), r)
    return c.finish()


def to_image(name, height, mask, thread):
    h, w = height.shape
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    px = np.zeros((h, w, 4), dtype=np.float32)
    px[..., 0] = height
    px[..., 1] = mask
    px[..., 2] = thread
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img


def images(band_length_mm):
    """(band image, panel image) as packed Blender images."""
    return to_image("embroidery_band", *band(band_length_mm)), to_image("embroidery_panel", *panel())


def remove_images():
    for name in ("embroidery_band", "embroidery_panel"):
        img = bpy.data.images.get(name)
        if img is not None:
            bpy.data.images.remove(img)
