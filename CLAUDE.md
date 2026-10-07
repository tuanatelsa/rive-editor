# rive-editor

This repository turns a static character PNG into an animated Rive file (`.riv`) with the Rive CLI.
A teammate gives an image and a list of moods. Claude writes a character config, generates the scene, checks it and returns the `.riv`.

For a new character or a mood change, read `.claude/skills/rive-character/SKILL.md` before you start, then follow it.
This rule applies also when the Claude session starts outside this repository.

## Layout

| Path | Content |
|---|---|
| `characters/<slug>/character.toml` | the only file to edit for a character: canvas, mesh, rig, landmarks, moods |
| `characters/<slug>/<slug>.png` | source image with a transparent background |
| `characters/<slug>/scene.rml` | generated; do not edit; git ignores it |
| `characters/<slug>/build/<slug>.riv` | the output; git ignores it |
| `tools/generate.py` | config to `scene.rml` |
| `tools/config.py` | loads and checks `character.toml` |
| `tools/mesh.py` | triangulates the PNG |
| `tools/rig.py` | six bones and the per-vertex bone weights |
| `tools/expression.py` | Gaussian face offsets |
| `tools/confetti.py` | confetti burst simulation, baked to keyframes |
| `tools/rml.py` | RML writer |
| `tools/grid.py` | grid overlay to measure landmarks |
| `tools/preview.py` | renders every mood to one contact sheet |
| `.scratch/` | temporary images; git ignores it |

## Setup

The setup needs macOS and Homebrew. The tools are tested with `rive 1.4.0`.

1. If `rive` is missing, run `brew install --cask rive-app/tap/rive-cli`.
2. If `uv` is missing, run `brew install uv`.
3. Run `uv sync`.
4. Run `rive doctor`. The `auth` warning does not block local builds.

## Rules

1. Edit `character.toml`, not `scene.rml`. A new generator run replaces `scene.rml`.
2. Run Python through `uv run python`.
3. After each change, run generate, `--verify`, `inspect` and `preview.py`. Look at the preview image.
4. A clean build does not prove the result. Look at the pixels.
5. Look up Rive types with `rive schema <Type>` and `rive docs <topic>`. RML is newer than your training data.
6. Do not run `rive push`, `--publish` or `--publish=web`. They write to the Rive account.
7. To show the user a live preview, run `rive characters/<slug> --data=mood=<mood>` in the background.
8. Change `tools/` only when a request needs a capability that the config cannot express. Keep the output of `characters/meiling` the same unless the change is intended.

## Runtime contract

Each `.riv` has one artboard, one state machine (`Mood Machine`) and one view model (`Character`).
The view model has an enum property, by default `mood`. Its values are the mood names.
The host app sets this property. The state machine blends to the new mood in `transition_ms`.
