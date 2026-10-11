# fmcareer

A manager's career history from a Football Manager 26 save: point it at a save and a
manager's name, and it builds one self-contained HTML page with:

- **Report**: a feature on the whole career with a timeline, then an article per season.
- **Career overview**: profile, league record, the game's own managerial stats (games,
  money spent, record signing and sale), the climb through the league pyramid, trophy
  cabinet, manager awards and the club legends of the era.
- **A review of every season**: written summary, the final league table, cup runs,
  honours and awards, full squad statistics, the season's best 18, transfers with fees
  and notable results.
- **Players** and **Records**: everyone who played under the manager, with a page per
  player, and the best and biggest of the era.
- **Honours & cups**, **Transfers** and **Club today** (finances, squad, tactics and the
  live league table).

A Report page tells the career as newspaper articles, written from the data or optionally by an AI model you choose.
Club badges, faces and competition logos come from the game and from any logo or face
packs you've installed.

Everything is read from the save itself through our fork of
[fmsave](https://github.com/karl0ss/fmsave) (branch `history-decoders`, which adds the
history decoders this tool needs), pinned to a commit in `pyproject.toml`. Nothing is scraped from screenshots or the game UI.

## Download (Windows)

Get `fmcareer-<version>-windows.exe` from the
[latest release](https://github.com/karl0ss/fmcareer/releases/latest) and double-click it.
The app opens in your browser; leave the black window open while you use it and close it
to stop. Nothing to install. Windows may warn about an unrecognised app the first time
(the exe isn't code-signed): choose "More info", then "Run anyway".

Reports are single HTML files with their images inside, so they open in any browser,
offline, and can be kept, copied or sent on. The app has a Download link for each.

## Install with Python (any system)

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

1. set your saves folder, FM26 install folder and graphics folder (it finds the usual
   Steam and Documents locations, and the graphics folder next to the saves) and read
   the competition/award names from the game once;
2. pick a save;
3. load its managers and pick one: the save's human managers (tick "Show all managers"
   for every manager in the save, searchable by name or club);
4. tick the pages to include, which kinds of move the transfer lists show at first
   (loans, trials, youth intake, released players, staff), and whether to embed images;
5. set options, for now AI-written articles for the Report page (below);
6. generate: a progress bar counts the steps, and the report opens in a new tab with a
   Download link beside it. Reports are kept in `~/.cache/fmcareer/reports`.

The Windows exe is this same app. On Windows `~` is your user folder
(`C:\Users\<you>`), so settings are in `C:\Users\<you>\.config\fmcareer` and reports in
`C:\Users\<you>\.cache\fmcareer\reports`.

Settings live in `~/.config/fmcareer/settings.json`. What the app reads from a save
(its managers, each manager's career, and badges and photos from the install) is kept in
`~/.cache/fmcareer/data`, so the same save opens in a moment next time, even after a
restart, and changing pages or toggles never rereads it. A save that has changed, new
names files or a new fmcareer/fmsave are read afresh; tick "Read the save again" to force it.

## Command line

```sh
.venv/bin/fmcareer "/path/to/My Career.fm" "Manager Name" names -o career_report.html
```

- The manager is matched by full, first + last, or common name, ignoring case and
  accents. Any manager in the save works, not only the human one.
- `--install "/path/to/Football Manager 26"` embeds club badges, real players' photos
  and competition logos from your own install, and `--graphics "/path/to/graphics"` adds
  your logo and face packs (they win over the game's images). Both need the images extra:
  `pip install "fmcareer[images] @ git+https://github.com/karl0ss/fmcareer.git"`. Clubs and
  people with no picture anywhere get a lettered crest or no photo.
- `--sections me,seasons,players,records,honours,transfers,club` picks the pages (default:
  all). `--show loans,trials,youth,released,staff` picks which kinds of move the transfer
  lists show at first (default: released); viewers can switch them in the report.
- `--json career_data.json` also writes the collected data.
- AI-written articles are set up in the app; the command line uses the report's own.
- A large save takes a few minutes and about 3 GB of memory.

## The Report page and AI-written articles (optional)

The Report page reads like a newspaper: it opens with a feature on the manager's whole
career and a timeline of every season, then one article per season, read in order with
previous and next (each season's review also opens with its article). The report writes
these articles itself from the data. Under "AI writing" in the app's Options step you can
have a language model write them instead, as news reports: tick the box, give an
OpenAI-compatible endpoint (OpenAI, llama.cpp/llama-swap, Ollama, LM Studio, vLLM: usually
ending in `/v1`), a token if it needs one and a model, and press Test.

The model is given only facts from the career and told to use nothing else; any number in
its text that the facts don't hold gets the piece asked again, then the report's own
article is used. A piece the model gives no usable text for keeps the report's own and the
rest carry on; if the endpoint fails, or the model manages none of the first two pieces,
the report keeps its own articles, and the app says how many the model wrote. Reasoning
models are asked to think briefly (`reasoning_effort: low`, dropped for endpoints that
refuse it). Articles already written for the same facts and model are reused, so
regenerating is quick. Readers can switch between the AI-written and the report's own
articles. The facts, including names from your save, are sent to the endpoint you choose;
the token stays in your local settings and is never shown again. The Career overview and
the rest of the report always use the report's own text.

## Images

The game keeps its licensed artwork in Unity asset bundles; the address catalog next to
them names each image by the save's own ids (`club_<club uid>`, `person_<unique id>`,
`comp_<database id>`). fmcareer reads only the images a report needs and embeds them,
scaled down, in the HTML. Nothing from the game is stored in this repository.

The game only has artwork for licensed clubs and people. Logo and face packs you've
added to the game's `graphics` folder (next to `games`, where the saves are) are used
too, and win over the game's own images, as they do in the game. The app finds that
folder by itself; on the command line pass `--graphics`. Packs that map their pictures
with a `config.xml` (face packs, generated-player faces) and packs that name pictures by
id (logo megapacks: `logos/Clubs/Normal/Normal/716.png`) both work; alternative and
retro badge sets and small sizes are skipped.

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

## Releases

The version lives in `fmcareer/__init__.py`. To publish one, bump it, commit, then tag:

```sh
git tag v0.0.6 && git push origin v0.0.6
```

GitHub Actions runs the tests, builds the exe on Windows with PyInstaller
(`packaging/build.py`), checks that it starts and serves the app, and attaches it to a
release. A local build: `pip install ".[images,build]"` then `python packaging/build.py`.

## Tests

```sh
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pyright
```

The tests use a small made-up career, so they need no save or game install. The page
tests run the report in headless Chromium and check that every page draws. They are
skipped when no Chromium is found; set `FMCAREER_CHROME` to point at one.

## Limits

- **Spells from before the save's history began** (for example a real manager's jobs
  before the game started) are not stored, so they don't appear.
- Seasons are July–June. A spell that started mid-season counts that whole season.
- The event log (fees, notable matches) exists only for human managers.
- Faces: the game draws its own faces for people without a photo (most generated
  players, and your manager) and doesn't keep them as pictures, so those show no face
  unless a face pack covers them. A manager with no face shows the club's badge.
- AI articles are only as good as the model; the number check catches invented
  figures, not every wrong word, and readers can always switch to the report's own articles.
- Checked against one long career save so far. Reports from other saves are welcome.
