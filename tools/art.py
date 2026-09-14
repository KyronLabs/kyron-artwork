#!/usr/bin/env python3
"""The artwork catalogue: draw it, check it, look at it.

    python3 tools/art.py draw            # rewrite Kyron's own pieces
    python3 tools/art.py check           # everything CI checks
    python3 tools/art.py sheet -o x.png  # a contact sheet to look at

Kyron's own artwork is *drawn by this file* rather than committed as opaque
pixels somebody has to take on trust. A pull request that changes the crown
shows a diff you can read, and anybody can rebuild every piece and compare.

Artwork from other people arrives as PNGs, which is the normal case and is
what `check` is for. `draw` only ever rewrites the pieces this file defines.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue.json"
ART = ROOT / "art"

SIZE = 512
SUPERSAMPLE = 4

#: Where the catalogue is published. Every url in it must start with this.
BASE = "https://kyronlabs.github.io/kyron-artwork/"

#: Licences a piece may carry.
#:
#: CC0 only, for now, and deliberately. Artwork here exists so that somebody
#: can publish a lens with it, and a lens is then copied, remixed and served
#: from a CDN by people who will never read this file. A licence with an
#: attribution requirement makes every one of those an obligation nobody is
#: tracking. If Kyron decides to accept CC-BY, the decision is a line here and
#: a column in the catalogue -- but it should be a decision, not a default.
LICENCES = {"CC0-1.0"}

ID = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
TAG = re.compile(r"^[a-z][a-z0-9-]{1,20}$")


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def canvas():
    """A transparent square, oversized so the edges come out smooth."""
    side = SIZE * SUPERSAMPLE
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def finish(image):
    return image.resize((SIZE, SIZE), Image.LANCZOS)


def star_points(cx, cy, outer, inner, points=5, turn=-math.pi / 2):
    out = []
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        a = turn + math.pi * i / points
        out.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return out


def draw_star():
    image, pen = canvas()
    s = SUPERSAMPLE
    pen.polygon(star_points(256 * s, 262 * s, 224 * s, 92 * s),
                fill=(255, 201, 71, 255), outline=(240, 150, 20, 255),
                width=10 * s)
    return finish(image)


def draw_heart():
    image, pen = canvas()
    s = SUPERSAMPLE
    # Two lobes and a point, which is all a heart is.
    pen.ellipse([70 * s, 90 * s, 266 * s, 286 * s], fill=(255, 92, 122, 255))
    pen.ellipse([246 * s, 90 * s, 442 * s, 286 * s], fill=(255, 92, 122, 255))
    pen.polygon([(80 * s, 222 * s), (432 * s, 222 * s), (256 * s, 452 * s)],
                fill=(255, 92, 122, 255))
    return finish(image)


def draw_halo():
    image, pen = canvas()
    s = SUPERSAMPLE
    # Flattened, because a halo is a circle seen from below.
    pen.ellipse([48 * s, 186 * s, 464 * s, 326 * s], fill=None,
                outline=(255, 224, 130, 255), width=34 * s)
    return finish(image)


def draw_sparkle():
    image, pen = canvas()
    s = SUPERSAMPLE
    pen.polygon(star_points(256 * s, 256 * s, 236 * s, 44 * s, points=4),
                fill=(255, 255, 255, 255))
    pen.polygon(star_points(256 * s, 256 * s, 140 * s, 26 * s, points=4,
                            turn=-math.pi / 4),
                fill=(186, 226, 255, 255))
    return finish(image)


def draw_crown():
    image, pen = canvas()
    s = SUPERSAMPLE
    pen.polygon(
        [(58 * s, 372 * s), (58 * s, 158 * s), (158 * s, 252 * s),
         (256 * s, 128 * s), (354 * s, 252 * s), (454 * s, 158 * s),
         (454 * s, 372 * s)],
        fill=(255, 201, 71, 255), outline=(214, 142, 20, 255), width=10 * s)
    for x in (158, 256, 354):
        pen.ellipse([(x - 20) * s, 300 * s, (x + 20) * s, 340 * s],
                    fill=(214, 142, 20, 255))
    return finish(image)


def draw_bolt():
    image, pen = canvas()
    s = SUPERSAMPLE
    pen.polygon(
        [(300 * s, 40 * s), (140 * s, 288 * s), (238 * s, 288 * s),
         (196 * s, 472 * s), (378 * s, 210 * s), (272 * s, 210 * s)],
        fill=(255, 214, 66, 255), outline=(232, 160, 16, 255), width=8 * s)
    return finish(image)


def draw_cloud():
    image, pen = canvas()
    s = SUPERSAMPLE
    white = (245, 249, 255, 255)
    for box in ([96, 210, 256, 356], [176, 156, 356, 340],
                [292, 214, 424, 350]):
        pen.ellipse([v * s for v in box], fill=white)
    pen.rounded_rectangle([104 * s, 274 * s, 416 * s, 352 * s],
                          radius=40 * s, fill=white)
    return finish(image)


def draw_leaf():
    """Kyron's own motif: two circular arcs meeting at a point at each end.

    Built as the overlap of two equal circles, which is what that shape is.
    Drawing it as two pie slices -- the first attempt -- gives two clipped
    quarter-discs that do not meet at a point, and reads as a broken circle
    rather than as a leaf.
    """
    side = SIZE * SUPERSAMPLE
    y, x = numpy.mgrid[0:side, 0:side]

    # Centres on the top-left/bottom-right diagonal, so the leaf lies along
    # the other one. The radius sets how fat it is: at half the distance
    # between the centres the two circles touch and there is no leaf at all.
    radius = 0.62 * side
    centres = ((0.18 * side, 0.18 * side), (0.82 * side, 0.82 * side))
    inside = numpy.ones((side, side), dtype=bool)
    for cx, cy in centres:
        inside &= (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2

    blade = numpy.zeros((side, side, 4), dtype=numpy.uint8)
    blade[inside] = (23, 209, 176, 255)

    # A darker half along one side of the midrib, so the leaf reads as a
    # surface rather than as a flat token.
    shaded = inside & ((x - y) > 0)
    blade[shaded] = (20, 178, 150, 255)

    image = Image.fromarray(blade, "RGBA")
    pen = ImageDraw.Draw(image)

    # The midrib, from tip to tip, which are on the other diagonal.
    half = math.sqrt(radius ** 2 - (0.64 * side * math.sqrt(2) / 2) ** 2)
    step = half / math.sqrt(2)
    middle = 0.5 * side
    pen.line([(middle + step, middle - step), (middle - step, middle + step)],
             fill=(9, 122, 102, 235), width=10 * SUPERSAMPLE)
    return finish(image)


def draw_bubble():
    image, pen = canvas()
    s = SUPERSAMPLE
    pen.rounded_rectangle([48 * s, 78 * s, 464 * s, 340 * s], radius=64 * s,
                          fill=(255, 255, 255, 255))
    pen.polygon([(150 * s, 320 * s), (250 * s, 320 * s), (146 * s, 452 * s)],
                fill=(255, 255, 255, 255))
    return finish(image)


def draw_flower():
    image, pen = canvas()
    s = SUPERSAMPLE
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        cx = 256 * s + math.cos(a) * 118 * s
        cy = 256 * s + math.sin(a) * 118 * s
        pen.ellipse([cx - 104 * s, cy - 104 * s, cx + 104 * s, cy + 104 * s],
                    fill=(255, 158, 196, 255))
    pen.ellipse([190 * s, 190 * s, 322 * s, 322 * s], fill=(255, 214, 92, 255))
    return finish(image)


#: Kyron's own pieces: what to call them, what they are for, and how to draw
#: them. `draw` writes every one; `check` reads the catalogue, not this.
PIECES = [
    ("star", "Star", ["shape", "sparkle", "celebration"], draw_star),
    ("heart", "Heart", ["shape", "love", "reaction"], draw_heart),
    ("halo", "Halo", ["shape", "angel", "head"], draw_halo),
    ("sparkle", "Sparkle", ["shape", "sparkle", "shine"], draw_sparkle),
    ("crown", "Crown", ["shape", "head", "celebration"], draw_crown),
    ("bolt", "Lightning bolt", ["shape", "energy"], draw_bolt),
    ("cloud", "Cloud", ["shape", "weather", "sky"], draw_cloud),
    ("leaf", "Leaf", ["shape", "nature", "kyron"], draw_leaf),
    ("bubble", "Speech bubble", ["shape", "talk"], draw_bubble),
    ("flower", "Flower", ["shape", "nature"], draw_flower),
]


def command_draw(_args):
    ART.mkdir(exist_ok=True)
    entries = []
    for piece_id, name, tags, drawer in PIECES:
        image = drawer()
        path = ART / f"{piece_id}.png"
        image.save(path)
        entries.append({
            "id": piece_id,
            "name": name,
            "url": f"{BASE}art/{piece_id}.png",
            "tags": tags,
            "author": "Kyron",
            "licence": "CC0-1.0",
            "width": image.width,
            "height": image.height,
        })
        print(f"{path.relative_to(ROOT)}  {image.width}x{image.height}")

    # Anything somebody else contributed is kept; only Kyron's own pieces are
    # rewritten from this file.
    mine = {entry["id"] for entry in entries}
    existing = read_catalogue().get("artwork", []) if CATALOGUE.exists() else []
    theirs = [entry for entry in existing if entry.get("id") not in mine]

    CATALOGUE.write_text(json.dumps(
        {"schema": 1, "artwork": entries + theirs}, indent=2) + "\n")
    print(f"\n{len(entries)} drawn, {len(theirs)} left alone, "
          f"written to {CATALOGUE.name}")
    return 0


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def read_catalogue():
    return json.loads(CATALOGUE.read_text())


def command_check(_args):
    wrong = []

    def bad(why):
        wrong.append(why)

    if not CATALOGUE.exists():
        print(f"{CATALOGUE.name} is missing")
        return 1

    try:
        catalogue = read_catalogue()
    except json.JSONDecodeError as error:
        print(f"{CATALOGUE.name} is not valid JSON: {error}")
        return 1

    if catalogue.get("schema") != 1:
        bad(f"schema is {catalogue.get('schema')!r}, which this tool cannot read")

    artwork = catalogue.get("artwork")
    if not isinstance(artwork, list) or not artwork:
        print("the catalogue has no artwork in it")
        return 1

    seen = set()
    named = set()
    for at, entry in enumerate(artwork):
        where = f"artwork[{at}]"
        if not isinstance(entry, dict):
            bad(f"{where}: not an object")
            continue

        piece = entry.get("id")
        where = f"{piece or where}"
        if not isinstance(piece, str) or not ID.match(piece):
            bad(f"{where}: id must be lowercase letters, digits and -")
            continue
        if piece in seen:
            bad(f"{where}: two pieces share this id")
        seen.add(piece)

        if not entry.get("name"):
            bad(f"{where}: no name")
        if not entry.get("author"):
            bad(f"{where}: no author")

        licence = entry.get("licence")
        if licence not in LICENCES:
            bad(f"{where}: licence {licence!r} is not one of "
                f"{', '.join(sorted(LICENCES))}")

        tags = entry.get("tags")
        if not isinstance(tags, list) or not tags:
            bad(f"{where}: no tags, so nobody will find it")
        else:
            for tag in tags:
                if not isinstance(tag, str) or not TAG.match(tag):
                    bad(f"{where}: tag {tag!r} must be one lowercase word")

        url = entry.get("url")
        want = f"{BASE}art/{piece}.png"
        if url != want:
            bad(f"{where}: url is {url!r}; it has to be {want}")

        path = ART / f"{piece}.png"
        named.add(path.name)
        if not path.exists():
            bad(f"{where}: {path.relative_to(ROOT)} is not here")
            continue

        try:
            with Image.open(path) as image:
                image.load()
                fault = fault_in(image, entry, where)
        except Exception as error:  # noqa: BLE001 - the reason is the message
            bad(f"{where}: {path.name} is not a PNG this tool can read: {error}")
            continue
        if fault:
            bad(fault)

    # Artwork nobody can find is artwork that is not in the catalogue.
    for path in sorted(ART.glob("*.png")):
        if path.name not in named:
            bad(f"art/{path.name} is not in the catalogue, so nothing can "
                f"reach it")

    for why in wrong:
        print(why)
    print(f"\n{len(artwork)} pieces, {len(wrong)} problems")
    return 1 if wrong else 0


def fault_in(image, entry, where):
    """What is wrong with one piece, or None."""
    if image.format != "PNG":
        return f"{where}: {image.format} rather than PNG"
    if image.mode != "RGBA":
        return (f"{where}: mode {image.mode}. Artwork goes on a face, so it "
                f"has to carry an alpha channel")

    if not (256 <= image.width <= 2048 and 256 <= image.height <= 2048):
        return (f"{where}: {image.width}x{image.height}. Under 256 it is soft "
                f"on a big screen and over 2048 it is a download nobody needs")

    for axis in ("width", "height"):
        said = entry.get(axis)
        real = getattr(image, axis)
        if said != real:
            return f"{where}: says {axis} {said}, the file is {real}"

    alpha = numpy.asarray(image.getchannel("A"))
    if not (alpha < 8).any():
        return (f"{where}: every pixel is opaque. A rectangle with no "
                f"transparency covers the face it is placed on")

    edge = max(alpha[0].max(), alpha[-1].max(),
               alpha[:, 0].max(), alpha[:, -1].max())
    if edge > 24:
        return (f"{where}: the drawing touches the edge of its box. It will "
                f"be cut off rather than sit on the face")

    return None


# ---------------------------------------------------------------------------
# Looking at it
# ---------------------------------------------------------------------------

def command_sheet(args):
    catalogue = read_catalogue()
    artwork = catalogue["artwork"]
    columns = args.columns
    rows = math.ceil(len(artwork) / columns)
    cell = args.size

    # Mid grey: artwork is mostly light or mostly dark, and either disappears
    # against its own end of the range.
    sheet = Image.new("RGB", (columns * cell, rows * cell), (108, 112, 120))
    for at, entry in enumerate(artwork):
        path = ART / f"{entry['id']}.png"
        if not path.exists():
            continue
        with Image.open(path) as piece:
            piece = piece.convert("RGBA")
            piece.thumbnail((cell - 24, cell - 24), Image.LANCZOS)
            x = (at % columns) * cell + (cell - piece.width) // 2
            y = (at // columns) * cell + (cell - piece.height) // 2
            sheet.paste(piece, (x, y), piece)

    sheet.save(args.out)
    print(f"{len(artwork)} pieces -> {args.out}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("draw", help="rewrite Kyron's own pieces")
    commands.add_parser("check", help="everything CI checks")

    sheet = commands.add_parser("sheet", help="a contact sheet to look at")
    sheet.add_argument("-o", "--out", default="contact-sheet.png")
    sheet.add_argument("--columns", type=int, default=5)
    sheet.add_argument("--size", type=int, default=240)

    args = parser.parse_args()
    return {
        "draw": command_draw,
        "check": command_check,
        "sheet": command_sheet,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
