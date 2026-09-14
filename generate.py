#!/usr/bin/env python3
"""
Ja'fari Hijri calendar feed generator.

Reads the official Hijri date published by the office of Grand Ayatollah
al-Sistani (Najaf), records it as a verified anchor, and regenerates an
ICS feed in which:

  * days inside months confirmed by an anchor are EXACT
  * days beyond the last confirmed month are ESTIMATED, using Umm al-Qura
    shifted by an offset that is re-derived from the newest anchor each run

Anchors accumulate in anchors.json, so the verified span grows over time.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from hijridate import Gregorian, Hijri

ROOT = Path(__file__).parent
ANCHORS = ROOT / "anchors.json"
OUT_ICS = ROOT / "hijri.ics"

SOURCE_URL = "https://www.sistani.org/"
NAJAF_TZ = timezone(timedelta(hours=3))          # Asia/Baghdad, no DST

YEARS_BACK = 1
YEARS_AHEAD = 2

AR_MONTHS = [
    "محرم", "صفر", "ربيع الأول", "ربيع الآخر",
    "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
    "رمضان", "شوال", "ذو القعدة", "ذو الحجة",
]

# Spelling variants the site may use, normalised -> month number
_VARIANTS = {
    "محرم": 1, "المحرم": 1,
    "صفر": 2,
    "ربيع الاول": 3, "ربيع 1": 3,
    "ربيع الاخر": 4, "ربيع الثاني": 4, "ربيع 2": 4,
    "جمادى الاولى": 5, "جمادي الاولى": 5, "جمادى 1": 5,
    "جمادى الاخرة": 6, "جمادي الاخرة": 6, "جمادى الثانية": 6, "جمادى 2": 6,
    "رجب": 7,
    "شعبان": 8,
    "رمضان": 9, "شهر رمضان": 9,
    "شوال": 10,
    "ذو القعدة": 11, "ذي القعدة": 11, "ذوالقعدة": 11,
    "ذو الحجة": 12, "ذي الحجة": 12, "ذوالحجة": 12,
}

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
EN_TO_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def ar_num(n: int) -> str:
    return str(n).translate(EN_TO_AR)


def normalise(s: str) -> str:
    """Fold Arabic orthographic variants so month names match reliably."""
    s = s.translate(AR_DIGITS)
    s = re.sub(r"[\u0640\u064B-\u0652\u0670]", "", s)   # tatweel + harakat
    s = s.replace("آ", "ا").replace("أ", "ا").replace("إ", "ا")
    s = s.replace("ة", "ة").replace("ي", "ي")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- scraping

def fetch_official_date() -> tuple[date, int, int, int]:
    """Return (gregorian_date, hijri_year, hijri_month, hijri_day) from sistani.org."""
    resp = requests.get(
        SOURCE_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; hijri-feed/1.0)"},
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    text = normalise(re.sub(r"<[^>]+>", " ", resp.text))

    month_alt = "|".join(sorted(map(re.escape, _VARIANTS), key=len, reverse=True))
    m = re.search(
        rf"(\d{{1,2}})\s*[-–]?\s*({month_alt})\s*[-–]?\s*(\d{{4}})\s*ه",
        text,
    )
    if not m:
        raise RuntimeError("Could not locate the Hijri date on sistani.org")

    hd, hmon, hy = int(m.group(1)), _VARIANTS[m.group(2)], int(m.group(3))
    if not (1 <= hd <= 30 and 1300 < hy < 1600):
        raise RuntimeError(f"Implausible Hijri date parsed: {hd}/{hmon}/{hy}")

    # Prefer the Gregorian date printed alongside; fall back to Najaf's today.
    g = None
    gm = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})\b", resp.text)
    if gm:
        try:
            g = datetime.strptime(
                f"{gm.group(1)} {gm.group(2)} {gm.group(3)}", "%d %b %Y"
            ).date()
        except ValueError:
            g = None
    if g is None or abs((g - datetime.now(NAJAF_TZ).date()).days) > 2:
        g = datetime.now(NAJAF_TZ).date()

    return g, hy, hmon, hd


# ---------------------------------------------------------------- anchors

def load_anchors() -> dict:
    if ANCHORS.exists():
        return json.loads(ANCHORS.read_text(encoding="utf-8"))
    return {"month_starts": {}, "log": []}


def record(store: dict, g: date, hy: int, hmon: int, hd: int) -> bool:
    """Derive this Hijri month's first Gregorian day and store it. True if new."""
    start = g - timedelta(days=hd - 1)
    key = f"{hy}-{hmon:02d}"
    prev = store["month_starts"].get(key)
    if prev == start.isoformat():
        return False
    store["month_starts"][key] = start.isoformat()
    store["log"].append(
        {"seen": g.isoformat(), "hijri": f"{hy}-{hmon:02d}-{hd:02d}",
         "month_start": start.isoformat(),
         "revised_from": prev}
    )
    store["log"] = store["log"][-400:]
    return True


# ---------------------------------------------------------------- calendar

def month_index(hy: int, hmon: int) -> int:
    return hy * 12 + (hmon - 1)


def build_lookup(store: dict) -> dict[date, tuple[int, int, int]]:
    """Exact Gregorian->Hijri mapping for every day inside confirmed months."""
    starts = {}
    for key, iso in store["month_starts"].items():
        hy, hmon = (int(x) for x in key.split("-"))
        starts[month_index(hy, hmon)] = date.fromisoformat(iso)

    out: dict[date, tuple[int, int, int]] = {}
    for idx in sorted(starts):
        nxt = starts.get(idx + 1)
        if nxt is None:
            # Length not yet announced. A Hijri month is never shorter than 29
            # days, so days 1-29 are already certain; day 30 is not.
            length = 29
        else:
            length = (nxt - starts[idx]).days
            if length not in (29, 30):
                continue                  # inconsistent pair, skip rather than lie
        hy, hmon = divmod(idx, 12)
        for i in range(length):
            out[starts[idx] + timedelta(days=i)] = (hy, hmon + 1, i + 1)
    return out


def derive_offset(store: dict) -> int:
    """Days to shift Umm al-Qura so it agrees with the newest anchor."""
    if not store["month_starts"]:
        return 1
    key = max(store["month_starts"], key=lambda k: month_index(*map(int, k.split("-"))))
    hy, hmon = (int(x) for x in key.split("-"))
    observed = date.fromisoformat(store["month_starts"][key])
    try:
        computed = date(*Hijri(hy, hmon, 1).to_gregorian().datetuple())
    except (ValueError, OverflowError):
        return 1
    return max(-3, min(3, (observed - computed).days))


def estimate(g: date, offset: int) -> tuple[int, int, int]:
    h = Gregorian.fromdate(g - timedelta(days=offset)).to_hijri()
    return h.year, h.month, h.day


# ---------------------------------------------------------------- ics

def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 73:
        return line
    chunks, i = [], 0
    while i < len(raw):
        size = 73 if not chunks else 72
        cut = min(i + size, len(raw))
        while cut > i and cut < len(raw) and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        chunks.append(raw[i:cut].decode("utf-8"))
        i = cut
    return ("\r\n ").join(chunks)


def build_ics(lookup, offset, first, last, generated) -> str:
    stamp = generated.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//Jafari Hijri Feed//sistani.org anchored//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:التقويم الهجري (جعفري)",
        fold(f"X-WR-CALDESC:{esc('Daily Hijri date anchored to the office of al-Sistani (Najaf). Updated ' + generated.strftime('%Y-%m-%d'))}"),
        "X-WR-TIMEZONE:Asia/Kuwait",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    g = first
    while g <= last:
        exact = lookup.get(g)
        hy, hmon, hd = exact if exact else estimate(g, offset)
        summary = f"{ar_num(hd)} {AR_MONTHS[hmon - 1]} {ar_num(hy)}"
        note = ("مؤكد حسب مكتب السيد السيستاني" if exact
                else "تقديري — لم يُعلَن هلال هذا الشهر بعد")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid5(uuid.NAMESPACE_URL, 'jafari-hijri/' + g.isoformat())}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{g:%Y%m%d}",
            f"DTEND;VALUE=DATE:{g + timedelta(days=1):%Y%m%d}",
            fold(f"SUMMARY:{esc(summary)}"),
            fold(f"DESCRIPTION:{esc(note)}"),
            "TRANSP:TRANSPARENT",
            "X-MICROSOFT-CDO-ALLDAYEVENT:TRUE",
            "END:VEVENT",
        ]
        g += timedelta(days=1)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------- main

def main() -> int:
    store = load_anchors()

    try:
        g, hy, hmon, hd = fetch_official_date()
        fresh = record(store, g, hy, hmon, hd)
        print(f"sistani.org: {g} = {hd} {AR_MONTHS[hmon-1]} {hy}"
              f"{'  [new anchor]' if fresh else '  [already known]'}")
    except Exception as exc:                       # keep serving the old feed
        print(f"WARNING: could not read sistani.org ({exc})", file=sys.stderr)
        if not store["month_starts"]:
            print("No anchors on file and fetch failed; aborting.", file=sys.stderr)
            return 1

    ANCHORS.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    lookup = build_lookup(store)
    offset = derive_offset(store)
    today = datetime.now(NAJAF_TZ).date()
    first = date(today.year - YEARS_BACK, 1, 1)
    last = date(today.year + YEARS_AHEAD, 12, 31)

    OUT_ICS.write_text(
        build_ics(lookup, offset, first, last, datetime.now(timezone.utc)),
        encoding="utf-8",
    )

    confirmed = sum(1 for d in lookup if first <= d <= last)
    total = (last - first).days + 1
    print(f"months on file : {len(store['month_starts'])}")
    print(f"umm al-qura offset: {offset:+d} day(s)")
    print(f"wrote {OUT_ICS.name}: {total} days, {confirmed} exact, {total - confirmed} estimated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
