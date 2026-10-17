"""Side-by-side renderings: reference (Aptos, read locally) vs Apodi, for visual review.

  APTOS_DIR=/path/to/aptos python -I render.py --fonts fonts/ttf --out docs/images

Writes one PNG per style (alphabet, numerals/currency, paragraph set with identical line
breaks, and an overlay strip), plus M_before_after.png. The PNGs are renderings for review
only; nothing is traced or measured from them.
"""
import argparse
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_metrics import PAIRS  # noqa: E402

ROWS = [
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789 €$£¥₹₽ R$ 1.234,56 % & @ # ( ) [ ] { } / \\ ? ! ; :",
    "ÁÀÂÃÄÇÉÊÍÓÔÕÚÜ áàâãäçéêíóôõúü ñ ß æ œ ø ł ő ș ț",
    "“Quoted” ‘single’ — en–dash … • · ° ± × ÷ ≠ ≤ ≥ fi fl ff ffi",
]
PARA = ("A Prelude Ltda. registrou receita líquida de R$ 4.218.750,00 no terceiro trimestre de 2026, "
        "alta de 12,4% sobre o mesmo período do ano anterior. The board approved the revised budget "
        "of €1,250,000 for FY2027; the Italian subsidiary (Milano S.r.l.) reported un fatturato di "
        "€ 876.300, in crescita del 7,9%. Quarterly figures: Q1 1,024; Q2 1,187; Q3 1,342; Q4 1,409.")
SIZE = 44
W = 1900


def font(path, size=SIZE):
    return ImageFont.truetype(path, size=size, layout_engine=ImageFont.Layout.RAQM)


def wrap(text, f, width):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def render_style(stem, ref_path, mine_path, out):
    fr, fm = font(ref_path), font(mine_path)
    lab = font(mine_path, 20)
    lh = int(SIZE * 1.45)
    para_w = 1500
    ref_lines = wrap(PARA, fr, para_w)
    my_lines = wrap(PARA, fm, para_w)
    h = 70 + len(ROWS) * (2 * lh + 30) + 2 * (len(ref_lines) * lh + 60) + 3 * lh + 120
    im = Image.new("RGB", (W, h), "white")
    d = ImageDraw.Draw(im)
    y = 20
    d.text((20, y), f"{stem}: grey label = reference (Aptos), black label = Apodi. Same size, same origin.", fill="black", font=lab)
    y += 50
    for row in ROWS:
        d.text((20, y + 18), "ref", fill=(150, 150, 150), font=lab)
        d.text((90, y), row, fill="black", font=fr)
        y += lh
        d.text((20, y + 18), "Apodi", fill="black", font=lab)
        d.text((90, y), row, fill="black", font=fm)
        y += lh + 30
    for name, f, lines in (("ref", fr, ref_lines), ("Apodi", fm, my_lines)):
        d.text((20, y), f"{name} paragraph (greedy wrap at {para_w}px; {len(lines)} lines)", fill="black", font=lab)
        y += 34
        for ln in lines:
            d.text((90, y), ln, fill="black", font=f)
            y += lh
        y += 26
    # overlay: reference in red, Apodi in blue, same origin
    d.text((20, y), "overlay (red = reference, blue = Apodi, purple = both)", fill="black", font=lab)
    y += 34
    for row in ROWS[:3]:
        a = Image.new("L", (W - 90, lh), 0)
        b = Image.new("L", (W - 90, lh), 0)
        ImageDraw.Draw(a).text((0, 0), row, fill=255, font=fr)
        ImageDraw.Draw(b).text((0, 0), row, fill=255, font=fm)
        rgb = Image.merge("RGB", (ImageChops.invert(b), ImageChops.invert(ImageChops.lighter(a, b)), ImageChops.invert(a)))
        im.paste(rgb, (90, y))
        y += lh
    im = im.crop((0, 0, W, y + 20))
    im.save(out)
    return ref_lines == my_lines


def render_M(opensans_vf, mine_dir, ref_dir, out):
    """Open Sans M (before) vs Apodi M (after); with ref_dir, also a reference rendering."""
    cells = []
    vf = font(opensans_vf, 300)
    try:
        vf.set_variation_by_axes([450, 100])
    except Exception:
        pass
    cells.append(("Open Sans (before)", vf, 1462 / 1346))
    cells.append(("Apodi Regular (after)", font(os.path.join(mine_dir, "Apodi-Regular.ttf"), 300), 1))
    cells.append(("Apodi Bold", font(os.path.join(mine_dir, "Apodi-Bold.ttf"), 300), 1))
    cells.append(("Apodi Italic", font(os.path.join(mine_dir, "Apodi-Italic.ttf"), 300), 1))
    if ref_dir:
        cells.append(("reference (Aptos)", font(os.path.join(ref_dir, "Aptos.ttf"), 300), 1))
    im = Image.new("RGB", (330 * len(cells), 420), "white")
    d = ImageDraw.Draw(im)
    lab = font(os.path.join(mine_dir, "Apodi-Regular.ttf"), 20)
    for i, (name, f, _) in enumerate(cells):
        d.text((i * 330 + 20, 10), name, fill="black", font=lab)
        d.text((i * 330 + 20, 40), "M", fill="black", font=f)
        d.line([(i * 330 + 10, 40 + f.getbbox("M")[3]), (i * 330 + 320, 40 + f.getbbox("M")[3])], fill=(200, 0, 0))
    im.save(out)


def render_specimen(mine_dir, out):
    """Apodi only: one line per style (safe to publish)."""
    stems = list(PAIRS)
    im = Image.new("RGB", (W, 40 + 70 * len(stems)), "white")
    d = ImageDraw.Draw(im)
    lab = font(os.path.join(mine_dir, "Apodi-Regular.ttf"), 20)
    y = 20
    for stem in stems:
        p = os.path.join(mine_dir, stem + ".ttf")
        if not os.path.exists(p):
            continue
        d.text((20, y + 14), stem, fill=(120, 120, 120), font=lab)
        d.text((330, y), "Minimum R$ 1.234,56 — Hamburgefonstiv ÁÉÇÕ fi fl", fill="black", font=font(p, 40))
        y += 70
    im.crop((0, 0, W, y + 10)).save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="fonts/ttf")
    ap.add_argument("--aptos", default=os.environ.get("APTOS_DIR"))
    ap.add_argument("--opensans-vf", default=None, help="Open Sans variable TTF for the M before/after")
    ap.add_argument("--out", default="docs/comparison", help="side-by-side images (contain reference renderings)")
    ap.add_argument("--images", default="docs/images", help="Apodi/Open Sans-only images")
    a = ap.parse_args()
    if not a.aptos:
        sys.exit("set APTOS_DIR or pass --aptos")
    os.makedirs(a.out, exist_ok=True)
    for stem, refname in PAIRS.items():
        mine = os.path.join(a.fonts, stem + ".ttf")
        ref = os.path.join(a.aptos, refname)
        if os.path.exists(mine) and os.path.exists(ref):
            same = render_style(stem, ref, mine, os.path.join(a.out, f"compare_{stem}.png"))
            print(stem, "paragraph breaks identical" if same else "PARAGRAPH BREAKS DIFFER")
    os.makedirs(a.images, exist_ok=True)
    render_specimen(a.fonts, os.path.join(a.images, "specimen.png"))
    if a.opensans_vf:
        render_M(a.opensans_vf, a.fonts, None, os.path.join(a.images, "M_before_after.png"))
        render_M(a.opensans_vf, a.fonts, a.aptos, os.path.join(a.out, "M_with_reference.png"))


if __name__ == "__main__":
    main()
