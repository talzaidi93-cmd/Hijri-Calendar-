# التقويم الهجري الجعفري — self-updating calendar feed

A Hijri date calendar for Google Calendar, anchored to the official date
published by the office of Grand Ayatollah al-Sistani in Najaf. Arabic month
names, Arabic-Indic numerals, one all-day entry per day.

It re-checks sistani.org twice daily and corrects itself when a new crescent
is announced.

---

## Setup (about 15 minutes, once)

### 1. Create the repository

On github.com, click **New repository**. Name it whatever you like —
`hijri-feed` works. Set it to **Public** (required for free GitHub Pages).
Don't add a README; this folder already has one.

### 2. Upload these files

On the empty repo page choose **uploading an existing file**, then drag in:

```
generate.py
anchors.json
hijri.ics
README.md
.github/workflows/update.yml
```

If the drag-and-drop flattens the `.github/workflows/` folder, create that
file manually instead: **Add file → Create new file**, type
`.github/workflows/update.yml` as the name (the slashes create the folders),
and paste the contents in.

### 3. Turn on Pages

**Settings → Pages**. Under *Build and deployment*, set Source to
**Deploy from a branch**, branch **main**, folder **/ (root)**. Save.

Wait two or three minutes. Your feed is then live at:

```
https://YOURUSERNAME.github.io/hijri-feed/hijri.ics
```

### 4. Let the action write back

**Settings → Actions → General**, scroll to *Workflow permissions*, select
**Read and write permissions**, save. Without this the daily job can run but
can't commit the updated file.

### 5. Run it once by hand

**Actions** tab → *Update Hijri feed* → **Run workflow**. Watch it go green.
Open the Pages URL above; you should see text starting with `BEGIN:VCALENDAR`.

### 6. Subscribe in Google Calendar

Google Calendar (desktop) → **Other calendars → + → From URL** → paste the
Pages URL → **Add calendar**. Rename it to `التاريخ الهجري` under
**Settings → Settings for my calendars**.

Then in Notion Calendar: **Settings → Calendars** → toggle it on.

---

## How it decides a date

Each run reads the Hijri date printed on sistani.org's home page and works
backward to the Gregorian day that month began. Those month starts pile up in
`anchors.json`, and the file is never discarded — so the record of confirmed
months grows for as long as the job keeps running.

Every day in the feed is one of two things:

- **مؤكد** — inside a month whose start has been confirmed from Najaf. Exact.
- **تقديري** — beyond the last confirmation. Calculated from Umm al-Qura,
  shifted by an offset re-derived from the most recent anchor on every run
  (currently +1 day).

Open any day in Google Calendar and the description tells you which it is.

Day 30 of the current month always shows as تقديري, even mid-month. That's
deliberate: until the next crescent is announced nobody knows whether the
month runs 29 days or 30, so claiming otherwise would be a guess dressed as
a fact.

## Limits worth knowing

- Google refreshes subscribed feeds on its own schedule, typically every
  12–24 hours. A correction published tonight may not appear in your calendar
  until tomorrow. Nothing can be done about this from the feed side.
- GitHub pauses scheduled actions on repos with no activity for 60 days.
  If updates stop, open the Actions tab and hit **Run workflow**.
- Scheduled runs on GitHub's free tier can be delayed by up to an hour at
  busy times. Harmless here.
- If sistani.org is unreachable or changes its page layout, the run logs a
  warning and republishes the previous feed rather than breaking. Check the
  Actions tab if dates ever look frozen.
- This tracks Najaf. If you follow a different marjaʿ, or your local community
  announces separately, the feed may differ by a day. The announcement you
  follow is the authority — this is a convenience, not a ruling.

## Changing the window

`generate.py` has `YEARS_BACK = 1` and `YEARS_AHEAD = 2` near the top.
Two years ahead keeps the file around 300 KB; raising it costs nothing but
adds more days that are estimates rather than confirmations.
