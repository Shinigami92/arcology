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


if __name__ == "__main__":
    write_wav("ball_bounce", ball_bounce())
    write_wav("can_hit", can_hit())
    write_wav("trash_accept", trash_accept())
    write_wav("door_bump", door_bump())
