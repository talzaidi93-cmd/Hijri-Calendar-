# التقويم الهجري الجعفري — self-updating calendar feed

A Hijri date calendar for Google Calendar, anchored to the official date
published by the office of Grand Ayatollah al-Sistani in Najaf. Arabic month
names, Arabic-Indic numerals, one all-day entry per day.

It re-checks sistani.org twice daily and corrects itself when a new crescent
is announced.


## Limits worth knowing

- Google refreshes subscribed feeds on its own schedule, typically every
  12–24 hours. A correction published tonight may not appear in your calendar
  until tomorrow.
- If sistani.org is unreachable or changes its page layout, the run logs a
  warning and republishes the previous feed rather than breaking. Check the
  Actions tab if dates ever look frozen.
- This tracks Najaf. If you follow a different marjaʿ, or your local community
  announces separately, the feed may differ by a day. The announcement you
  follow is the authority — this is a convenience, not a ruling.
