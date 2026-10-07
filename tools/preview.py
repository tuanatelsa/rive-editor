import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from config import load_character

LABEL = (255, 255, 0)
FACE_HEIGHT = 300


def capture(character, mood, advance, out_path):
    subprocess.run(
        [
            "rive",
            str(character.directory),
            f"--screenshot={out_path}",
            f"--data={character.state_machine.property}={mood}",
            f"--advance={advance}",
            "--quiet",
        ],
        check=True,
    )
    return Image.open(out_path).convert("RGB")


def face_box(character):
    x0, y0, x1, y1 = character.mesh.fine_regions[0]
    dx, dy = character.canvas.pad_x, character.canvas.pad_top
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)


def compose(character, frames, scale):
    width, height = frames[0][1].size
    cell_w, cell_h = round(width * scale), round(height * scale)
    box = face_box(character)
    face_w = round((box[2] - box[0]) * FACE_HEIGHT / (box[3] - box[1]))
    sheet = Image.new("RGB", (max(cell_w, face_w) * len(frames), cell_h + FACE_HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    column = max(cell_w, face_w)
    for i, (mood, frame) in enumerate(frames):
        sheet.paste(frame.resize((cell_w, cell_h)), (i * column, 0))
        sheet.paste(frame.crop(box).resize((face_w, FACE_HEIGHT)), (i * column, cell_h))
        draw.text((i * column + 8, 8), mood, fill=LABEL)
    return sheet


def main():
    parser = argparse.ArgumentParser(description="Render every mood headlessly and write one contact sheet.")
    parser.add_argument("character_dir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--advance", type=int, default=30)
    parser.add_argument("--scale", type=float, default=0.4)
    args = parser.parse_args()
    character = load_character(args.character_dir)
    with tempfile.TemporaryDirectory() as tmp:
        frames = [
            (mood.name, capture(character, mood.name, args.advance, Path(tmp) / f"{mood.name}.png"))
            for mood in character.moods
        ]
        compose(character, frames, args.scale).save(args.out)


if __name__ == "__main__":
    main()
