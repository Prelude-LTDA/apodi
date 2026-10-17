"""Check that hand edits kept the fitted advance widths (no reference fonts needed).

  python check_locked.py sources/*.ufo

Every UFO stores the fitted advance width of each metric-bearing glyph in its lib under
`org.apodi.lockedAdvanceWidths`. Changing one of those widths breaks line-for-line
compatibility; this lists any glyph whose width no longer matches. Exit status 1 if any.
"""
import sys

import ufoLib2


def main(paths):
    bad = 0
    for p in paths:
        ufo = ufoLib2.Font.open(p, lazy=True)
        locked = ufo.lib.get("org.apodi.lockedAdvanceWidths", {})
        diffs = [(g, w, ufo[g].width) for g, w in sorted(locked.items()) if g in ufo and ufo[g].width != w]
        missing = [g for g in locked if g not in ufo]
        bad += len(diffs) + len(missing)
        status = "ok" if not (diffs or missing) else f"{len(diffs)} changed, {len(missing)} missing"
        print(f"{p}: {len(locked)} locked widths, {status}")
        for g, w, now in diffs[:20]:
            print(f"    {g}: locked {w}, now {now}")
        for g in missing[:20]:
            print(f"    {g}: missing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
