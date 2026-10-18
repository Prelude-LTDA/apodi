"""Before/after sheet for the letter-shape revisions (G K k M, cut C c S s, italic obliques).

  python -I scripts/revisions.py --before OLD_TTF_DIR --after fonts/ttf [--aptos APTOS_DIR] \
         --styles Regular,Bold --out docs/images/revisions.png

Columns: reference (only with --aptos), Apodi before, Apodi after. One block per style, with an
upright and an italic group of rows. A sheet made with --aptos contains reference renderings:
keep it local (docs/comparison/ is git-ignored).
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

REF = {"": "Aptos", "Narrow": "Aptos Narrow", "Display": "Aptos Display"}
UPRIGHT = ["G Ğ Gaming", "K Ķ Kick", "k ķ kick keeps", "M Museum", "C c Ç ç Classic",
           "S s Ş š Sessions", "Sessions class asks", "Gaming Kick Museum"]
ITALIC = ["f e é offence", "C c Ç ç classic", "S s Ş š Sessions", "Sessions class asks",
          "k ķ kick keeps", "offence classic Sessions", "Gaming Kick Museum"]
SIZE = 54


def paths(stem_family, weight, italic, before, after, aptos):
    """stem_family: '', 'Narrow' or 'Display'; weight: 'Regular' or 'Bold'."""
    st = {("Regular", False): "Regular", ("Bold", False): "Bold",
          ("Regular", True): "Italic", ("Bold", True): "BoldItalic"}[(weight, italic)]
    name = f"Apodi{stem_family}-{st}.ttf"
    out = []
    if aptos:
        ref_st = {"Regular": "", "Bold": " Bold", "Italic": " Italic", "BoldItalic": " Bold Italic"}[st]
        out.append(("Aptos", os.path.join(aptos, REF[stem_family] + ref_st + ".ttf")))
    out.append(("Apodi before", os.path.join(before, name)))
    out.append(("Apodi after", os.path.join(after, name)))
    return out


def closeup(versions, aptos, out, text="s S Sessions", size=200):
    """Large rows of `text`: Aptos (if given), then each (label, font dir), in Regular and Bold."""
    lab = ImageFont.truetype(os.path.join(versions[-1][1], "Apodi-Regular.ttf"), 24)
    rows = []
    for st, ref in (("Regular", "Aptos.ttf"), ("Bold", "Aptos Bold.ttf")):
        if aptos:
            rows.append((f"Aptos {st}", os.path.join(aptos, ref)))
        for name, d in versions:
            rows.append((f"Apodi {name} {st}", os.path.join(d, f"Apodi-{st}.ttf")))
    lh = int(size * 1.3)
    im = Image.new("RGB", (60 + int(size * 6.5), 20 + len(rows) * (lh + 34)), "white")
    d = ImageDraw.Draw(im)
    y = 10
    for name, p in rows:
        d.text((20, y), name, fill=(110, 110, 110), font=lab)
        d.text((60, y + 30), text, fill="black", font=ImageFont.truetype(p, size, layout_engine=ImageFont.Layout.RAQM))
        y += lh + 34
    im.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--closeup", default=None,
                    help="label=dir,label=dir,...: write a large 's S Sessions' close-up of these versions instead")
    ap.add_argument("--before", default=None)
    ap.add_argument("--after", default="fonts/ttf")
    ap.add_argument("--aptos", default=None)
    ap.add_argument("--styles", default="Regular,Bold", help="e.g. Regular,Bold,NarrowBold,DisplayRegular")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.closeup:
        closeup([tuple(v.split("=", 1)) for v in a.closeup.split(",")], a.aptos, a.out)
        return
    blocks = []
    for s in a.styles.split(","):
        fam = "Narrow" if s.startswith("Narrow") else "Display" if s.startswith("Display") else ""
        weight = s[len(fam):] or "Regular"
        blocks.append((s, [(False, t) for t in UPRIGHT] + [(True, t) for t in ITALIC], fam, weight))
    label_font = ImageFont.truetype(os.path.join(a.after, "Apodi-Regular.ttf"), 22)
    ncol = 3 if a.aptos else 2
    colw = 720
    lh = int(SIZE * 1.35)
    H = sum(70 + len(rows) * lh + 30 for _, rows, _, _ in blocks) + 20
    im = Image.new("RGB", (60 + ncol * colw, H), "white")
    d = ImageDraw.Draw(im)
    y = 10
    for s, rows, fam, weight in blocks:
        cols = paths(fam, weight, False, a.before, a.after, a.aptos)
        d.text((20, y), f"{('Apodi ' + fam).strip()} {weight} / Italic", fill="black", font=label_font)
        for i, (lab, _) in enumerate(cols):
            d.text((60 + i * colw, y + 34), lab, fill=(110, 110, 110), font=label_font)
        y += 70
        for italic, text in rows:
            cols = paths(fam, weight, italic, a.before, a.after, a.aptos)
            for i, (_, p) in enumerate(cols):
                f = ImageFont.truetype(p, SIZE, layout_engine=ImageFont.Layout.RAQM)
                d.text((60 + i * colw, y), text, fill="black", font=f)
            if italic and text == ITALIC[0]:
                d.line([(20, y - 4), (60 + ncol * colw - 20, y - 4)], fill=(220, 220, 220))
            y += lh
        y += 30
    im.save(a.out)


if __name__ == "__main__":
    main()
