"""Silena's filigree ornament as height images (numpy, deterministic), embossed into
the glove leather by the procedural material and baked.

- `panel()`: the back-of-hand panel, mirror-symmetric about the hand's middle
  line (so the mirrored right glove looks the same): a pointed crest like her
  emblem, C- and S-scrolls ending in volutes, lancet leaves, a stem toward the
  wrist. Covers PANEL_SIZE x PANEL_SIZE meters centered on the OrnUV origin.
- `band()`: a running scroll for the cuff, tileable along U (one motif per tile).

Images are float RGB, Non-Color: R = height 0..1 (rounded ridges with a faint
pressed groove around them), G = the ridge mask (for the violet tint).
"""

import math

import bpy
import numpy as np

PANEL_SIZE = 0.090      # meters covered by the panel image (u across, v along the hand)
PANEL_PX = 1024
BAND_LENGTH = 0.038     # meters per motif along the cuff
BAND_HEIGHT = 0.016
BAND_PX = (640, 270)    # (along, across)


def _catmull(points, samples=10):
    pts = [np.array(p, dtype=float) for p in points]
    pts = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(samples):
            t = k / samples
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-2])
    return np.array(out)


def _spiral(center, r0, r1, a0, turns, sense, n=40):
    s = np.linspace(0.0, 1.0, n)
    r = r0 * (r1 / r0) ** s
    a = a0 + sense * 2.0 * math.pi * turns * s
    return np.c_[center[0] + r * np.cos(a), center[1] + r * np.sin(a)]


def scroll(points, center, r0, r1, turns, sense):
    """A stroke through `points` (mm) ending in a volute around `center`: the spiral
    starts where the stroke ends (radius r0) and winds `turns` times down to r1."""
    end = np.array(points[-1], dtype=float)
    a0 = math.atan2(end[1] - center[1], end[0] - center[0])
    spiral = _spiral(center, r0, r1, a0, turns, sense)
    return np.r_[_catmull(points), spiral[1:]]


def leaf(base, tip, width):
    """A lancet leaf outline from `base` to `tip` (mm)."""
    base, tip = np.array(base, float), np.array(tip, float)
    d = tip - base
    n = np.array((-d[1], d[0])) / np.linalg.norm(d)
    mid = base + d * 0.45
    return [_catmull([base, mid + n * width, tip], 12), _catmull([base, mid - n * width, tip], 12)]


class Canvas:
    def __init__(self, w, h, px_per_mm, origin_px, wrap_x=False):
        self.h = np.zeros((h, w))
        self.ppm = px_per_mm
        self.origin = origin_px
        self.wrap = wrap_x

    def stroke(self, path_mm, w0=0.85, w1=0.38, taper_start=0.0):
        """Rounded ridge along a polyline (mm), width tapering from w0 to w1 (mm)."""
        p = np.asarray(path_mm, dtype=float)
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
        total = seg.sum()
        if total <= 0:
            return
        step = 0.4 / self.ppm  # stamp every 0.4 px
        acc = np.r_[0.0, np.cumsum(seg)]
        ts = np.arange(0.0, total, step)
        xs = np.interp(ts, acc, p[:, 0])
        ys = np.interp(ts, acc, p[:, 1])
        s = ts / total
        widths = w0 + (w1 - w0) * s ** 1.4
        if taper_start > 0:
            widths *= np.clip(0.45 + 0.55 * s / taper_start, 0.0, 1.0)
        for x, y, w in zip(xs, ys, widths):
            self._stamp(x, y, w * 0.5)

    def dot(self, center, r):
        self._stamp(center[0], center[1], r)

    def _stamp(self, x_mm, y_mm, r_mm):
        H, W = self.h.shape
        cx = self.origin[0] + x_mm * self.ppm
        cy = self.origin[1] + y_mm * self.ppm
        r = max(r_mm * self.ppm, 0.8)
        x0, x1 = int(math.floor(cx - r - 1)), int(math.ceil(cx + r + 1))
        y0, y1 = max(0, int(math.floor(cy - r - 1))), min(H, int(math.ceil(cy + r + 1)))
        if y1 <= y0:
            return
        ys = np.arange(y0, y1)[:, None] + 0.5
        for shift in ((-W, 0, W) if self.wrap else (0,)):
            xa, xb = x0 + shift, x1 + shift
            lo, hi = max(0, xa), min(W, xb)
            if hi <= lo:
                continue
            xs = np.arange(lo, hi)[None, :] + 0.5
            d2 = ((xs - (cx + shift)) ** 2 + (ys - cy) ** 2) / (r * r)
            prof = np.sqrt(np.clip(1.0 - d2, 0.0, 1.0))
            self.h[y0:y1, lo:hi] = np.maximum(self.h[y0:y1, lo:hi], prof)

    def finish(self, groove=0.32, blur_px=5):
        """Ridges plus a faint pressed groove around them (leather tooling)."""
        h = self.h
        b = _box_blur(h, blur_px, self.wrap)
        b = _box_blur(b, blur_px, self.wrap)
        out = np.clip(h - groove * np.clip(b - h, 0.0, 1.0) * 2.0, -1.0, 1.0)
        mask = np.clip(h * 3.0, 0.0, 1.0)
        return out, mask


def _box_blur(a, r, wrap):
    out = a.copy()
    for axis in (0, 1):
        mode = "wrap" if (wrap and axis == 1) else "edge"
        p = np.pad(out, [(r, r) if i == axis else (0, 0) for i in range(2)], mode=mode)
        c = np.cumsum(p, axis=axis)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        n = out.shape[axis]
        out = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
               - np.take(c, np.arange(0, n), axis=axis)) / (2 * r + 1)
    return out


def _mirror(paths):
    return paths + [np.c_[-np.asarray(p)[:, 0], np.asarray(p)[:, 1]] for p in paths]


def panel_paths():
    """Right half of the panel (u > 0), in mm; mirrored for the left half."""
    strokes = []   # (path, w0, w1)
    # pointed crest: a lancet arch from the base point up to the tip
    crest = _catmull([(0.0, -13.0), (3.6, -7.5), (6.2, 1.5), (5.2, 11.0), (2.4, 18.5), (0.0, 23.5)], 14)
    strokes.append((crest, 0.95, 0.55))
    inner = _catmull([(0.0, -6.0), (2.2, -1.0), (3.0, 5.0), (1.6, 11.5), (0.0, 15.5)], 12)
    strokes.append((inner, 0.6, 0.35))
    # S-scrolls from the crest's foot down and out, ending in volutes
    strokes.append((scroll([(0.0, -13.0), (-0.2, -17.0), (3.0, -20.5), (8.5, -21.5), (12.5, -18.8)],
                           (11.2, -15.6), 3.4, 0.55, 1.25, 1.0), 0.95, 0.3))
    strokes.append((scroll([(4.0, -19.8), (7.0, -25.5), (12.0, -27.8), (16.4, -25.0)],
                           (15.0, -22.6), 2.6, 0.5, 1.15, 1.0), 0.7, 0.3))
    # C-scrolls leaving the crest's flanks, curling back toward the wrist
    strokes.append((scroll([(6.0, 2.0), (10.0, 5.5), (14.5, 5.0), (17.2, 1.4)],
                           (14.6, -0.6), 3.1, 0.5, 1.2, -1.0), 0.85, 0.3))
    strokes.append((scroll([(5.4, 9.5), (9.0, 14.5), (13.2, 16.0)], (13.0, 12.9), 3.0, 0.5, 1.1, -1.0),
                    0.75, 0.3))
    # a tendril from the tip of the crest, rolling outward
    strokes.append((scroll([(0.0, 23.5), (2.0, 27.0), (6.0, 28.8), (9.6, 27.0)], (8.2, 24.6), 2.5, 0.45, 1.1,
                           -1.0), 0.7, 0.28))
    # stem toward the wrist with a small fleur
    strokes.append((_catmull([(0.0, -13.0), (0.0, -24.0), (0.0, -33.0)], 10), 0.85, 0.6))
    strokes.append((scroll([(0.0, -30.0), (2.6, -33.0), (5.6, -33.2)], (5.2, -31.2), 1.8, 0.4, 1.0, 1.0),
                    0.6, 0.28))
    leaves = []
    leaves += leaf((7.0, -1.0), (11.5, -8.5), 1.5)
    leaves += leaf((16.6, -17.2), (20.0, -10.0), 1.3)
    leaves += leaf((9.8, 21.0), (14.4, 23.0), 1.1)
    for lf in leaves:
        strokes.append((lf, 0.42, 0.3))
    dots = [((0.0, 4.5), 0.9), ((0.0, -36.5), 0.8), ((19.5, 4.0), 0.6), ((18.0, -28.5), 0.55)]
    return strokes, dots


def panel():
    ppm = PANEL_PX / (PANEL_SIZE * 1000.0)
    c = Canvas(PANEL_PX, PANEL_PX, ppm, (PANEL_PX * 0.5, PANEL_PX * 0.5))
    strokes, dots = panel_paths()
    for path, w0, w1 in strokes:
        for p in _mirror([path]):
            c.stroke(p, w0, w1)
    for (x, y), r in dots:
        c.dot((x, y), r)
        c.dot((-x, y), r)
    return c.finish()


def band():
    """One running-scroll motif, tileable along U: a wavy stem with a volute above and below."""
    W, H = BAND_PX
    ppm = W / (BAND_LENGTH * 1000.0)
    c = Canvas(W, H, ppm, (0.0, H * 0.5), wrap_x=True)
    L = BAND_LENGTH * 1000.0
    xs = np.linspace(-0.1 * L, 1.1 * L, 80)
    stem = np.c_[xs, 1.8 * np.sin(2 * np.pi * xs / L)]
    c.stroke(stem, 0.7, 0.7)
    up = scroll([(0.18 * L, 1.6), (0.26 * L, 4.0), (0.36 * L, 5.4)], (0.36 * L, 3.2), 2.2, 0.4, 1.1, -1.0)
    down = scroll([(0.68 * L, -1.6), (0.76 * L, -4.0), (0.86 * L, -5.4)], (0.86 * L, -3.2), 2.2, 0.4, 1.1, 1.0)
    c.stroke(up, 0.6, 0.26)
    c.stroke(down, 0.6, 0.26)
    for lf in leaf((0.05 * L, 1.2), (0.12 * L, 5.2), 0.9) + leaf((0.55 * L, -1.2), (0.62 * L, -5.2), 0.9):
        c.stroke(lf, 0.38, 0.28)
    c.dot((0.45 * L, -3.2), 0.5)
    c.dot((0.95 * L, 3.2), 0.5)
    return c.finish()


def to_image(name, height, mask):
    h, w = height.shape
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    px = np.zeros((h, w, 4), dtype=np.float32)
    px[..., 0] = height
    px[..., 1] = mask
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img


def images():
    """(panel image, band image) as packed Blender images."""
    return to_image("filigree_panel", *panel()), to_image("filigree_band", *band())
