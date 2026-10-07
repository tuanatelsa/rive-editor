---
name: rive-character
description: Make an animated Rive (.riv) file from a static character PNG and a list of moods or poses, or change the moods of an existing character. Use when the user gives an image and asks for a Rive animation, new states, new expressions, or tuning of an existing character in characters/.
---

# Make a Rive character from a PNG

The tool deforms one PNG with a triangle mesh, six bones and Gaussian face offsets.
Each mood is one looping timeline. A state machine switches moods through a view model enum.
You write only `characters/<slug>/character.toml`. `tools/generate.py` writes `scene.rml`.

## Inputs

1. Get the image path and the requested moods from the user.
2. If the user gives no moods, use `smiling`, `sad` and `cheer`.
3. Use a lowercase slug for the character name, for example `meiling`.

## Step 1: Check the image

1. Run `uv run python -c "from PIL import Image; im = Image.open('<path>'); print(im.size, im.mode)"`.
2. If the mode is not `RGBA`, stop. Tell the user that the tool needs a transparent background.
3. Look at the image with the Read tool.
4. Confirm that the character faces the camera, with the head at the top and both arms visible.
5. If the pose is very different (side view, arms crossed, no arms), tell the user which bones cannot work.

## Step 2: Create the character directory

1. Run `mkdir -p characters/<slug>`.
2. Copy the image to `characters/<slug>/<slug>.png`.
3. Copy `characters/meiling/character.toml` to `characters/<slug>/character.toml`.
4. Set `name` and `image` in the new file.

## Step 3: Measure the landmarks

Do not guess coordinates. Read them from grid overlays.

1. Render the full body:
   `uv run python tools/grid.py characters/<slug>/<slug>.png --step 50 --scale 0.75 --out .scratch/full.png`
2. Render the face at high zoom:
   `uv run python tools/grid.py characters/<slug>/<slug>.png --crop <x0,y0,x1,y1> --step 10 --scale 4 --out .scratch/face.png`
3. Render the mouth at very high zoom. The mouth corners are the most important landmarks.
4. Look at each overlay with the Read tool. Labels show source pixel coordinates.
5. Write the coordinates into `character.toml`.

Find these points:

| Key | Point |
|---|---|
| `rig.hip` | body centre, low on the torso; the root bone starts here |
| `rig.neck` | centre of the neck, below the chin; the head pivots here |
| `rig.crown` | centre of the head, above the eyes |
| `rig.shoulder_left` | top of the left sleeve (viewer's left) |
| `rig.elbow_left` | elbow of the left arm |
| `rig.wrist_left` | wrist of the left arm |
| `rig.mirror_x` | twice the body centre x; mirrors the left side to the right side |
| `rig.side_boundary_left` | polyline from shoulder to image bottom; it separates the left arm from the torso |
| `mesh.fine_regions` | box around brows, eyes and mouth; it gets a dense mesh |
| `landmarks.*` | mouth corners, mouth centre, lower lip, cheeks, eyelids, brows |

Rules for `side_boundary_left`:

1. Find the transparent gap between the arm and the torso in each row. Run a script on the alpha channel for this.
2. Put the boundary in the middle of that gap.
3. Where the arm touches the torso, put the boundary on the sleeve seam.
4. Keep the boundary away from the pants and the hands. Else the cheer pose pulls spikes out of the pants.

If the character is not symmetric, set `shoulder_right`, `elbow_right`, `wrist_right` and `side_boundary_right`. These replace the mirror.

## Step 4: Write the moods

Each `[[moods]]` entry has a `name`, a `duration` in frames (60 fps), an `expression` list and a `[moods.bones]` table.

Expression entry: `{ at = "<landmark>", offset = [dx, dy], radius = <px> }`.
The offset moves the pixels near the landmark. The weight falls off as a Gaussian with that radius.

Bone track: `"<Bone>.<property>" = [[frame, offset], ...]`.

1. Bones: `Root`, `Head`, `UpperArmL`, `ForearmL`, `UpperArmR`, `ForearmR`.
2. Properties: `rotation` on all bones, in radians. Positive turns clockwise on screen. `y` on `Root` only, in pixels. Negative moves up.
3. Offsets add to the rest pose. `0` is the pose in the PNG.
4. Key every bone track in every mood. Else a mood keeps the bone value of the previous mood.
5. Make the first and the last keyframe equal, so the loop has no jump.

Start values that work:

| Effect | Values |
|---|---|
| Smile | mouth corners `[∓3, -7]` r10, mouth centre `[0, 2]` r12, cheeks `[0, -4]` r22 |
| Frown | mouth corners `[±3, 15]` r13, mouth centre `[0, -5]` r16 |
| Sad brows | inner brow ends `[±2, -10]` r16, outer brow ends `[0, 4]` r18 |
| Raised brows | brow centres `[0, -8]` r30 |
| Head tilt | `Head.rotation` ±0.05 to ±0.13 |
| Jump | `Root.y` `[[0, 0], [20, -45], [40, 0]]` |
| Arms up | `UpperArmL.rotation` 0.55, `ForearmL.rotation` 1.55, negative values on the right side |
| Arms closer to the body | `UpperArmL.rotation` -0.06, positive value on the right side |

Set `state_machine.default` to the mood that plays first.

### Confetti

To add a confetti burst to one or more moods, add a `[confetti]` table. Copy it from `characters/meiling/character.toml`.

| Key | Meaning |
|---|---|
| `moods` | moods that show the confetti |
| `seed` | random seed; the same seed gives the same burst |
| `pieces` | number of pieces |
| `duration` | frames of one burst loop, separate from the mood duration |
| `life` | minimum and maximum frames that one piece lives; the maximum must not exceed `duration` |
| `speed` | launch speed in pixels per frame; each piece gets 50% to 100% of it |
| `spread` | launch cone in degrees |
| `cannons` | launch points in image coordinates and the angle in degrees; 90 points up |
| `colors` | `AARRGGBB` colours |

The confetti plays on its own state machine layer, `Confetti`. It restarts each time a listed mood starts. It fades out in `transition_ms` when the mood changes.

## Step 5: Build and check

Do all of these steps after every change:

1. `uv run python tools/generate.py characters/<slug>`
2. `rive characters/<slug> --verify`. It must report 0 errors.
3. `rive inspect characters/<slug> --summary | jq .problems`. It must print `[]`.
4. `uv run python tools/preview.py characters/<slug> --out .scratch/<slug>.png`
5. Look at the contact sheet with the Read tool. Check each mood against the request.
6. For a moving mood, render more frames: `--advance 10`, `--advance 20`, `--advance 30`.

Fix what you see:

| Problem | Fix |
|---|---|
| Mouth makes a wave, not a frown | Move `mouth_left` and `mouth_right` to the real ends of the lip line. Increase the radius. |
| Spikes near the pants or the hands | Move `side_boundary_left` into the transparent gap. |
| Hands or head cut off at the edge | Increase `canvas.pad_x` or `canvas.pad_top`. |
| Image bottom edge shows in a jump | Make `canvas.pad_bottom` more negative than the jump height. |
| Head neck seam tears | Move `head_ramp_center` lower, or make the ramp longer. |
| Sleeve stretches like a wing | Decrease `UpperArm*.rotation`. Bend the forearm more. |

## Step 6: Report

1. Give the user the path `characters/<slug>/build/<slug>.riv`. Run `rive characters/<slug> --once` to write it.
2. Show the contact sheet.
3. List the moods and the view model property name, for example `mood = sad`.
4. State the visible defects that remain.
5. Do not run `rive push` or `--publish`. Do not commit or push unless the user asks.
