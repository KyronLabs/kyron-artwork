# Kyron artwork

Artwork lens authors can use, for [Kyron](https://github.com/KyronLabs/kyron)'s
lens studio. All of it CC0: use any of it for anything, without asking.

**Adding a piece does not need an app release, or a studio release.** Merge it
here and the studio offers it.

| | |
|:--|:--|
| `catalogue.json` | The catalogue. This is what the studio reads. |
| `art/` | The pieces, as PNGs with an alpha channel. |
| `sources/` | The pictures Kyron's own pieces were cut out of. |
| `tools/art.py` | Cut Kyron's own pieces, check the catalogue, render a contact sheet. |

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

## Kyron's own pieces are cut here, not in an image editor

They arrive as renders on a flat plate — black, white, a blue backdrop — and a
lens needs the picture with the plate gone. `tools/art.py cut` is that step,
and it lives here rather than in somebody's copy of Photoshop so the result is
reproducible: the source is committed in `sources/`, anybody can re-cut and
compare, and CI fails if a committed PNG and the source it claims to come from
have come apart.

```bash
python3 tools/art.py cut          # re-cut Kyron's own pieces from sources/
python3 tools/art.py cut --verify # what CI runs: compare, do not overwrite
python3 tools/art.py check        # everything else CI checks
python3 tools/art.py sheet        # a contact sheet to look at
```

Artwork from anybody else arrives already cut, as a PNG, which is the normal
case. `cut` only ever rewrites the pieces it lists and leaves everything else
alone.

### What cutting actually does

Four steps, and each one is there because of something that went wrong
without it:

1. **Flood fill from the border**, rather than keying on colour. A colour key
   punches the ghost's eyes out: they are the same black as the plate behind
   it. Only plate the edge of the picture can reach is plate.
2. **Undo the blend at the rim.** Edge pixels are part subject and part plate,
   so they ship as a halo — dark on a black plate, pale on white — unless the
   blend is reversed.
3. **Drop everything but the subject.** The diamond came with a stock
   watermark in the corner; it is a separate island of pixels and it goes.
4. **Treat a lit plate as plate.** The crown is shot on deep blue with a
   sparkle over one ball, and the glow lifts the blue far enough from the
   plate colour that a distance test called it subject — the crown came out
   wearing a lump of blue. Brightness cannot tell them apart; hue can, and
   only when the plate is a saturated colour somebody chose.

`--verify` allows a little drift rather than demanding identical bytes,
because this is the output of a JPEG decoder and a resampler and both may move
by a bit when Pillow is upgraded. A hand edit moves it much further; a single
flipped alpha pixel is caught.

## How the studio gets it

Merging to `main` publishes to **GitHub Pages**:

```
https://kyronlabs.github.io/kyron-artwork/catalogue.json
```

A stable public URL on a CDN, needing no token — which is what a tool fetching
a file at runtime requires. Actions artifacts cannot do that job: they need
authentication to download even from a public repo, they expire, and the id
changes every run. They are used here for the contact sheet, which is a thing a
person looks at once, on a pull request.

The studio reads `CATALOGUE_URL` in `src/format/artwork.js`, overridable with
`KYRON_ARTWORK_CATALOGUE` so a staging build can point elsewhere.

**Two settings have to be right**, and each fails differently:

| | |
|:--|:--|
| Settings → Pages → Source → **GitHub Actions** | Without it: *Failed to create deployment (status: 404) … Ensure GitHub Pages has been enabled* |
| Settings → Environments → **github-pages** → Deployment branches and tags → allow `main` | Without it: *Branch "main" is not allowed to deploy to github-pages due to environment protection rules* |

The second one is worth knowing about, because it is invisible. The
environment's branch policy is fixed when Pages is first turned on, and it
names whatever the default branch was *then* — so a repository that started
life with some other default branch keeps refusing to publish from `main`
afterwards, and the job that refuses has no log at all: it is rejected before
a runner is assigned, and the reason is only an annotation.

That is why there is a third CI job. **Publishing and being fetchable are
different claims**, and the studio depends on the second, so `confirm` asks the
published URL the way the studio does and compares what comes back with what
was committed. When publishing fails instead, it says which of the two settings
is wrong, in the run, rather than leaving a red tick with nothing behind it.

Until publishing works the URL 404s, the studio says so in plain words, and the
library is empty — so nothing breaks, but nothing appears either.

## Adding your own

1. Draw it. PNG, RGBA, between 256 and 2048 a side, with a margin so nothing
   touches the edge. If it is on a flat background, `tools/art.py` has the
   cut-out in it — put the source in `sources/` and add it to `PIECES`.
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
