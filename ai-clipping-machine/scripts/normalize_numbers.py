#!/usr/bin/env python3
"""Caption number normalisation — spelled-out numbers -> numerals + symbols.

Standing rule: captions show digits, never spelled-out numbers. Speech-to-text returns
number WORDS; every burned text layer must show digits.

  "twenty-three percent"  -> "23%"
  "twenty-four seven"     -> "24/7"
  "under forty seconds"   -> "under 40 seconds"
  "one hundred K"         -> "$100k"
  "five setters"          -> "5 setters"

Run this over the caption word list **right after** the `caption_lexicon.json`
pass and before `captions_plan.py` groups it into lines.

Input/output is the repo's caption-word format:
    [{"word": "...", "start": float, "end": float}, ...]
Merged tokens inherit the span of the words they replaced, so caption timing and
line grouping stay correct.

    from normalize_numbers import normalize
    words = normalize(words)
"""
from __future__ import annotations

import re

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}

# Multi-word idioms, matched before the generic number parser. Keys are
# lowercase, punctuation-stripped word sequences.
IDIOMS = {
    ("twenty-four", "seven"): "24/7",
    ("twenty", "four", "seven"): "24/7",
    ("24", "seven"): "24/7",
    ("twenty-four", "hour"): "24-hour",
    ("nine", "to", "five"): "9-to-5",
}

# Words that must NOT be digitised — they read as words, not counts.
KEEP = {"one", "once", "first", "second", "third", "half", "quarter", "no", "none"}
# "one" is ambiguous ("one of the", "number one"); only digitise it inside a
# larger number ("one hundred") — handled explicitly below.

_PUNCT_TAIL = re.compile(r"[^\w%$/-]+$")


def _split(tok: str) -> tuple[str, str]:
    """token -> (core, trailing punctuation)"""
    m = _PUNCT_TAIL.search(tok)
    return (tok[:m.start()], tok[m.start():]) if m else (tok, "")


def _val(core: str):
    """A single word's numeric value, or None."""
    c = core.lower()
    if c in TENS:
        return TENS[c]
    if c in UNITS:
        return UNITS[c]
    if "-" in c:                                  # "twenty-three"
        a, _, b = c.partition("-")
        if a in TENS and b in UNITS and UNITS[b] < 10:
            return TENS[a] + UNITS[b]
    return None


def _numeric(core: str):
    """Already-a-numeral token -> int."""
    return int(core) if core.isdigit() else None


def normalize(words: list[dict]) -> list[dict]:
    out: list[dict] = []
    i = 0
    n = len(words)

    def merge(a: int, b: int, text: str):
        """Replace words[a:b] with one token spanning their timings."""
        out.append({"word": text + _split(words[b - 1]["word"])[1],
                    "start": words[a]["start"], "end": words[b - 1]["end"]})

    while i < n:
        cores = [_split(w["word"])[0].lower() for w in words[i:i + 3]]

        # 1. idioms
        hit = None
        for ln in (3, 2):
            key = tuple(cores[:ln])
            if len(key) == ln and key in IDIOMS:
                hit = (ln, IDIOMS[key]); break
        if hit:
            merge(i, i + hit[0], hit[1])
            i += hit[0]
            continue

        core, tail = _split(words[i]["word"])
        v = _val(core)
        if v is None:
            v = _numeric(core)
        if v is None:
            out.append(dict(words[i])); i += 1
            continue

        # 2. build the largest number phrase starting here
        j = i + 1
        total = v
        low = core.lower()
        # "one/two/... hundred|thousand"
        while j < n:
            nxt = _split(words[j]["word"])[0].lower()
            if nxt in SCALES:
                total *= SCALES[nxt]; j += 1
                # "one hundred and twenty" / "one hundred twenty"
                if j < n and _split(words[j]["word"])[0].lower() == "and" and j + 1 < n \
                        and _val(_split(words[j + 1]["word"])[0]) is not None:
                    j += 1
                continue
            add = _val(nxt)
            if add is not None and total % 100 == 0 and add < 100 and total >= 100:
                total += add; j += 1
                continue
            break

        # bare "one" that never joined a scale stays a word ("one of the coaches")
        if j == i + 1 and low in KEEP and _numeric(core) is None:
            out.append(dict(words[i])); i += 1
            continue

        text = str(total)

        # 3. suffixes that fuse onto the digits
        if j < n:
            nxt_core, _ = _split(words[j]["word"])
            nc = nxt_core.lower()
            if nc in ("percent", "percentage"):
                merge(i, j + 1, text + "%"); i = j + 1; continue
            if nc in ("k", "grand"):
                merge(i, j + 1, "$" + text + "k"); i = j + 1; continue

        if total >= 1000 and total % 1000 == 0:       # 100000 -> $100k
            text = "$" + str(total // 1000) + "k"

        merge(i, j, text)
        i = j
    return out


if __name__ == "__main__":
    import json, sys
    ws = json.load(open(sys.argv[1]))
    print(json.dumps(normalize(ws), indent=1))
