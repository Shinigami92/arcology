"""Stage-3 ornament images (numpy, deterministic), sampled by the procedural materials
and baked:

- `vine(length_mm)`: the coat's front panels carry the sleeve's vine (embroidery.band,
  the same design, as long as the panel) at a lower resolution: the coat body's atlas
  has ~1 texel per mm, the sleeve's ~3.
- `hem_border()`: a running scroll border for the coat's hem, tileable along x (one
  period HEM_PERIOD wide): a wavy stem with scrolls curling alternately up and down,
  lancet leaves and dots, satin-stitched like the vine.
- `lace()`: the top's black lace, tileable in both directions (LACE_TILE): a net of
  fine threads, roses of filled petals around a seed with corded outlines, scrolling
  stems between them. R = height, G = coverage (1 = lace, 0 = the violet underlayer
  shows through), B = the cord (outline) mask.

Images are float RGBA, Non-Color (embroidery.to_image layout: R height, G mask, B thread).
"""

import math

import numpy as np

import embroidery as E
from filigree import _catmull, scroll

LOW_PX_MM = 3.0
HEM_PERIOD = 120.0           # mm
HEM_HEIGHT = 64.0
LACE_TILE = 72.0             # mm
LACE_PX_MM = 6.0


class _Res:
    """Temporarily change embroidery.PX_MM (SatinCanvas reads the module value)."""

    def __init__(self, px):
        self.px = px

    def __enter__(self):
        self.old = E.PX_MM
        E.PX_MM = self.px

    def __exit__(self, *args):
        E.PX_MM = self.old


def vine(length_mm):
    with _Res(LOW_PX_MM):
        return E.band(length_mm)


def hem_border():
    """One period of the hem border: x 0..HEM_PERIOD (wraps), y 0..HEM_HEIGHT up from the hem."""
    P, H = HEM_PERIOD, HEM_HEIGHT
    with _Res(LOW_PX_MM):
        c = E.SatinCanvas(3 * P, H, (P, 0.0))
        y0 = H * 0.47

        def stem_y(x):
            return y0 + 5.5 * np.sin(2.0 * np.pi * x / P * 2.0)

        for shift in (-P, 0.0, P):
            xs = np.linspace(0.0, P, 80)
            c.stroke(np.c_[xs + shift, stem_y(xs)], 2.6, 2.6)
            for k in range(4):
                side = 1.0 if k % 2 == 0 else -1.0
                x = P * (k + 0.5) / 4.0 + shift
                sy = float(stem_y(x - shift))
                pts = [(x, sy), (x + 6.0, sy + side * 7.0), (x + 13.0, sy + side * 12.5), (x + 18.0, sy + side * 11.0)]
                c.stroke(scroll(pts, (x + 15.5, sy + side * 7.2), 4.0, 0.8, 1.15, -side), 2.6, 1.0)
                _leafy(c, (x - 1.5, sy + side * 2.0), (x - 9.0, sy + side * 17.0), 3.0)
                _leafy(c, (x + 4.0, sy - side * 2.5), (x + 11.0, sy - side * 12.0), 2.2)
                c.dot((x - 8.0, sy - side * 9.0), 1.3)
                c.dot((x + 22.5, sy + side * 4.5), 1.0)
            # a thin line of satin along the hem and above the border
            c.stroke(np.c_[np.linspace(0.0, P, 40) + shift, np.full(40, 4.0)], 1.6, 1.6)
            c.stroke(np.c_[np.linspace(0.0, P, 40) + shift, np.full(40, H - 4.0)], 1.4, 1.4)
        h, m, t = c.finish()
        w = int(round(P * LOW_PX_MM))
        return h[:, w:2 * w], m[:, w:2 * w], t[:, w:2 * w]


def _leafy(c, base, tip, width):
    E._leaf(c, base, tip, width)


def lace():
    """The lace tile (LACE_TILE mm square, wraps in x and y)."""
    T = LACE_TILE
    with _Res(LACE_PX_MM):
        c = E.SatinCanvas(3 * T, 3 * T, (T, T))
        cords = E.SatinCanvas(3 * T, 3 * T, (T, T))
        for sx in (-T, 0.0, T):
            for sy in (-T, 0.0, T):
                _lace_tile(c, cords, sx, sy)
        h, m, _ = c.finish()
        hc, mc, _ = cords.finish()
        n = int(round(T * LACE_PX_MM))
        crop = (slice(n, 2 * n), slice(n, 2 * n))
        net = _net(n)
        height = np.maximum(np.maximum(h[crop] * 0.7, hc[crop]), net * 0.45)
        mask = np.clip(np.maximum(m[crop] + mc[crop], net), 0.0, 1.0)
        return height, mask, mc[crop]


def _net(n, lines=16, width_mm=0.42):
    """Tulle: threads along both diagonals and horizontally, periodic in the tile."""
    T = LACE_TILE
    px = T / n
    y, x = (np.mgrid[0:n, 0:n] + 0.5) * px
    d = T / lines
    out = np.zeros((n, n))
    for v, scale in ((x + y, 1.0 / math.sqrt(2.0)), (x - y, 1.0 / math.sqrt(2.0)), (y * 2.0, 0.5)):
        dist = np.abs(((v / d) + 0.5) % 1.0 - 0.5) * d * scale
        out = np.maximum(out, np.clip(1.0 - dist / (width_mm * 0.5), 0.0, 1.0))
    return out


def _lace_tile(c, cords, sx, sy):
    T = LACE_TILE
    # roses at the tile's center and corners (half-offset rows, so they tile)
    for cx, cy in ((T * 0.5, T * 0.5), (0.0, 0.0)):
        cx, cy = cx + sx, cy + sy
        for k in range(5):
            a = 2.0 * math.pi * k / 5.0 + 0.3
            tip = (cx + 12.0 * math.cos(a), cy + 12.0 * math.sin(a))
            base = (cx + 2.5 * math.cos(a), cy + 2.5 * math.sin(a))
            E._leaf(c, base, tip, 5.2)
            outline = _catmull([base, (cx + 8.0 * math.cos(a + 0.42), cy + 8.0 * math.sin(a + 0.42)), tip,
                                (cx + 8.0 * math.cos(a - 0.42), cy + 8.0 * math.sin(a - 0.42)), base], 8)
            cords.stroke(outline, 0.9, 0.9)
        cords.dot((cx, cy), 2.6)
        # scrolling stems toward the neighbors
        for k in range(4):
            a = math.pi * 0.5 * k + 0.785
            p = [(cx + 13.0 * math.cos(a), cy + 13.0 * math.sin(a)),
                 (cx + 19.0 * math.cos(a + 0.25), cy + 19.0 * math.sin(a + 0.25)),
                 (cx + 23.0 * math.cos(a - 0.05), cy + 23.0 * math.sin(a - 0.05))]
            ctr = (cx + 21.5 * math.cos(a - 0.22), cy + 21.5 * math.sin(a - 0.22))
            cords.stroke(scroll(p, ctr, 2.6, 0.6, 1.0, 1.0 if k % 2 else -1.0), 1.1, 0.7)
            E._leaf(c, (cx + 16.0 * math.cos(a + 0.5), cy + 16.0 * math.sin(a + 0.5)),
                    (cx + 22.0 * math.cos(a + 0.75), cy + 22.0 * math.sin(a + 0.75)), 2.2)
