import tomllib
from dataclasses import dataclass
from pathlib import Path

BONE_PROPERTIES = ("y", "rotation")


@dataclass
class Canvas:
    pad_x: float
    pad_top: float
    pad_bottom: float
    background: str


@dataclass
class MeshSettings:
    base_step: int
    fine_step: int
    fine_regions: list


@dataclass
class ExpressionOffset:
    center: tuple
    offset: tuple
    radius: float


@dataclass
class Mood:
    name: str
    duration: int
    expression: list
    bone_offsets: dict


@dataclass
class StateMachineSettings:
    property: str
    default: str
    transition_ms: int


@dataclass
class Character:
    name: str
    directory: Path
    image: Path
    canvas: Canvas
    mesh: MeshSettings
    rig: dict
    moods: list
    state_machine: StateMachineSettings


def point(value):
    return (float(value[0]), float(value[1]))


def parse_rig(raw):
    rig = {}
    for key, value in raw.items():
        if isinstance(value, list) and value and isinstance(value[0], list):
            rig[key] = [point(p) for p in value]
        elif isinstance(value, list):
            rig[key] = point(value)
        else:
            rig[key] = float(value)
    return rig


def parse_mood(raw, landmarks):
    expression = []
    for entry in raw.get("expression", []):
        if entry["at"] not in landmarks:
            raise ValueError(f"mood {raw['name']}: unknown landmark {entry['at']!r}")
        expression.append(ExpressionOffset(landmarks[entry["at"]], point(entry["offset"]), float(entry["radius"])))
    bone_offsets = {}
    for track, keys in raw.get("bones", {}).items():
        bone, prop = track.split(".")
        if prop not in BONE_PROPERTIES:
            raise ValueError(f"mood {raw['name']}: {track} must key one of {BONE_PROPERTIES}")
        bone_offsets[(bone, prop)] = [(int(frame), float(value)) for frame, value in keys]
    return Mood(raw["name"], int(raw["duration"]), expression, bone_offsets)


def load_character(directory):
    directory = Path(directory)
    raw = tomllib.loads((directory / "character.toml").read_text())
    landmarks = {name: point(value) for name, value in raw.get("landmarks", {}).items()}
    moods = [parse_mood(m, landmarks) for m in raw["moods"]]
    machine = StateMachineSettings(**raw["state_machine"])
    if machine.default not in {m.name for m in moods}:
        raise ValueError(f"state_machine.default {machine.default!r} names no mood")
    return Character(
        name=raw["name"],
        directory=directory,
        image=directory / raw["image"],
        canvas=Canvas(**raw["canvas"]),
        mesh=MeshSettings(**raw["mesh"]),
        rig=parse_rig(raw["rig"]),
        moods=moods,
        state_machine=machine,
    )
