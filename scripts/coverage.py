"""Character-set coverage: reference metrics JSON (codepoints) vs Open Sans cmap.

Usage: python -I coverage.py <ref_Regular.json> <ref_Italic.json> <OpenSans-VF.ttf> <OpenSans-Italic-VF.ttf>
"""
import json
import sys
import unicodedata

from fontTools.ttLib import TTFont

BLOCKS = [
    ("Basic Latin", 0x20, 0x7E), ("Latin-1 Supplement", 0xA0, 0xFF),
    ("Latin Extended-A", 0x100, 0x17F), ("Latin Extended-B", 0x180, 0x24F),
    ("IPA/Spacing modifiers", 0x250, 0x2FF), ("Combining marks", 0x300, 0x36F),
    ("Greek", 0x370, 0x3FF), ("Cyrillic", 0x400, 0x52F),
    ("Latin Extended Additional", 0x1E00, 0x1EFF), ("General Punctuation", 0x2000, 0x206F),
    ("Super/subscripts", 0x2070, 0x209F), ("Currency", 0x20A0, 0x20CF),
    ("Letterlike", 0x2100, 0x214F), ("Number forms", 0x2150, 0x218F),
    ("Arrows", 0x2190, 0x21FF), ("Math operators", 0x2200, 0x22FF),
    ("Misc technical", 0x2300, 0x23FF), ("Box/blocks/shapes", 0x2500, 0x25FF),
    ("Misc symbols/dingbats", 0x2600, 0x27BF), ("Private Use", 0xE000, 0xF8FF),
    ("Alphabetic presentation", 0xFB00, 0xFB4F),
]


def block(cp):
    for n, a, b in BLOCKS:
        if a <= cp <= b:
            return n
    return "Other"


def name(cp):
    try:
        return unicodedata.name(chr(cp))
    except ValueError:
        return "?"


def main(refR, refI, osR, osI):
    for label, ref, osf in (("Upright", refR, osR), ("Italic", refI, osI)):
        a = {int(k) for k in json.load(open(ref))["advances"]}
        o = set(TTFont(osf).getBestCmap())
        miss = sorted(a - o)
        extra = len(o - a)
        print(f"## {label}: reference {len(a)} codepoints, Open Sans {len(o)}; "
              f"in reference but not Open Sans: {len(miss)}; in Open Sans only: {extra}\n")
        byb = {}
        for cp in miss:
            byb.setdefault(block(cp), []).append(cp)
        for b, cps in byb.items():
            print(f"- **{b}** ({len(cps)}): " + ", ".join(
                f"U+{c:04X} {chr(c) if c >= 0x20 and not 0xE000 <= c <= 0xF8FF else ''} ({name(c).title()})" for c in cps))
        print()


if __name__ == "__main__":
    main(*sys.argv[1:5])
