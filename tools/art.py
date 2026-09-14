#!/usr/bin/env python3
"""The artwork catalogue: cut it out, check it, look at it.

    python3 tools/art.py cut             # re-cut Kyron's own pieces
    python3 tools/art.py check           # everything CI checks
    python3 tools/art.py sheet -o x.png  # a contact sheet to look at

Kyron's own artwork arrives as pictures on a flat background -- black, white,
a blue plate -- and a lens needs the picture with the plate gone. `cut` is
that step, and it is in the repository rather than in somebody's image editor
so that the result is reproducible: the source is committed beside the cut
PNG, anybody can re-cut and compare, and CI fails if a committed piece and the
source it claims to come from have come apart.

Artwork from other people arrives already cut, as PNGs, which is the normal
case and is what `check` is for. `cut` only ever rewrites the pieces listed in
PIECES below.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue.json"
ART = ROOT / "art"
SOURCES = ROOT / "sources"

#: Every piece is this square, with the drawing centred inside it.
SIZE = 512

#: Transparent border, as a fraction of the box. A piece that reaches the edge
#: of its own file gets cut off when the app scales it onto a face.
MARGIN = 0.035

#: Where the colour distance from the plate ramps alpha 0 -> 1. Below the
#: first number is plate, above the second is subject, and between them is the
#: anti-aliased rim -- which has to be soft, or the cut-out comes out with
#: stair-stepped edges.
SOFT_LO, SOFT_HI = 0.04, 0.16

#: How far past the flood-filled plate the soft rim is allowed to reach.
BAND = 4

#: A plate this saturated is a colour somebody *chose* to shoot against, and
#: then a pixel of that colour is plate however bright it is. Below it the
#: plate is black, white or near it, where brightness is the only signal there
#: is and that test would cut the subject instead.
PLATE_SATURATION = 0.15

#: How parallel to the plate's own colour a pixel has to be to count as plate
#: rather than subject. Measured on the crown: its blue plate, lit by the
#: sparkle over one ball, runs 0.92 to 1.00; the gold runs 0.42 to 0.54.
HUE_PLATE, HUE_SUBJECT = 0.92, 0.82

#: Pixels taken off the whole outline after the cut. Measured on the crown,
#: whose plate is a deep blue: its violet outline is gone at 4 and still
#: visible at 2. Four pixels off a 736-pixel source is not something a person
#: can see; the outline is.
TRIM = 4

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
# Cutting a picture off its plate
# ---------------------------------------------------------------------------

def mask_image(mask):
    """A boolean or 0..1 array as an image Pillow will filter and flood-fill.

    `.copy()` is not decoration. `Image.fromarray` shares the numpy buffer,
    and `ImageDraw.floodfill` then writes somewhere `numpy.asarray` does not
    read back -- the fill silently does nothing and every cut comes out empty.
    """
    return Image.fromarray((mask * 255).astype(numpy.uint8), "L").copy()


def grow(mask, by):
    """Every pixel within `by` of a true one. A max filter is a dilation."""
    if by <= 0:
        return mask
    grown = mask_image(mask).filter(ImageFilter.MaxFilter(2 * by + 1))
    return numpy.array(grown) > 127


def shrink(mask, by):
    """Every pixel at least `by` inside a true one. A min filter is an erosion."""
    if by <= 0:
        return mask
    worn = mask_image(mask).filter(ImageFilter.MinFilter(2 * by + 1))
    return numpy.array(worn) > 127


def reaches_border(mask):
    """The part of `mask` a flood fill from outside the picture can reach."""
    tall, wide = mask.shape
    # One ring of true pixels around the outside, so a single fill from a
    # corner walks the whole border and then inwards.
    padded = numpy.ones((tall + 2, wide + 2), dtype=bool)
    padded[1:-1, 1:-1] = mask
    image = mask_image(padded)
    ImageDraw.floodfill(image, (0, 0), 128, thresh=0)
    return numpy.array(image)[1:-1, 1:-1] == 128


def blobs(mask):
    """Every connected run of true pixels, largest first."""
    pixels = numpy.array(mask_image(mask))
    found = []
    for mark in range(1, 250):
        where = numpy.argwhere(pixels == 255)
        if not len(where):
            break
        y, x = where[0]
        image = Image.fromarray(pixels, "L").copy()
        ImageDraw.floodfill(image, (int(x), int(y)), mark, thresh=0)
        pixels = numpy.array(image)
        found.append((int((pixels == mark).sum()), pixels == mark))
    found.sort(key=lambda it: -it[0])
    return found


def cut_out(path):
    """One source picture, with its background gone. Returns the image and
    how many separate things were dropped as not being the subject."""
    rgb = numpy.asarray(Image.open(path).convert("RGB"), dtype=numpy.float64) / 255

    # The background, from the border ring rather than one corner: a single
    # pixel of JPEG noise should not decide what gets cut away.
    ring = numpy.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    back = numpy.median(ring, axis=0)

    distance = numpy.sqrt(((rgb - back) ** 2).sum(axis=2) / 3)
    alpha = numpy.clip((distance - SOFT_LO) / (SOFT_HI - SOFT_LO), 0, 1)

    # A lit plate is still plate.
    #
    # The crown is shot on a deep blue with a sparkle over one ball, and the
    # sparkle's glow lifts the blue around it far enough from the plate colour
    # that a distance test calls it subject -- so the crown came out wearing a
    # lump of blue. Brightness cannot tell them apart; hue can. This asks how
    # parallel a pixel is to the plate's own colour, which the glow is and the
    # gold is not.
    #
    # Only for a saturated plate, and the limitation is the obvious one: a
    # subject that is genuinely the plate's colour would be cut away with it.
    # That is the same thing shooting against a colour already assumes.
    if back.max() - back.min() > PLATE_SATURATION:
        lit = numpy.linalg.norm(rgb, axis=2)
        parallel = ((rgb / numpy.maximum(lit, 1e-6)[..., None]) *
                    (back / numpy.linalg.norm(back))).sum(axis=2)
        plateness = numpy.clip(
            (parallel - HUE_SUBJECT) / (HUE_PLATE - HUE_SUBJECT), 0, 1)
        alpha = alpha * (1 - numpy.where(lit > SOFT_LO, plateness, 1.0))

    # Background is what the *border* can reach. A colour key on its own would
    # punch the ghost's eyes out -- they are the same black as behind it.
    plate = reaches_border(alpha < 0.5)
    alpha = numpy.where(grow(plate, BAND), alpha, 1.0)

    # Then take one pixel off the whole outline.
    #
    # The outermost pixel of any cut-out is the one most made of plate, and
    # the ramp above cannot always tell: on the crown's deep blue, gold that
    # is half blue is still far from blue in plain colour distance, so the
    # ramp calls it solid and the crown ships with a violet line around it.
    # Normalising the ramp against the neighbouring subject instead was tried
    # and is worse -- it cuts the diamond's near-white lower facets off the
    # white plate, because there the subject and the plate really are the same
    # colour. Losing a pixel off a 512-pixel sticker is not visible; a violet
    # outline is.
    alpha = numpy.minimum(alpha, shrink(alpha > 0.02, TRIM))

    # The rim that is left is still the subject blended with the plate: dark
    # edges on a black plate, pale ones on white. Undo the blend rather than
    # ship the halo -- C = aF + (1-a)B, so F = (C - (1-a)B) / a.
    fore = numpy.clip(
        (rgb - (1 - alpha)[..., None] * back) / numpy.maximum(alpha, 1e-3)[..., None],
        0, 1)

    # One subject, not a subject and a stock watermark in the corner.
    parts = blobs(alpha > 0.5)
    dropped = len(parts) - 1
    if dropped > 0:
        alpha = numpy.where(grow(parts[0][1], BAND), alpha, 0.0)

    rows = numpy.where(alpha.max(axis=1) > 0.02)[0]
    cols = numpy.where(alpha.max(axis=0) > 0.02)[0]
    if not len(rows) or not len(cols):
        raise SystemExit(f"{path.name}: nothing survived the cut")
    cropped = numpy.dstack([fore, alpha[..., None]])[
        rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    piece = Image.fromarray((cropped * 255).round().astype(numpy.uint8), "RGBA")

    # Every piece fills its box the same way, up or down. Without the "up" a
    # subject that sat small in its source stays small, and then a star and a
    # crown at the same width on a face are different sizes.
    inner = round(SIZE * (1 - 2 * MARGIN))
    scale = inner / max(piece.width, piece.height)
    piece = piece.resize(
        (max(1, round(piece.width * scale)), max(1, round(piece.height * scale))),
        Image.LANCZOS)

    box = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    box.paste(piece, ((SIZE - piece.width) // 2, (SIZE - piece.height) // 2))
    return box, dropped


#: Kyron's own pieces: the source beside it, the name, and how to find it.
PIECES = [
    ("star", "Star", ["star", "sparkle", "holographic", "celebration"]),
    ("star-rose", "Rose star", ["star", "pink", "glass", "cute"]),
    ("bolt", "Bolt", ["bolt", "lightning", "holographic", "energy"]),
    ("bolt-galaxy", "Galaxy bolt", ["bolt", "lightning", "galaxy", "space"]),
    ("diamond", "Diamond", ["diamond", "gem", "jewel", "shine"]),
    ("crown", "Crown", ["crown", "gold", "king", "queen", "head"]),
    ("ghost", "Ghost", ["ghost", "halloween", "spooky", "holographic"]),
]


#: How far a re-cut may drift from the committed PNG before it counts as a
#: different picture.
#:
#: Not zero, and the reason is that this compares the output of a JPEG decoder
#: and a Lanczos resampler, both of which are allowed to change by a bit
#: between Pillow releases. A bar of zero would turn every upgrade of a
#: dependency into a red build about artwork nobody touched. A hand edit, a
#: different source, or a change to the cut moves the *mean*, which is what
#: the first of these is for; the second catches a small patch somebody
#: painted over one corner.
DRIFT_MEAN, DRIFT_MAX = 1.0, 12


def verify_cut(piece_id, image):
    """How far the committed PNG is from what cutting produces now."""
    path = ART / f"{piece_id}.png"
    if not path.exists():
        return f"{path.relative_to(ROOT)} is not here; run: python3 tools/art.py cut"

    committed = Image.open(path)
    if committed.size != image.size:
        return (f"{path.relative_to(ROOT)}: committed {committed.width}x"
                f"{committed.height}, cutting gives {image.width}x{image.height}")

    difference = numpy.abs(
        numpy.asarray(committed.convert("RGBA"), dtype=numpy.int16) -
        numpy.asarray(image, dtype=numpy.int16))
    mean, worst = difference.mean(), int(difference.max())
    if mean > DRIFT_MEAN or worst > DRIFT_MAX:
        return (f"{path.relative_to(ROOT)}: differs from its source by "
                f"{mean:.2f} on average and {worst} at worst (allowed "
                f"{DRIFT_MEAN} and {DRIFT_MAX}). The committed picture and "
                f"sources/{piece_id}.jpg have come apart")
    return None


def command_cut(args):
    ART.mkdir(exist_ok=True)
    entries = []
    wrong = []
    for piece_id, name, tags in PIECES:
        source = SOURCES / f"{piece_id}.jpg"
        if not source.exists():
            raise SystemExit(f"{source.relative_to(ROOT)} is missing")
        image, dropped = cut_out(source)
        path = ART / f"{piece_id}.png"
        if getattr(args, "verify", False):
            fault = verify_cut(piece_id, image)
            if fault:
                wrong.append(fault)
        else:
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
        aside = f", dropped {dropped}" if dropped else ""
        print(f"{path.relative_to(ROOT)}  {image.width}x{image.height}{aside}")

    # Anything somebody else contributed is kept; only Kyron's own pieces are
    # rewritten from here.
    mine = {entry["id"] for entry in entries}
    existing = read_catalogue().get("artwork", []) if CATALOGUE.exists() else []
    theirs = [entry for entry in existing if entry.get("id") not in mine]
    catalogue = json.dumps({"schema": 1, "artwork": entries + theirs}, indent=2) + "\n"

    if getattr(args, "verify", False):
        if CATALOGUE.read_text() != catalogue:
            wrong.append(f"{CATALOGUE.name} is not what cutting produces; "
                         f"run: python3 tools/art.py cut")
        for fault in wrong:
            print(f"  {fault}")
        print(f"\n{len(entries)} checked, {len(wrong)} adrift")
        return 1 if wrong else 0

    CATALOGUE.write_text(catalogue)
    print(f"\n{len(entries)} cut, {len(theirs)} left alone, "
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

    cut = commands.add_parser("cut", help="re-cut Kyron's own pieces from sources/")
    cut.add_argument("--verify", action="store_true",
                     help="compare against what is committed instead of writing")
    commands.add_parser("check", help="everything CI checks")

    sheet = commands.add_parser("sheet", help="a contact sheet to look at")
    sheet.add_argument("-o", "--out", default="contact-sheet.png")
    sheet.add_argument("--columns", type=int, default=5)
    sheet.add_argument("--size", type=int, default=240)

    args = parser.parse_args()
    return {
        "cut": command_cut,
        "check": command_check,
        "sheet": command_sheet,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
