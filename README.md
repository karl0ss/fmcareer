# fmcareer

A manager's career history from a Football Manager 26 save: point it at a save and a
manager's name, and it builds one self-contained HTML page with:

- **Career overview**: profile, league record, the game's own managerial stats (games,
  money spent, record signing and sale), the climb through the league pyramid, trophy
  cabinet, manager awards and the club legends of the era.
- **A review of every season**: written summary, the final league table, cup runs,
  honours and awards, full squad statistics, the season's best 18, transfers with fees
  and notable results.
- **Honours & cups** and **Transfers** pages covering the whole career.

Everything is read from the save itself through
[fmsave](https://github.com/karl0ss/fmsave) (branch `history-decoders`, which adds the
history decoders this tool needs). Nothing is scraped from screenshots or the game UI.

## Setup

Python 3.12 or newer.

```sh
python -m venv .venv
.venv/bin/pip install git+https://github.com/karl0ss/fmcareer.git
```

The save stores competitions and awards by id only. Build the name lists once from your
own FM26 install (the tool reads the game's database files; nothing from the game is
redistributed here):

```sh
.venv/bin/fmcareer-names "/path/to/Football Manager 26" names
```

This writes `names/competition_names.csv` and `names/award_names.csv`.

## The app

```sh
.venv/bin/fmcareer-app
```

opens a page in your browser (served only on your own machine, at
`http://127.0.0.1:8765/`) where you:

1. set your saves folder and FM26 install folder (it guesses the usual Steam and
   Documents locations) and read the competition/award names from the game once;
2. pick a save;
3. load its managers and pick one: the save's human managers (tick "Show all managers"
   for every manager in the save, searchable by name or club);
4. tick the pages to include, which kinds of move the transfer lists show at first
   (loans, trials, youth intake, released players, staff), and whether to embed images;
5. generate: progress shows as it goes, and the report opens in a new tab. Reports are
   kept in `~/.cache/fmcareer/reports`.

Settings live in `~/.config/fmcareer/settings.json`. The save stays open between steps,
so a second report from the same save is much quicker.

## Command line

```sh
.venv/bin/fmcareer "/path/to/My Career.fm" "Manager Name" names -o career_report.html
```

- The manager is matched by full, first + last, or common name, ignoring case and
  accents. Any manager in the save works, not only the human one.
- `--install "/path/to/Football Manager 26"` embeds club badges, real players' photos
  and competition logos from your own install. It needs the images extra:
  `pip install "fmcareer[images] @ git+https://github.com/karl0ss/fmcareer.git"`. Clubs and
  players without licensed artwork (most non-league clubs, every regen) get a lettered
  crest or no photo.
- `--sections me,seasons,players,records,honours,transfers,club` picks the pages (default:
  all). `--show loans,trials,youth,released,staff` picks which kinds of move the transfer
  lists show at first (default: released); viewers can switch them in the report.
- `--json career_data.json` also writes the collected data.
- A large save takes a few minutes and about 3 GB of memory.

## Images

The game keeps its licensed artwork in Unity asset bundles; the address catalog next to
them names each image by the save's own ids (`club_<club uid>`, `person_<unique id>`,
`comp_<database id>`). fmcareer reads only the images a report needs and embeds them,
scaled down, in the HTML. Nothing from the game is stored in this repository.

## How it works out the history

- **Clubs managed**: every spell the save's manager history keeps (`Save.manager_spells`:
  ended spells with dates and results, plus the current job).
- **League tables**: past tables come from the save's league history. fmsave works out
  which club each table row belongs to from fixtures, uid order and each club's
  league-by-season record in player history.
- **League levels**: worked out from how clubs move between leagues (finishing high in
  one league and appearing in another the next season), so the pyramid works for any
  country without a built-in table.
- **Squads**: every player's season statistics, including retired players whose full
  record the save still keeps. For players the game has cut down to a name, only the
  season's best-18 line (appearances, goals, rating) survives; those rows are marked
  *Partial*.
- **Transfer fees**: from each player's statistics history, plus the human manager's
  event log.

## Tests

```sh
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

The tests use a small made-up career, so they need no save or game install. The page
tests run the report in headless Chromium and check that every page draws. They are
skipped when no Chromium is found; set `FMCAREER_CHROME` to point at one.

## Limits

- **Spells from before the save's history began** (for example a real manager's jobs
  before the game started) are not stored, so they don't appear.
- Seasons are July–June. A spell that started mid-season counts that whole season.
- The event log (fees, notable matches) exists only for human managers.
- Checked against one long career save so far. Reports from other saves are welcome.
