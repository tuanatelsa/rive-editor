import argparse

from PIL import Image, ImageDraw

BACKDROP = (40, 160, 40, 255)
LINE = (255, 255, 0, 160)
LABEL = (255, 0, 0, 255)


def parse_box(text, image):
    if text is None:
        return (0, 0, image.width, image.height)
    x0, y0, x1, y1 = (int(v) for v in text.split(","))
    return (x0, y0, x1, y1)


def render(image_path, box, step, scale, out_path):
    source = Image.open(image_path).convert("RGBA")
    x0, y0, x1, y1 = box
    crop = source.crop(box)
    size = (round(crop.width * scale), round(crop.height * scale))
    canvas = Image.new("RGBA", size, BACKDROP)
    canvas.alpha_composite(crop.resize(size, Image.LANCZOS))
    draw = ImageDraw.Draw(canvas)
    for x in range(x0 - x0 % step + step, x1, step):
        px = (x - x0) * scale
        draw.line([(px, 0), (px, size[1])], fill=LINE)
        draw.text((px + 2, 2), str(x), fill=LABEL)
    for y in range(y0 - y0 % step + step, y1, step):
        py = (y - y0) * scale
        draw.line([(0, py), (size[0], py)], fill=LINE)
        draw.text((2, py + 2), str(y), fill=LABEL)
    canvas.save(out_path)


def main():
    parser = argparse.ArgumentParser(description="Overlay a labelled pixel grid on an image to read landmark coordinates.")
    parser.add_argument("image")
    parser.add_argument("--out", required=True)
    parser.add_argument("--crop", help="x0,y0,x1,y1 in source pixels")
    parser.add_argument("--step", type=int, default=50)
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()
    image = Image.open(args.image)
    render(args.image, parse_box(args.crop, image), args.step, args.scale, args.out)


if __name__ == "__main__":
    main()
