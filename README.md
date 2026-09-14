# Kyron artwork

Artwork lens authors can use, for [Kyron](https://github.com/KyronLabs/kyron)'s
lens studio. All of it CC0: use any of it for anything, without asking.

**Adding a piece does not need an app release, or a studio release.** Merge it
here and the studio offers it.

| | |
|:--|:--|
| `catalogue.json` | The catalogue. This is what the studio reads. |
| `art/` | The pieces, as PNGs with an alpha channel. |
| `tools/art.py` | Draw Kyron's own pieces, check the catalogue, render a contact sheet. |

## Why this exists

A lens is artwork pinned to a face. Somebody opening the studio for the first
time has none, so the first thing the tool asks of them is the one thing they
cannot do yet — which is where a beginner stops.

## What the studio reads

```json
{
  "schema": 1,
  "artwork": [
    {
      "id": "star",
      "name": "Star",
      "url": "https://kyronlabs.github.io/kyron-artwork/art/star.png",
      "tags": ["shape", "sparkle", "celebration"],
      "author": "Kyron",
      "licence": "CC0-1.0",
      "width": 512,
      "height": 512
    }
  ]
}
```

The `url` is absolute and points at this repository's GitHub Pages, because it
is copied verbatim into the `asset` field of a published lens. A lens is read
on a phone that has never heard of this catalogue, so a relative path there
would resolve against nothing.

## The rules a piece has to pass

`python3 tools/art.py check` runs on every pull request. It fails on:

- an id that is not lowercase letters, digits and `-`, or one used twice;
- a missing name, author, or tags — artwork nobody can search for is artwork
  nobody will find;
- a licence that is not `CC0-1.0`;
- a `url` that is not exactly this repository's Pages URL for that id;
- a file that is not a PNG, or is not RGBA — **artwork goes on a face, so it
  has to carry an alpha channel**;
- a piece under 256px, which is soft on a large screen, or over 2048px, which
  is a download nobody needs;
- `width` or `height` in the catalogue disagreeing with the actual file;
- a piece with no transparent pixels at all, which is a rectangle that covers
  the face it is placed on;
- a drawing that touches the edge of its box, which will be cut off rather
  than sit on the face;
- a PNG in `art/` that is missing from the catalogue, which nothing can reach.

What it cannot check is whether the artwork is yours. That is what the pull
request template asks, and the answer is taken on trust.

## Kyron's own pieces are drawn, not pasted

The ten pieces authored by Kyron are produced by `tools/art.py draw`. A pull
request that changes the crown shows a diff you can read, and anybody can
rebuild every one and compare. CI redraws them and fails if a committed file
and the code that claims to produce it have come apart.

Artwork from anybody else arrives as PNGs, which is the normal case. `draw`
only ever rewrites the pieces it defines and leaves everything else alone.

```bash
python3 tools/art.py draw       # rewrite Kyron's own pieces
python3 tools/art.py check      # everything CI checks
python3 tools/art.py sheet      # a contact sheet to look at
```

## Adding your own

1. Draw it. PNG, RGBA, between 256 and 2048 a side, with a margin so nothing
   touches the edge.
2. Save it as `art/<id>.png`.
3. Add an entry to `catalogue.json`.
4. Run `python3 tools/art.py check`.
5. Open a pull request and answer the four questions in the template.

The most important one is the first: **it has to be yours.** CC0 gives away
rights permanently and to everybody, so a piece traced from somebody else's
work, a font, a game, a film, a brand, or an emoji set cannot go in here. That
is not a formality — a published lens carrying it gets copied and served to
people who will never see this repository.

## Licence

Artwork: **CC0 1.0** — public domain, no attribution required.
Tooling: **MIT**.

The reasoning for CC0 rather than something with attribution is in `LICENSE`,
and it is worth reading before proposing a change to it.
