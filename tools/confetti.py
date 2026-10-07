import math
from dataclasses import dataclass

import numpy as np

KEY_STEP = 3
DECAY = 0.9
GRAVITY = 3.5
WOBBLE_AMPLITUDE = 10.0
FADE_START = 0.6
LAUNCH_SPREAD_FRAMES = 6
CIRCLE_SHARE = 0.25
BACK_SHARE = 0.5
BACK_SCALE = 0.75
PIECE_SIZE = (20.0, 12.0)
CIRCLE_SIZE = 12.0


@dataclass
class Piece:
    shape: str
    width: float
    height: float
    color: str
    behind: bool
    x: list
    y: list
    rotation: list
    scale_y: list
    opacity: list


def simulate_piece(rng, origin, aim, settings, duration):
    launch = int(rng.integers(0, LAUNCH_SPREAD_FRAMES + 1))
    life = int(rng.integers(settings.life[0], settings.life[1] + 1))
    end = min(launch + life, duration)
    angle = math.radians(aim + rng.uniform(-settings.spread / 2, settings.spread / 2))
    velocity = settings.speed * (0.5 + 0.5 * rng.random())
    wobble, wobble_speed = rng.uniform(0, 2 * math.pi), min(0.11, rng.random() * 0.1 + 0.05)
    tilt, tilt_speed = rng.uniform(0, 2 * math.pi), rng.uniform(0.05, 0.15)
    spin = rng.uniform(-0.12, 0.12)
    rotation = rng.uniform(0, 2 * math.pi)

    x, y = origin
    samples = []
    for frame in range(launch, end + 1):
        progress = (frame - launch) / (end - launch)
        fade = max(0.0, (progress - FADE_START) / (1 - FADE_START))
        samples.append(
            (frame, x + WOBBLE_AMPLITUDE * math.cos(wobble), y, rotation, math.cos(tilt), 1.0 - fade)
        )
        x += math.cos(angle) * velocity
        y -= math.sin(angle) * velocity - GRAVITY
        velocity *= DECAY
        wobble += wobble_speed
        tilt += tilt_speed
        rotation += spin
    return launch, end, samples


def bake(samples, launch, end, duration):
    keep = [s for s in samples if (s[0] - launch) % KEY_STEP == 0 or s[0] == end]
    columns = list(zip(*keep))
    frames = columns[0]
    tracks = [list(zip(frames, values)) for values in columns[1:5]]
    opacity = [(0, 1.0)] if launch == 0 else sorted({0: 0.0, launch - 1: 0.0, launch: 1.0}.items())
    opacity += [(f, o) for f, o in zip(frames, columns[5]) if o < 1.0]
    if end < duration:
        opacity.append((duration, 0.0))
    for track in tracks:
        if launch > 0:
            track.insert(0, (0, track[0][1]))
    return tracks + [opacity]


def build_pieces(settings, to_world):
    rng = np.random.default_rng(settings.seed)
    duration = settings.duration
    pieces = []
    for index in range(settings.pieces):
        cannon = settings.cannons[index % len(settings.cannons)]
        launch, end, samples = simulate_piece(rng, to_world(cannon.at), cannon.angle, settings, duration)
        x, y, rotation, scale_y, opacity = bake(samples, launch, end, duration)
        circle = rng.random() < CIRCLE_SHARE
        behind = rng.random() < BACK_SHARE
        scale = BACK_SCALE if behind else 1.0
        width, height = (CIRCLE_SIZE, CIRCLE_SIZE) if circle else PIECE_SIZE
        pieces.append(
            Piece(
                shape="Ellipse" if circle else "Rectangle",
                width=width * scale,
                height=height * scale,
                color=settings.colors[int(rng.integers(len(settings.colors)))],
                behind=behind,
                x=x,
                y=y,
                rotation=rotation,
                scale_y=scale_y,
                opacity=opacity,
            )
        )
    return pieces
