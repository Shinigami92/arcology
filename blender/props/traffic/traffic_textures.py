"""Decal canvases for the traffic: taxi roof sign, liveries, logos, destination sign.

Each decal is drawn in meters on a numpy canvas (albedo, ink alpha, emission),
turned into two packed build-time images (`decal_<name>_albedo` with the ink
mask in alpha, `decal_<name>_emit`), sampled by the src_ materials through a
planar projection (lib_candidates.side_uv / end_uv) and baked into the atlas.
The images are removed after baking. All brands and characters are invented.
"""

import numpy as np

from lib_candidates import image_from_canvas, pseudo_glyph, rect_mask, stroke_mask, text_strokes, text_width
from traffic_common import AMBER, MAGENTA


class Canvas:
    """A decal `w` x `h` meters at `px_m` pixels per meter (origin bottom-left)."""

    def __init__(self, w, h, px_m, background=None, background_emit=(0.0, 0.0, 0.0)):
        self.w, self.h, self.px = w, h, px_m
        self.shape = (int(round(h * px_m)), int(round(w * px_m)))
        self.albedo = np.zeros(self.shape + (3,))
        self.alpha = np.zeros(self.shape)
        self.emit = np.zeros(self.shape + (3,))
        if background is not None:
            self.albedo[...] = background
            self.alpha[...] = 1.0
            self.emit[...] = background_emit

    def paint(self, mask, albedo, emit=(0.0, 0.0, 0.0)):
        m = mask[..., None]
        self.albedo = self.albedo * (1 - m) + np.asarray(albedo) * m
        self.emit = self.emit * (1 - m) + np.asarray(emit) * m
        self.alpha = np.maximum(self.alpha, mask)

    def rect(self, x0, y0, x1, y1, albedo, emit=(0.0, 0.0, 0.0), radius=0.0):
        p = self.px
        self.paint(rect_mask(self.shape, x0 * p, y0 * p, x1 * p, y1 * p, radius * p), albedo, emit)

    def strokes(self, segs_m, width_m, albedo, emit=(0.0, 0.0, 0.0)):
        p = self.px
        segs = [((a[0] * p, a[1] * p), (b[0] * p, b[1] * p)) for a, b in segs_m]
        self.paint(stroke_mask(self.shape, segs, width_m * p / 2), albedo, emit)

    def text(self, s, x, y, height, albedo, emit=(0.0, 0.0, 0.0), weight=0.17, center=False, gap=0.35):
        """Stroke text `height` tall at (x, y) bottom-left (or centered on x)."""
        if center:
            x -= text_width(s, height, gap) / 2
        segs, _ = text_strokes(s, x, y, height, gap)
        self.strokes(segs, height * weight, albedo, emit)

    def glyphs(self, seed, count, x, y, size, albedo, emit=(0.0, 0.0, 0.0), weight=0.12, step=1.15, vertical=False):
        rng = np.random.default_rng(seed)
        segs = []
        for i in range(count):
            gx, gy = (x + i * size * step, y) if not vertical else (x, y - i * size * step)
            segs += pseudo_glyph(rng, gx, gy, size)
        self.strokes(segs, size * weight, albedo, emit)

    def images(self, name):
        a = np.concatenate([self.albedo, self.alpha[..., None]], axis=-1)
        e = np.concatenate([self.emit, np.ones(self.shape + (1,))], axis=-1)
        return (image_from_canvas(f"decal_{name}_albedo", a.astype(np.float32), "Non-Color"),
                image_from_canvas(f"decal_{name}_emit", e.astype(np.float32), "Non-Color"))


INK = (0.012, 0.012, 0.014)
WHITE = (0.70, 0.70, 0.68)
DARK = (0.010, 0.010, 0.012)


def taxi_sign_side():
    """Roof sign side, 1.0 x 0.28 m: glowing invented kanji | backlit 'TAXI' panel."""
    c = Canvas(1.0, 0.28, 512, background=DARK)
    c.rect(0.39, 0.03, 0.97, 0.25, (0.80, 0.70, 0.40), tuple(0.62 * k for k in (1.0, 0.80, 0.42)), radius=0.02)
    c.text("TAXI", 0.68, 0.065, 0.15, INK, center=True, weight=0.2)
    c.glyphs(11, 2, 0.045, 0.055, 0.15, (0.8, 0.3, 0.45), tuple(0.95 * k for k in MAGENTA), weight=0.13, step=1.18)
    return c.images("taxi_sign_side")


def taxi_sign_end():
    """Roof sign ends, 0.26 x 0.28 m: backlit panel with one dark glyph."""
    c = Canvas(0.26, 0.28, 512, background=DARK)
    c.rect(0.02, 0.03, 0.24, 0.25, (0.80, 0.70, 0.40), tuple(0.62 * k for k in (1.0, 0.80, 0.42)), radius=0.02)
    c.glyphs(23, 1, 0.05, 0.065, 0.16, INK, weight=0.15)
    return c.images("taxi_sign_end")


def taxi_door():
    """Rear door, 0.9 x 0.26 m (ink only): cab number and operator glyphs."""
    c = Canvas(0.9, 0.26, 384)
    c.text("4096", 0.04, 0.05, 0.15, INK, weight=0.18)
    c.glyphs(5, 3, 0.48, 0.06, 0.12, INK, weight=0.13)
    return c.images("taxi_door")


def van_logo():
    """Cargo box side, 3.4 x 1.15 m: HAKO EXPRESS, a backlit cube mark, glyphs."""
    c = Canvas(3.4, 1.15, 256)
    cx, cy, r = 0.55, 0.58, 0.40  # cube mark: hexagon with a Y inside
    hexa = [(cx + r * np.cos(np.radians(90 + 60 * k)), cy + r * np.sin(np.radians(90 + 60 * k))) for k in range(7)]
    segs = list(zip(hexa[:-1], hexa[1:]))
    segs += [((cx, cy), hexa[k]) for k in (2, 4)] + [((cx, cy), (cx, cy - r))]
    c.rect(cx - r - 0.06, cy - r - 0.06, cx + r + 0.06, cy + r + 0.06, (0.03, 0.03, 0.035), radius=0.08)
    c.strokes(segs, 0.075, (0.95, 0.62, 0.15), tuple(0.9 * k for k in AMBER))
    c.text("HAKO", 1.12, 0.46, 0.50, (0.025, 0.026, 0.03), weight=0.19)
    c.text("EXPRESS", 1.14, 0.12, 0.20, (0.85, 0.42, 0.04), weight=0.2)
    c.glyphs(41, 3, 2.62, 0.13, 0.20, (0.025, 0.026, 0.03), weight=0.13)
    return c.images("van_logo")


def patrol_side():
    """Door band text, 2.3 x 0.30 m (ink only): unit glyphs, PATROL, number."""
    c = Canvas(2.3, 0.30, 384)
    c.glyphs(77, 2, 0.06, 0.06, 0.17, (0.02, 0.03, 0.08), weight=0.13)
    c.text("PATROL", 0.62, 0.065, 0.17, (0.02, 0.03, 0.08), weight=0.19)
    c.text("07", 1.92, 0.05, 0.20, (0.02, 0.03, 0.08), weight=0.2)
    return c.images("patrol_side")


def bus_destination():
    """Front destination sign, 1.6 x 0.26 m: amber LED route and stop."""
    c = Canvas(1.6, 0.26, 512, background=DARK)
    c.text("12", 0.08, 0.055, 0.15, (0.6, 0.35, 0.05), tuple(0.95 * k for k in AMBER), weight=0.2)
    c.text("KAZE", 0.50, 0.055, 0.15, (0.6, 0.35, 0.05), tuple(0.85 * k for k in AMBER), weight=0.17)
    c.glyphs(9, 2, 1.18, 0.05, 0.16, (0.6, 0.35, 0.05), tuple(0.85 * k for k in AMBER), weight=0.11)
    return c.images("bus_destination")


def bus_side():
    """Lower body livery, 4.6 x 0.55 m (ink only): operator and a big line number."""
    c = Canvas(4.6, 0.55, 192)
    c.text("ARC TRANSIT", 0.0, 0.16, 0.22, (0.62, 0.62, 0.60), weight=0.17)
    c.glyphs(13, 3, 2.75, 0.16, 0.22, (0.62, 0.62, 0.60), weight=0.12)
    c.rect(3.70, 0.04, 4.55, 0.51, (0.70, 0.40, 0.03), radius=0.05)
    c.text("12", 4.125, 0.10, 0.34, (0.02, 0.02, 0.02), weight=0.2, center=True)
    return c.images("bus_side")


def bus_rear():
    """Rear route number, 0.9 x 0.30 m: a lit amber LED panel."""
    c = Canvas(0.9, 0.30, 384, background=DARK)
    c.text("12", 0.45, 0.07, 0.17, (0.6, 0.35, 0.05), tuple(0.85 * k for k in AMBER), weight=0.2, center=True)
    return c.images("bus_rear")


def build_all():
    return {
        "taxi_sign_side": taxi_sign_side(),
        "taxi_sign_end": taxi_sign_end(),
        "taxi_door": taxi_door(),
        "van_logo": van_logo(),
        "patrol_side": patrol_side(),
        "bus_destination": bus_destination(),
        "bus_side": bus_side(),
        "bus_rear": bus_rear(),
    }

