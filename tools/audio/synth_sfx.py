"""Synthesizes placeholder sound effects into assets/audio/sfx/.

Deterministic (fixed seeds), stdlib only, so the WAVs can be regenerated
anytime: python tools/audio/synth_sfx.py

Replace any of these with recorded or better-designed sounds later; keep the
file names so scenes don't need to change.
"""

import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parents[2] / "assets" / "audio" / "sfx"


def write_wav(name: str, samples: list[float]) -> None:
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = 0.89 / peak  # normalize to about -1 dBFS
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(b"".join(struct.pack("<h", int(s * scale * 32767)) for s in samples))
    print(f"wrote {name}.wav ({len(samples) / RATE:.2f} s)")


def env(t: float, attack: float, decay: float) -> float:
    if t < attack:
        return t / attack
    return math.exp(-(t - attack) / decay)


def lowpass(samples: list[float], alpha: float) -> list[float]:
    out, y = [], 0.0
    for s in samples:
        y += alpha * (s - y)
        out.append(y)
    return out


def ball_bounce() -> list[float]:
    """Rubber ball on a hard floor: pitched thump with a falling pitch plus a short click."""
    rng = random.Random(1)
    n = int(RATE * 0.25)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.35)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        freq = 150 + 170 * math.exp(-t / 0.015)
        phase += 2 * math.pi * freq / RATE
        body = math.sin(phase) * env(t, 0.001, 0.045)
        click = noise[i] * env(t, 0.0005, 0.004)
        out.append(0.9 * body + 0.5 * click)
    return out


def can_hit() -> list[float]:
    """Thin aluminum can: bright, inharmonic partials with fast decay."""
    rng = random.Random(2)
    n = int(RATE * 0.35)
    partials = [(1180, 0.06, 1.0), (2270, 0.045, 0.7), (3410, 0.03, 0.5), (4930, 0.02, 0.35), (6100, 0.015, 0.25)]
    phases = [rng.uniform(0, 2 * math.pi) for _ in partials]
    out = []
    for i in range(n):
        t = i / RATE
        s = sum(a * math.sin(2 * math.pi * f * t + p) * env(t, 0.0005, d) for (f, d, a), p in zip(partials, phases))
        s += rng.uniform(-1, 1) * 0.6 * env(t, 0.0003, 0.003)
        out.append(s)
    return out


def trash_accept() -> list[float]:
    """Item landing in a bin bag: soft low thud plus a plastic rustle."""
    rng = random.Random(3)
    n = int(RATE * 0.5)
    rustle = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.5)
    out = []
    for i in range(n):
        t = i / RATE
        thud = math.sin(2 * math.pi * (90 + 60 * math.exp(-t / 0.02)) * t) * env(t, 0.002, 0.06)
        crackle = rustle[i] * env(t, 0.01, 0.12) * (0.6 + 0.4 * math.sin(2 * math.pi * 23 * t))
        out.append(0.8 * thud + 0.35 * crackle)
    return out


def door_bump() -> list[float]:
    """Wooden door hitting its stop or frame: dull knock."""
    rng = random.Random(4)
    n = int(RATE * 0.3)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.2)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.7 * math.sin(2 * math.pi * 110 * t) * env(t, 0.001, 0.05)
        s += 0.4 * math.sin(2 * math.pi * 237 * t) * env(t, 0.001, 0.03)
        s += 0.5 * noise[i] * env(t, 0.0005, 0.01)
        out.append(s)
    return out


def fridge_seal() -> list[float]:
    """Fridge door unsticking from its rubber seal: soft suction pop and a breath of air."""
    rng = random.Random(5)
    n = int(RATE * 0.35)
    raw = [rng.uniform(-1, 1) for _ in range(n)]
    out, y = [], 0.0
    for i in range(n):
        t = i / RATE
        alpha = 0.02 + 0.25 * math.exp(-t / 0.03)  # filter closes: pop, then air
        y += alpha * (raw[i] - y)
        pop = math.sin(2 * math.pi * (90 + 120 * math.exp(-t / 0.01)) * t) * env(t, 0.002, 0.025)
        air = y * env(t, 0.01, 0.12)
        out.append(0.8 * pop + 1.4 * air)
    return out


def fridge_close() -> list[float]:
    """Fridge door closing: padded thump, seal puff and a faint bottle clink."""
    rng = random.Random(6)
    n = int(RATE * 0.45)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.08)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.8 * math.sin(2 * math.pi * 70 * t) * env(t, 0.003, 0.06)
        s += 0.3 * math.sin(2 * math.pi * 143 * t) * env(t, 0.002, 0.04)
        s += 0.9 * noise[i] * env(t, 0.004, 0.05)
        tc = t - 0.06  # bottles in the door bins
        if tc > 0:
            clink = sum(math.sin(2 * math.pi * f * tc) for f in (2350, 3710, 5230)) / 3
            s += 0.06 * clink * env(tc, 0.0005, 0.03)
        out.append(s)
    return out


def fridge_hum() -> list[float]:
    """Compressor hum, 4 s seamless loop (import with loop mode Forward)."""
    rng = random.Random(7)
    seconds = 4.0
    n = int(RATE * seconds)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.01)
    fade = int(RATE * 0.5)
    # Make the noise periodic: crossfade its tail into its head.
    for i in range(fade):
        w = i / fade
        noise[i] = noise[i] * w + noise[n - fade + i] * (1 - w)
    noise = noise[: n - fade]
    n = len(noise)
    base = round(50 * n / RATE) * RATE / n  # whole cycles per loop
    out = []
    for i in range(n):
        t = i / RATE
        wobble = 1 + 0.08 * math.sin(2 * math.pi * t * RATE / n)  # one slow swell per loop
        s = 0.5 * math.sin(2 * math.pi * base * t) + 0.35 * math.sin(2 * math.pi * 2 * base * t)
        s += 0.12 * math.sin(2 * math.pi * 3 * base * t)
        out.append(wobble * s * 0.6 + 3.0 * noise[i])
    return out


def pillow_thud() -> list[float]:
    """Throw pillow landing: soft, muffled whump with a short fabric rustle."""
    rng = random.Random(8)
    n = int(RATE * 0.3)
    low = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.03)
    hiss = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.35)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.6 * math.sin(2 * math.pi * (55 + 40 * math.exp(-t / 0.02)) * t) * env(t, 0.006, 0.05)
        s += 2.5 * low[i] * env(t, 0.004, 0.06)
        s += 0.12 * hiss[i] * env(t, 0.01, 0.07)
        out.append(s)
    return out


def button_click() -> list[float]:
    """Small plastic push button: a short, bright double click."""
    rng = random.Random(9)
    n = int(RATE * 0.08)
    noise = [rng.uniform(-1, 1) for _ in range(n)]
    out = []
    for i in range(n):
        t = i / RATE
        s = noise[i] * env(t, 0.0003, 0.003) + 0.6 * noise[i] * env(t - 0.03, 0.0003, 0.004) * (t > 0.03)
        s += 0.4 * math.sin(2 * math.pi * 2400 * t) * env(t, 0.0003, 0.006)
        out.append(s)
    return out


def drawer_bump() -> list[float]:
    """Wooden drawer reaching its stop: short hollow knock with a rattle."""
    rng = random.Random(10)
    n = int(RATE * 0.25)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.25)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.6 * math.sin(2 * math.pi * 180 * t) * env(t, 0.001, 0.035)
        s += 0.35 * math.sin(2 * math.pi * 410 * t) * env(t, 0.001, 0.02)
        s += 0.5 * noise[i] * env(t, 0.0005, 0.012)
        tr = t - 0.04
        if tr > 0:
            s += 0.15 * noise[i] * env(tr, 0.001, 0.02)
        out.append(s)
    return out


def fridge_alarm() -> list[float]:
    """Door-open alarm: three short 2.6 kHz beeps, then a pause; 2 s seamless loop
    (import with loop mode Forward)."""
    n = int(RATE * 2.0)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.0
        for start in (0.0, 0.18, 0.36):
            tb = t - start
            if 0.0 <= tb < 0.1:
                gate = min(1.0, tb / 0.004, (0.1 - tb) / 0.004)
                s += gate * (math.sin(2 * math.pi * 2600 * t) + 0.25 * math.sin(2 * math.pi * 5200 * t))
        out.append(s)
    return out


def _loop_noise(rng: random.Random, n: int, alpha: float, fade_s: float = 0.5) -> list[float]:
    """Lowpassed noise made periodic (tail crossfaded into the head); returns n - fade samples."""
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], alpha)
    fade = int(RATE * fade_s)
    for i in range(fade):
        w = i / fade
        noise[i] = noise[i] * w + noise[n - fade + i] * (1 - w)
    return noise[: n - fade]


def shade_motor() -> list[float]:
    """Roller-shade tube motor: soft buzz, gear whine and a little air; seamless
    loop (import with loop mode Forward)."""
    rng = random.Random(11)
    noise = _loop_noise(rng, int(RATE * 2.5), 0.05)
    n = len(noise)
    hiss = _loop_noise(random.Random(12), int(RATE * 2.5), 0.4)
    # Whole cycles per loop for every partial.
    def f(hz: float) -> float:
        return round(hz * n / RATE) * RATE / n
    buzz, whine, wob = f(118), f(940), f(3)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.5 * math.sin(2 * math.pi * buzz * t) + 0.25 * math.sin(2 * math.pi * 2 * buzz * t)
        s += 0.12 * math.sin(2 * math.pi * 3 * buzz * t)
        s += 0.06 * math.sin(2 * math.pi * whine * t) * (1 + 0.3 * math.sin(2 * math.pi * wob * t))
        out.append(s * 0.5 + 2.5 * noise[i] + 0.05 * hiss[i])
    return out


def tint_tone() -> list[float]:
    """Smart glass changing: a soft, glassy two-note tone."""
    n = int(RATE * 1.0)
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.6 * math.sin(2 * math.pi * 880 * t) * env(t, 0.02, 0.3)
        t2 = t - 0.12
        if t2 > 0:
            s += 0.5 * math.sin(2 * math.pi * 1318.5 * t2) * env(t2, 0.02, 0.4)
            s += 0.08 * math.sin(2 * math.pi * 2637 * t2) * env(t2, 0.01, 0.15)
        out.append(s * (1 + 0.04 * math.sin(2 * math.pi * 5 * t)))
    return out


def vent_latch() -> list[float]:
    """Window sash catching in its frame: a firm plastic-and-metal click-clack."""
    rng = random.Random(13)
    n = int(RATE * 0.25)
    noise = [rng.uniform(-1, 1) for _ in range(n)]
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.6 * math.sin(2 * math.pi * 140 * t) * env(t, 0.001, 0.03)
        s += 0.5 * noise[i] * env(t, 0.0003, 0.004)
        s += 0.2 * math.sin(2 * math.pi * 1850 * t) * env(t, 0.0005, 0.012)
        t2 = t - 0.055
        if t2 > 0:
            s += 0.7 * noise[i] * env(t2, 0.0003, 0.003)
            s += 0.3 * math.sin(2 * math.pi * 3100 * t2) * env(t2, 0.0005, 0.02)
            s += 0.3 * math.sin(2 * math.pi * 210 * t2) * env(t2, 0.001, 0.025)
        out.append(s)
    return out


def city_ambience() -> list[float]:
    """The city through an open window: low traffic rumble, far hiss and slow
    swells of passing vehicles; 8 s seamless loop (import with loop mode Forward)."""
    rng = random.Random(14)
    rumble = _loop_noise(rng, int(RATE * 8.5), 0.004)
    body = _loop_noise(random.Random(15), int(RATE * 8.5), 0.05)
    hiss = _loop_noise(random.Random(16), int(RATE * 8.5), 0.5)
    n = len(rumble)
    period = n / RATE
    out = []
    for i in range(n):
        t = i / RATE
        # Swells: whole cycles per loop so the loop stays seamless.
        swell = 0.5 + 0.3 * math.sin(2 * math.pi * 2 * t / period) + 0.2 * math.sin(2 * math.pi * 5 * t / period + 1.3)
        s = 6.0 * rumble[i] + 1.2 * body[i] * swell + 0.04 * hiss[i]
        out.append(s)
    return out


def _ticks(rng: random.Random, n: int, rate_hz: float, dur: float, lo: float, hi: float, gain: float) -> list[float]:
    """Random short noise ticks (drops hitting something), wrapped around the end so the loop stays seamless."""
    out = [0.0] * n
    length = int(RATE * dur)
    for _ in range(int(rate_hz * n / RATE)):
        start = rng.randrange(n)
        amp = gain * rng.uniform(0.2, 1.0) ** 2
        f = rng.uniform(lo, hi)
        phase = rng.uniform(0, 2 * math.pi)
        for k in range(length):
            t = k / RATE
            e = math.exp(-t / (dur * 0.25))
            v = amp * e * (math.sin(2 * math.pi * f * t + phase) * 0.6 + rng.uniform(-1, 1) * 0.4)
            out[(start + k) % n] += v
    return out


def rain_patter() -> list[float]:
    """Rain on a window pane from inside: dense soft ticks on the glass over a
    muffled hiss; 5 s seamless loop (import with loop mode Forward)."""
    rng = random.Random(17)
    hiss = _loop_noise(rng, int(RATE * 5.5), 0.12)
    n = len(hiss)
    ticks = _ticks(random.Random(18), n, 260.0, 0.012, 1800, 4200, 0.35)
    heavy = _ticks(random.Random(19), n, 18.0, 0.03, 500, 1200, 0.6)
    return [1.4 * hiss[i] + lowpass_one(ticks[i] + heavy[i]) for i in range(n)]


def rain_outside() -> list[float]:
    """Heavy rain outside an open window: broadband roar, splashes and drips on
    the sill; 6 s seamless loop (import with loop mode Forward)."""
    rng = random.Random(20)
    roar = _loop_noise(rng, int(RATE * 6.5), 0.35)
    n = len(roar)
    body = _loop_noise(random.Random(21), int(RATE * 6.5), 0.04)
    splashes = _ticks(random.Random(22), n, 120.0, 0.02, 900, 3000, 0.4)
    drips = _ticks(random.Random(23), n, 3.0, 0.06, 350, 700, 0.8)
    return [0.9 * roar[i] + 2.0 * body[i] + splashes[i] + drips[i] for i in range(n)]


_lp_state = [0.0]


def lowpass_one(x: float, alpha: float = 0.45) -> float:
    """One-pole lowpass with module state (softens the glass ticks)."""
    _lp_state[0] += alpha * (x - _lp_state[0])
    return _lp_state[0]


def _flush(seed: int, dur: float, rush: float) -> list[float]:
    """Concealed-cistern flush: the button's clack and the valve's thunk, a rush of water
    into the bowl with a swirl, gurgling bubbles as the bowl siphons empty, then the
    cistern refilling (a fading hiss). `rush` = seconds of full water flow."""
    rng = random.Random(seed)
    n = int(RATE * dur)
    white = [rng.uniform(-1, 1) for _ in range(n)]
    roar = lowpass(white, 0.16)
    low = lowpass(lowpass(white, 0.025), 0.05)
    hiss = [w - r for w, r in zip(white, lowpass(white, 0.5))]  # highpassed: the refill valve
    # Bubbles: short chirps (rising pitch), densest as the bowl siphons empty.
    bubbles = [0.0] * n
    for _ in range(int(9 * rush)):
        start_t = rng.uniform(0.4 * rush, rush + 0.9)
        f0 = rng.uniform(170, 480)
        length = rng.uniform(0.03, 0.08)
        amp = rng.uniform(0.2, 1.0) ** 2
        start = int(start_t * RATE)
        for k in range(int(length * RATE)):
            if start + k >= n:
                break
            t = k / RATE
            bubbles[start + k] += amp * math.sin(2 * math.pi * f0 * (t + t * t / length)) * env(t, 0.003, length / 3)
    out = []
    t_rush = 0.15
    for i in range(n):
        t = i / RATE
        s = 0.5 * white[i] * env(t, 0.0005, 0.006) + 0.5 * math.sin(2 * math.pi * 420 * t) * env(t, 0.001, 0.02)
        t2 = t - 0.11
        if t2 > 0:
            s += 0.7 * math.sin(2 * math.pi * 85 * t2) * env(t2, 0.003, 0.07)
        tr = t - t_rush
        if tr > 0:
            if tr < 0.35:
                flow = tr / 0.35
            elif tr < rush:
                flow = 1.0
            else:
                flow = math.exp(-(tr - rush) / 0.55)
            swirl = 1.0 + 0.22 * math.sin(2 * math.pi * 2.7 * t + 0.6 * math.sin(2 * math.pi * 0.7 * t))
            s += flow * swirl * (2.2 * roar[i] + 5.0 * low[i])
            # The siphon: a deep gurgle swelling at the end of the rush.
            gurgle = math.exp(-((tr - rush) / 0.5) ** 2)
            s += gurgle * (7.0 * low[i] * (0.6 + 0.4 * math.sin(2 * math.pi * 6.5 * t)) + 0.5 * bubbles[i])
            s += 0.25 * bubbles[i] * flow
            # Refill: starts with the rush, fades out by the end.
            refill = min(1.0, tr / 0.5) * max(0.0, 1.0 - tr / (dur - t_rush))
            s += 0.12 * refill * hiss[i]
        fade = min(1.0, (dur - t) / 0.3)
        out.append(s * fade)
    return out


def toilet_flush_short() -> list[float]:
    """Small (half) flush: about 1.5 s of water, 4 s with the refill."""
    return _flush(24, 4.0, 1.5)


def toilet_flush_full() -> list[float]:
    """Large (full) flush: about 3 s of water, 7 s with the refill."""
    return _flush(25, 7.0, 3.0)


def deadbolt() -> list[float]:
    """A deadbolt thrown by its thumb-turn: a short steel slide, then a solid clunk as it seats."""
    rng = random.Random(21)
    n = int(RATE * 0.35)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.35)
    out = []
    for i in range(n):
        t = i / RATE
        # Slide: filtered scrape rising then cut off when the bolt seats.
        s = 0.25 * noise[i] * (min(1.0, t / 0.05) if t < 0.11 else math.exp(-(t - 0.11) / 0.004))
        t2 = t - 0.11
        if t2 > 0:
            s += 0.9 * math.sin(2 * math.pi * 95 * t2) * env(t2, 0.001, 0.045)
            s += 0.45 * math.sin(2 * math.pi * 410 * t2) * env(t2, 0.0005, 0.02)
            s += 0.5 * noise[i] * env(t2, 0.0003, 0.006)
            s += 0.12 * math.sin(2 * math.pi * 2650 * t2) * env(t2, 0.0005, 0.05)
        out.append(s)
    return out


def door_rattle() -> list[float]:
    """A locked door pulled by its lever: the leaf knocks twice against the bolt, the lever clacks."""
    rng = random.Random(22)
    n = int(RATE * 0.45)
    noise = [rng.uniform(-1, 1) for _ in range(n)]
    out = []
    for i in range(n):
        t = i / RATE
        s = 0.0
        for at, gain in ((0.0, 1.0), (0.11, 0.7), (0.19, 0.35)):
            t2 = t - at
            if t2 > 0:
                s += gain * 0.8 * math.sin(2 * math.pi * 120 * t2) * env(t2, 0.001, 0.05)
                s += gain * 0.4 * noise[i] * env(t2, 0.0003, 0.005)
                s += gain * 0.2 * math.sin(2 * math.pi * 1720 * t2) * env(t2, 0.0005, 0.03)
        out.append(s)
    return out


def lock_beep(rising: bool) -> list[float]:
    """Smart lock confirmation: two short soft beeps, rising (locked) or falling (unlocked)."""
    n = int(RATE * 0.26)
    tones = (1568.0, 2093.0) if rising else (2093.0, 1568.0)
    out = []
    for i in range(n):
        t = i / RATE
        k = 0 if t < 0.13 else 1
        t2 = t - 0.13 * k
        a = min(1.0, t2 / 0.004) * min(1.0, max(0.0, 0.09 - t2) / 0.01)
        out.append(a * math.sin(2 * math.pi * tones[k] * t2))
    return out


def shower_spray() -> list[float]:
    """Water from a shower head on tiles: dense bright hiss with a softer splash layer;
    4 s seamless loop (import with loop mode Forward)."""
    rng = random.Random(23)
    hiss = _loop_noise(rng, int(RATE * 4.5), 0.55)
    body = _loop_noise(rng, int(RATE * 4.5), 0.08)
    drops = _ticks(rng, len(hiss), 140.0, 0.004, 1800.0, 4200.0, 0.35)
    out = [0.55 * h + 0.9 * b + d for h, b, d in zip(hiss, body, drops)]
    return out


# In this order (rain_patter's lowpass keeps state across calls).
SOUNDS = [
    ("ball_bounce", ball_bounce), ("can_hit", can_hit), ("trash_accept", trash_accept), ("door_bump", door_bump),
    ("fridge_seal", fridge_seal), ("fridge_close", fridge_close), ("fridge_hum", fridge_hum),
    ("pillow_thud", pillow_thud), ("button_click", button_click), ("drawer_bump", drawer_bump),
    ("fridge_alarm", fridge_alarm), ("shade_motor", shade_motor), ("tint_tone", tint_tone),
    ("vent_latch", vent_latch), ("city_ambience", city_ambience), ("rain_patter", rain_patter),
    ("rain_outside", rain_outside), ("toilet_flush_short", toilet_flush_short),
    ("toilet_flush_full", toilet_flush_full), ("deadbolt", deadbolt), ("door_rattle", door_rattle),
    ("lock_beep_locked", lambda: lock_beep(True)), ("lock_beep_unlocked", lambda: lock_beep(False)),
    ("shower_spray", shower_spray),
]


if __name__ == "__main__":
    # python tools/audio/synth_sfx.py [name ...]: all sounds, or only the named ones.
    import sys
    wanted = set(sys.argv[1:])
    unknown = wanted - {name for name, _ in SOUNDS}
    if unknown:
        sys.exit(f"unknown sound(s): {', '.join(sorted(unknown))}")
    for name, make in SOUNDS:
        if not wanted or name in wanted:
            write_wav(name, make())
