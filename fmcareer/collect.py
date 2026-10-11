"""Collect a manager's career history from a save into one JSON-ready dict.

Every value comes from fmsave decoders plus joins between them; names come from
the competition/award CSVs fmcareer-names builds from the game install. Nothing
here is specific to one save: the manager is found by name, his clubs from what the
save keeps about his spells, and league levels are inferred from how clubs move
between competitions.
"""

import collections
import csv
import datetime as dt
import os
import unicodedata
import warnings

import fmsave

warnings.simplefilter("ignore")

CUP_METHOD = {1: "", 2: "after extra time", 3: "on penalties", 7: "over two legs"}
MOVE_TYPE = {
    1: "Transfer",
    3: "Loan",
    4: "Free",
    5: "Signing",
    6: "Staff joined",
    7: "Trial",
    9: "Staff left",
    14: "Youth intake",
    24: "Released",
    37: "Retired",
}
STAFF_TYPES = {6, 9}
PLACING = {0: "Winner", 1: "Runner-up", 2: "Third"}


def season_label(end_year):
    return f"{end_year - 1}/{str(end_year)[2:]}"


def season_end_of(day):
    """The ending year of the (July-June) season a date falls in."""
    return day.year + 1 if day.month >= 7 else day.year


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).casefold().split())


def find_manager(s, manager_name):
    """The staff member the name means: full, first+last or common name, accents ignored.

    Several matches prefer the human manager, then whoever has a managerial record.
    """
    want = _norm(manager_name)
    found = []
    for x in s.staff():
        names = {
            _norm(x.name),
            _norm(x.full_name),
            _norm(x.common_name),
            _norm(f"{x.first_name or ''} {x.last_name or ''}"),
        }
        if want in names:
            found.append(x)
    if not found:
        raise SystemExit(f"no staff member called {manager_name!r} in this save")
    if len(found) > 1:
        humans = [x for x in found if x.is_human_manager]
        managers = [x for x in found if s.manager_career(x.uid) is not None]
        found = humans or managers or found
    if len(found) > 1:
        listing = ", ".join(f"{x.name} ({x.club_name}, uid {x.uid})" for x in found)
        raise SystemExit(f"{manager_name!r} matches several people: {listing}")
    return found[0]


def manager_stints(s, me, record, events, club_by_team, game_date):
    """The manager's club spells, oldest first: [{club_uid, start, end}] (end None = current).

    `Save.manager_spells` (every ended spell from the save's manager history, plus the
    current job) when this fmsave has it; otherwise, merged per club, the career record's
    longest/shortest club windows, the event log's team stamps and the managed club.
    National-team spells are left out. Back-to-back spells at one club are joined.
    """
    stints = []
    if hasattr(s, "manager_spells"):
        for sp in s.manager_spells(me.uid):
            club_uid = club_by_team.get(sp.team_id)
            if club_uid is None:  # a national team, or a team the save does not name
                continue
            if (
                stints
                and stints[-1]["club_uid"] == club_uid
                and stints[-1]["end"] is not None
                and (sp.start_date is None or (sp.start_date - stints[-1]["end"]).days <= 1)
            ):
                stints[-1]["end"] = sp.end_date
                continue
            stints.append(dict(club_uid=club_uid, start=sp.start_date, end=sp.end_date))
        if stints:
            return stints

    spans = collections.defaultdict(lambda: [None, None])

    def add(club_uid, start, end):
        if club_uid is None:
            return
        span = spans[club_uid]
        if start and (span[0] is None or start < span[0]):
            span[0] = start
        if end and (span[1] is None or end > span[1]):
            span[1] = end

    if record is not None:
        for w in (record.longest_club_spell, record.shortest_club_spell):
            if w is not None:
                add(club_by_team.get(w.team_id), w.start_date, w.end_date)
    for e in events:
        if e.team_id is not None and e.event_date:
            add(club_by_team.get(e.team_id), e.event_date, e.event_date)
    managed = {m.manager_staff_uid: m.club_uid for m in s.managed_clubs()}
    current = managed.get(me.uid)
    if current is not None:
        add(current, None, game_date)
    for club_uid, (start, end) in spans.items():
        is_current = club_uid == current or (end is not None and game_date and end >= game_date)
        stints.append(dict(club_uid=club_uid, start=start, end=None if is_current else end))
    stints.sort(key=lambda x: x["start"] or dt.date.max)
    return stints


def league_levels(rows):
    """Level of every competition, inferred from clubs moving between competitions.

    A club finishing in the top third of X and playing Y the next season says Y is
    above X; the bottom third says below. Pairs keep the direction most moves agree
    on; a competition's level is one more than the deepest competition above it.
    Parallel divisions (two leagues feeding the same one) share a level.
    """
    by_list = collections.defaultdict(dict)
    for r in rows:
        if r.history_index is not None and r.games_played != 255:
            by_list[r.history_index][r.season_year] = (r.competition_id, r.position, r.total_teams)
    votes = collections.Counter()
    for seasons in by_list.values():
        for year, (comp, pos, teams) in seasons.items():
            nxt = seasons.get(year + 1)
            if not nxt or nxt[0] == comp or not teams:
                continue
            if pos < teams / 3:
                votes[(nxt[0], comp)] += 1  # next competition is above
            elif pos >= 2 * teams / 3:
                votes[(comp, nxt[0])] += 1  # this competition is above
    above = collections.defaultdict(set)
    for (hi, lo), n in votes.items():
        if n >= 2 and n > votes.get((lo, hi), 0):
            above[lo].add(hi)
    level = {}

    def depth(comp, seen=()):
        if comp in level:
            return level[comp]
        if comp in seen:  # a cycle the votes did not settle
            return 1
        ups = above.get(comp, ())
        level[comp] = 1 + max((depth(u, (*seen, comp)) for u in ups), default=0)
        return level[comp]

    comps = {r.competition_id for r in rows}
    return {c: depth(c) for c in comps}, above


def pyramid_of(above, start):
    """The competitions linked to `start` by club movement: one nation's pyramid."""
    links = collections.defaultdict(set)
    for lo, his in above.items():
        for hi in his:
            links[lo].add(hi)
            links[hi].add(lo)
    seen, todo = set(start), list(start)
    while todo:
        for nxt in links[todo.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


DEFAULT_OPTIONS = {
    # report pages, in nav order
    "sections": ["me", "seasons", "players", "records", "honours", "transfers", "club"],
    # which kinds of move transfer lists show at first (viewers can toggle them)
    "show": {"Loan": False, "Trial": False, "Youth intake": False, "Released": True, "staff": False},
}


def read_names(names_dir):
    """Competition and award names from fmcareer-names CSVs; empty maps when absent."""
    db_names, award_names, comp_csv = {}, {}, None
    if names_dir:
        path = os.path.join(names_dir, "competition_names.csv")
        if os.path.exists(path):
            comp_csv = path
            with open(path, encoding="utf-8") as f:
                db_names = {int(r[0]): r[1] for r in csv.reader(f)}
        path = os.path.join(names_dir, "award_names.csv")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                award_names = {int(r["award_index"]): r["name"] for r in csv.DictReader(f)}
    return db_names, award_names, comp_csv


def open_save(save_path, names_dir=None):
    """Open a save with the competition names hooked in when they exist."""
    _db, _aw, comp_csv = read_names(names_dir)
    return fmsave.open(save_path, competition_names=comp_csv) if comp_csv else fmsave.open(save_path)


def manager_steps(everyone):
    """How many progress steps list_managers reports."""
    return 3 if everyone else 1


def list_managers(s, progress=lambda text: None, everyone=False):
    """Managers to report on: the save's human managers, or with `everyone` every current
    staff member with a managerial record (human managers first, then by games).

    [{staff_uid, name, club, games, wins, draws, losses, club_jobs, human}]
    """
    progress("Reading staff")
    staff = list(s.staff())
    found = {}
    for x in staff:  # human managers: their record joins by reference
        if x.is_human_manager:
            rec = s.manager_career(x.uid)
            if rec is not None:
                found[x.uid] = (x, rec)
    if everyone:
        progress("Reading managerial records")
        records = {r.reference: r for r in s.career_manager_records()}
        progress("Reading people")
        people = {h.reference: h for h in s.history_people()}
        by_unique = {x.unique_id: x for x in staff if x.unique_id}
        for ref, rec in records.items():
            h = people.get(ref)
            x = by_unique.get(h.unique_id) if h else None
            if x is not None and x.uid not in found:
                found[x.uid] = (x, rec)
    out = [
        dict(
            staff_uid=x.uid,
            name=x.name,
            club=x.club_name,
            games=rec.games,
            wins=rec.wins,
            draws=rec.draws,
            losses=rec.losses,
            club_jobs=rec.club_jobs,
            human=x.is_human_manager,
        )
        for x, rec in found.values()
        if x.name and rec.games
    ]
    out.sort(key=lambda m: (not m["human"], -m["games"], m["name"]))
    return out


COLLECT_STEPS = 7  # progress steps collect reports; tests check this against the code
SIGNING_TYPES = ("Transfer", "Free", "Signing")


def collect(save_path, manager_name, names_dir, *, staff_uid=None, save=None, options=None, progress=lambda text: None):
    """The whole career of one manager, as a JSON-ready dict.

    The manager is `staff_uid` when given, else found by `manager_name`. `save` reuses an
    already opened Save; `options` overrides DEFAULT_OPTIONS (sections, transfer toggles).
    """
    s = save if save is not None else open_save(save_path, names_dir)
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    opts["show"] = {**DEFAULT_OPTIONS["show"], **(options or {}).get("show", {})}
    progress("Finding the manager")
    c = Career(s, names_dir, manager_name, staff_uid)
    progress("Reading players and retired players")
    c.read_people()
    progress("Reading league history")
    league, tables, levels = league_section(c)
    progress("Reading honours, cups and awards")
    honours, cups, awards = honours_section(c)
    logged_fees, notable = event_log(c)
    progress("Reading transfers and fees")
    moves, mover_uids, gone_refs = transfers_section(c, logged_fees)
    progress("Reading player statistics")
    best_eleven, squad_stats = statistics_section(c, mover_uids, gone_refs)
    career = career_record(c)
    progress("Reading the club today")
    club_today = None
    if c.current is not None and c.current["club_uid"] in c.clubs:
        club_today = club_now(s, c.clubs, c.current["club_uid"], c.players, c.comp_name, c.comp_db)
    return dict(
        manager=c.manager_summary(),
        stints=[
            dict(
                club=st["club"],
                club_uid=st["club_uid"],
                start=st["start"].isoformat() if st["start"] else None,
                end=st["end"].isoformat() if st["end"] else None,
            )
            for st in c.stints
        ],
        tables=tables,
        career=career,
        squad_stats=squad_stats,
        notable_matches=notable,
        league=league,
        levels=levels,
        honours=honours,
        cups=cups,
        awards=awards,
        best_eleven=best_eleven,
        transfers=moves,
        players_bought=sum(1 for m in moves if m["kind"] == "signing"),
        squad=c.current_squad(),
        club_today=club_today if "club" in opts["sections"] else None,
        options=opts,
    )


class Career:
    """What every part of a career needs: the manager, his spells, and the save's lookups."""

    def __init__(self, s, names_dir, manager_name, staff_uid):
        self.s = s
        self.db_names, self.award_names, _csv = read_names(names_dir)
        self.game_date = s.info.game_date
        if staff_uid is not None:
            me = next((x for x in s.staff() if x.uid == staff_uid), None)
            if me is None:
                raise SystemExit(f"no staff member with uid {staff_uid}")
        else:
            me = find_manager(s, manager_name)
        self.me, self.staff_uid = me, me.uid
        self.manager_name = me.name or manager_name
        self.clubs = {c.uid: c for c in s.clubs()}
        self.club_by_team = {t.team_id: c.uid for c in self.clubs.values() for t in c.teams if not t.is_affiliate}
        self.teams = {t.team_id: c.name for c in self.clubs.values() for t in c.teams}
        comps = list(s.competitions())
        self.comp_name = {c.id: c.name for c in comps}
        self.comp_db = {c.id: c.database_id for c in comps}
        self.record = s.manager_career(self.staff_uid)
        self.manager_ref = s.history_person_reference(self.staff_uid)
        self.events = list(s.manager_events(self.staff_uid)) if me.is_human_manager else []
        self.stints = manager_stints(s, me, self.record, self.events, self.club_by_team, self.game_date)
        if not self.stints:
            raise SystemExit(f"{self.manager_name}: the save keeps no club spell for this manager")
        # an unknown start (a spell older than the save's history) counts from that history's start
        history_years = [r.season_year for r in s.career_league_history() if not r.imported]
        history_start = dt.date(min(history_years) - 1, 7, 1) if history_years else dt.date.min
        for st in self.stints:
            st["club"] = self.clubs[st["club_uid"]].name if st["club_uid"] in self.clubs else f"Club {st['club_uid']}"
            st["from"] = st["start"] or history_start
        self.current = next((st for st in self.stints if st["end"] is None), None)

    # ---- spells

    def stint_for(self, day):
        """The stint covering a date, else None."""
        for st in self.stints:
            if day >= st["from"] and (st["end"] is None or day <= st["end"]):
                return st
        return None

    def stint_for_season(self, end_year):
        """The club the manager had at the end of a season (or latest in it)."""
        last_day, first_day = dt.date(end_year, 6, 30), dt.date(end_year - 1, 7, 1)
        best = None
        for st in self.stints:
            if st["from"] <= last_day and (st["end"] or dt.date.max) >= first_day:
                best = st  # stints are oldest first: keep the latest overlapping
        return best

    def in_career(self, club_uid, end_year):
        st = self.stint_for_season(end_year)
        return st is not None and st["club_uid"] == club_uid

    # ---- people

    def read_people(self):
        """Names and photo ids: current players, then retired people found in game_db."""
        s = self.s
        self.players = {p.uid: p for p in s.players()}
        people = list(s.history_people())
        self.retired = {h.reference: h.name for h in people if h.name}
        self.retired_unique = {h.reference: h.unique_id for h in people}
        self.ref_to_uid = s.history_player_references()
        club = self.current["club_uid"] if self.current else None
        self.current_uids = {u for u, p in self.players.items() if club is not None and p.club_uid == club}

    def person_id(self, uid, ref):
        """The person's unique id, the key of his photo."""
        if uid is None:
            uid = self.ref_to_uid.get(ref)
        if uid in self.players:
            return self.players[uid].unique_id or uid + 1
        return self.retired_unique.get(ref)

    def person(self, uid, ref, fallback=None):
        if ref is not None and ref == self.manager_ref:
            return self.manager_name
        if uid is None:
            uid = self.ref_to_uid.get(ref)
        if uid in self.players:
            return self.players[uid].name
        return self.retired.get(ref) or fallback or f"Unknown player ({ref})"

    def current_squad(self):
        return sorted(
            (
                dict(name=p.name, age=p.age, person_id=p.unique_id or u + 1)
                for u, p in self.players.items()
                if u in self.current_uids
            ),
            key=lambda x: x["name"],
        )

    def manager_summary(self):
        me, current = self.me, self.current
        return dict(
            name=self.manager_name,
            club=current["club"] if current else None,
            spell_start=current["start"].year if current and current["start"] else None,
            game_date=self.game_date.isoformat() if self.game_date else "",
            birth_date=me.birth_date.isoformat() if me.birth_date else None,
            age=me.age,
            wage=me.wage if current else None,
            contract_start=me.contract_start.isoformat() if current and me.contract_start else None,
            contract_end=me.contract_end.isoformat() if current and me.contract_end else None,
            human=me.is_human_manager,
            person_id=me.unique_id or self.staff_uid + 1,
            nation_id=me.nation_id,
        )


def league_section(c):
    """The manager's league seasons, each season's final table, and the pyramid's levels.

    Each season carries what the report and the AI writer both say about it: champion,
    promoted / relegated (by the club's level the next season) and moved (a new club next).
    """
    s = c.s
    all_rows = [r for r in s.career_league_history() if not r.imported]
    level, above = league_levels(all_rows)
    league, club_lists = [], {}
    for st in c.stints:
        club_uid = st["club_uid"]
        history = list(s.club_league_history(club_uid))
        club_lists[club_uid] = next((r.history_index for r in history), None)
        for r in history:
            if r.imported or r.games_played == 255 or not c.in_career(club_uid, r.season_year):
                continue
            league.append(
                dict(
                    season=season_label(r.season_year),
                    end_year=r.season_year,
                    club=st["club"],
                    club_uid=club_uid,
                    competition=c.comp_name.get(r.competition_id) or f"Competition {r.competition_id}",
                    competition_id=r.competition_id,
                    competition_db=c.comp_db.get(r.competition_id),
                    tier=level.get(r.competition_id),
                    position=r.position + 1,
                    teams=r.total_teams,
                    played=r.games_played,
                    won=r.wins,
                    drawn=r.draws,
                    lost=r.losses,
                    goals_for=r.goals_for,
                    goals_against=r.goals_against,
                    points=r.points,
                )
            )
    league.sort(key=lambda r: r["end_year"])
    for i, r in enumerate(league):
        nxt = league[i + 1] if i + 1 < len(league) else None
        same = nxt is not None and nxt["club_uid"] == r["club_uid"]
        r["champion"] = r["position"] == 1
        r["promoted"] = bool(same and nxt["tier"] and r["tier"] and nxt["tier"] < r["tier"])
        r["relegated"] = bool(same and nxt["tier"] and r["tier"] and nxt["tier"] > r["tier"])
        r["moved"] = bool(nxt and not same)
    # level sizes within the pyramid of the manager's latest league, then each row's overall rank
    home = pyramid_of(above, {league[-1]["competition_id"]}) if league else set()
    level_size = collections.defaultdict(int)
    for r in all_rows:
        if r.games_played != 255 and r.competition_id in home:
            lv = level.get(r.competition_id)
            level_size[lv] = max(level_size[lv], r.total_teams)
    for lr in league:
        lv = lr["tier"]
        lr["rank"] = sum(level_size[x] for x in range(1, lv)) + lr["position"] if lv else None
    tables = {}
    for lr in league:
        rows = [
            r
            for r in s.league_history_table(lr["end_year"], lr["competition_id"])
            if not r.imported and r.games_played != 255
        ]
        mine = club_lists.get(lr["club_uid"])
        tables[lr["season"]] = [
            dict(
                position=r.position + 1,
                club=r.club_name,
                club_uid=r.club_uid,
                me=r.history_index == mine,
                played=r.games_played,
                won=r.wins,
                drawn=r.draws,
                lost=r.losses,
                goals_for=r.goals_for,
                goals_against=r.goals_against,
                points=r.points,
            )
            for r in sorted(rows, key=lambda r: r.position)
        ]
    # the levels down to the manager's lowest league, named for the chart's bands
    deepest = max((r["tier"] for r in league if r["tier"]), default=0)
    levels = []
    for lv in range(1, deepest + 1):
        names = collections.Counter(r["competition"] for r in league if r["tier"] == lv)
        if not names:  # a level the manager never played: the competitions the save puts there
            names = collections.Counter(
                c.comp_name.get(x) for x, n in level.items() if n == lv and x in home and c.comp_name.get(x)
            )
        levels.append(dict(level=lv, name=names.most_common(1)[0][0] if names else f"Level {lv}", size=level_size[lv]))
    return league, tables, levels


def honours_section(c):
    """Trophies, every cup run and the manager's awards."""
    s, clubs = c.s, c.clubs
    honours = [
        dict(
            season=season_label(h.season),
            end_year=h.season,
            club=clubs[h.club_uid].name,
            competition_db=h.competition_id,
            name=c.db_names.get(h.competition_id, f"Competition {h.competition_id}"),
        )
        for h in sorted(s.career_honours(), key=lambda h: h.season)
        if h.club_uid in clubs and c.in_career(h.club_uid, h.season)
    ]
    cups = []
    for st in c.stints:
        for cup in s.club_cup_history(st["club_uid"]):
            if not c.in_career(st["club_uid"], cup.end_year):
                continue
            name = c.comp_name.get(cup.competition_id) or f"Stage {cup.stage_id}"
            cups.append(
                dict(
                    season=season_label(cup.end_year),
                    end_year=cup.end_year,
                    club=st["club"],
                    competition_db=c.comp_db.get(cup.competition_id),
                    opponent_uid=c.club_by_team.get(cup.opponent_team_id),
                    competition=name,
                    youth=any(w in name for w in ("U18", "U19", "U21", "U23")),
                    won=cup.result == 3,
                    league_stage=cup.result == 0 and cup.opponent_team_id is None,
                    position=cup.position,
                    opponent=c.teams.get(cup.opponent_team_id),
                    method=CUP_METHOD.get(cup.method, ""),
                )
            )
    awards = [
        dict(
            season=season_label(a.season_year),
            end_year=a.season_year,
            name=c.award_names.get(a.award_id, f"Award {a.award_id}"),
            placing=PLACING.get(a.placing, str(a.placing)),
            age=a.winner_age,
            club=clubs[a.club_uid].name if a.club_uid in clubs else None,
        )
        for a in sorted(s.career_awards(), key=lambda a: (a.season_year, a.placing))
        if c.manager_ref is not None and a.winner_id == c.manager_ref
    ]
    return honours, cups, awards


def event_log(c):
    """From a human manager's event log: the fees it logged, and the notable matches."""
    logged_fees = {}
    for e in c.events:
        if e.event_type == 2 and e.fee and e.player_reference is not None:
            logged_fees.setdefault((e.player_reference, e.from_team_id, e.to_team_id), []).append(
                (e.effective_date or e.event_date, e.fee)
            )
    notable = []
    for e in c.events:
        if e.event_type == 8 and e.goals_for is not None and e.event_date:
            notable.append(
                dict(
                    date=e.event_date.isoformat(),
                    season=season_label(season_end_of(e.event_date)),
                    opponent=c.teams.get(e.opponent_team_id),
                    goals_for=e.goals_for,
                    goals_against=e.goals_against,
                    competition=c.comp_name.get(e.competition_id) if e.competition_id is not None else None,
                )
            )
    notable.sort(key=lambda x: x["date"])
    return logged_fees, notable


def move_kind(direction, move_type, other):
    """What a move counts as in totals and summaries: a signing, a sale, a free departure
    to another club, or None (loans, trials, releases, staff and the like)."""
    if direction == "in":
        return "signing" if move_type in SIGNING_TYPES else None
    if move_type == "Transfer":
        return "sale"
    if move_type == "Free" and other:
        return "free_departure"
    return None


def transfers_section(c, logged_fees):
    """Every move in and out during the manager's spells, with fees, plus who moved
    (current player uids and the references of people who are gone) for the statistics."""
    s, players = c.s, c.players
    moves, mover_uids, gone_refs = [], set(), set()
    for st in c.stints:
        club_uid = st["club_uid"]
        club_moves = list(s.club_player_moves(club_uid, fees=True))
        for m in club_moves:
            if not m.date or c.stint_for(m.date) is not st:
                continue
            end = season_end_of(m.date)
            move_type = MOVE_TYPE.get(m.record_type, f"Type {m.record_type}")
            other = m.from_club_name if m.direction == "in" else m.to_club_name
            staff = m.record_type in STAFF_TYPES
            moves.append(
                dict(
                    date=m.date.isoformat(),
                    season=season_label(end),
                    end_year=end,
                    club=st["club"],
                    direction=m.direction,
                    type=move_type,
                    staff=staff,
                    kind=None if staff else move_kind(m.direction, move_type, other),
                    fee=m.fee if m.fee else None,
                    _key=(m.player_reference, m.from_team_id, m.to_team_id),
                    player=c.person(m.player_uid, m.player_reference, m.player_name),
                    person_id=None if staff else c.person_id(m.player_uid, m.player_reference),
                    other=other,
                    other_uid=(m.from_club_uid if m.direction == "in" else m.to_club_uid),
                )
            )
        mover_uids |= {m.player_uid for m in club_moves if m.player_uid}
        mover_uids |= {u for u, p in players.items() if p.club_uid == club_uid}
        gone_refs |= {m.player_reference for m in club_moves if m.player_uid is None and m.player_reference}
    for key, logged in logged_fees.items():  # each logged fee goes to the closest unpriced move
        for when, amount in logged:
            if any(m["_key"] == key and m["fee"] == amount for m in moves):
                continue
            cands = [m for m in moves if m["_key"] == key and m["fee"] is None]
            if cands and when:
                min(cands, key=lambda m: abs((dt.date.fromisoformat(m["date"]) - when).days))["fee"] = amount
    for m in moves:
        m.pop("_key")
        if m["staff"] and m["player"].startswith("Unknown player"):
            m["player"] = "Staff member"
    moves.sort(key=lambda m: m["date"])
    return moves, mover_uids, gone_refs


def statistics_section(c, mover_uids, gone_refs):
    """Each season's best eleven and full squad statistics at the manager's clubs."""
    s, clubs = c.s, c.clubs
    history_rows = list(s.player_season_history(sorted(mover_uids)))
    history_rows += list(s.history_person_season_history(sorted(gone_refs)))
    team_club = {
        t.team_id: st["club_uid"]
        for st in c.stints
        if st["club_uid"] in clubs
        for t in clubs[st["club_uid"]].teams
        if t.slot == 0
    }
    best_eleven = _best_eleven(c, history_rows, team_club)
    squad_stats = _squad_stats(c, history_rows, team_club)
    # players whose stats rows are gone (retired, cut to a stub) still have their best-eleven line
    for season, xi in best_eleven.items():
        have = {p["name"] for p in squad_stats.get(season, [])}
        extra = [
            dict(
                name=b["name"],
                current=b["current"],
                apps=b["apps"],
                goals=b["goals"],
                rating=b["rating"],
                person_id=b["person_id"],
                starts=None,
                subs=None,
                assists=None,
                minutes=None,
                pom=None,
                yellow=None,
                red=None,
                partial=True,
            )
            for b in xi
            if b["name"] not in have and b["apps"]
        ]
        if extra:
            squad_stats[season] = sorted(squad_stats.get(season, []) + extra, key=lambda x: (-x["apps"], x["name"]))
    return best_eleven, squad_stats


def _best_eleven(c, history_rows, team_club):
    """Best eleven: the save's list whose players had rows at the club's first team."""
    by_list = collections.defaultdict(list)
    for r in c.s.career_best_eleven():
        by_list[r.history_index].append(r)
    at_club = collections.defaultdict(set)  # club uid -> {(reference, season start)}
    for r in history_rows:
        club = team_club.get(r.team_id)
        if club is not None:
            at_club[club].add((r.player_reference, r.season_year))
    best_eleven = {}
    for club_uid, seen in at_club.items():
        score = {
            idx: sum(1 for r in rows if (r.player_reference, r.season_year) in seen) for idx, rows in by_list.items()
        }
        idx = max(score, key=score.get, default=None)
        if idx is None or score[idx] < 6:
            continue
        for r in by_list[idx]:
            end_year = r.season_year + 1  # best-eleven years are season start years
            if not c.in_career(club_uid, end_year):
                continue
            best_eleven.setdefault(season_label(end_year), []).append(
                dict(
                    slot=r.slot,
                    name=c.person(r.player_uid, r.player_reference, r.player_name),
                    person_id=c.person_id(r.player_uid, r.player_reference),
                    current=r.player_uid in c.current_uids,
                    apps=r.appearances,
                    goals=r.goals,
                    rating=round(r.average_rating, 2) if r.average_rating else None,
                )
            )
    for rows in best_eleven.values():
        rows.sort(key=lambda x: x["slot"])
    return best_eleven


def _squad_stats(c, history_rows, team_club):
    """Full squad statistics per season: competitive rows for the club's first team."""
    squads = collections.defaultdict(dict)
    seen_rows = set()
    for r in history_rows:
        club = team_club.get(r.team_id)
        if club is None or r.kind_code not in (1, 2, 3) or not c.in_career(club, r.season_year + 1):
            continue
        who = r.player_uid if r.player_uid is not None else ("ref", r.player_reference)
        key = (who, r.season_year, r.team_id, r.kind, r.minutes, r.goals, r.rated_appearances, r.rating_total)
        if key in seen_rows:  # the section stores some rows twice
            continue
        seen_rows.add(key)
        p = squads[season_label(r.season_year + 1)].setdefault(
            who,
            dict(
                name=c.person(r.player_uid, r.player_reference),
                current=r.player_uid in c.current_uids,
                person_id=c.person_id(r.player_uid, r.player_reference),
                apps=0,
                starts=0,
                subs=0,
                goals=0,
                assists=0,
                minutes=0,
                rating_total=0,
                pom=0,
                yellow=0,
                red=0,
            ),
        )
        p["apps"] += r.rated_appearances or 0
        p["starts"] += r.starts or 0
        p["subs"] += r.substitute_appearances or 0
        p["goals"] += r.goals or 0
        p["assists"] += r.assists or 0
        p["minutes"] += r.minutes or 0
        p["rating_total"] += r.rating_total or 0
        p["pom"] += r.player_of_the_match or 0
        p["yellow"] += r.yellow_cards or 0
        p["red"] += r.red_cards or 0
    squad_stats = {}
    for season, players in squads.items():
        for p in players.values():
            p["rating"] = round(p.pop("rating_total") / p["apps"] / 10, 2) if p["apps"] else None
        squad_stats[season] = sorted(
            (p for p in players.values() if p["apps"] > 0), key=lambda x: (-x["apps"], x["name"])
        )
    return squad_stats


def career_record(c):
    """The game's own managerial record (games, money, record signing and sale), or None."""
    record = c.record
    if record is None:
        return None

    def fee(f):
        if f is None:
            return None
        return dict(
            player=c.person(None, f.player_reference),
            fee=f.fee,
            person_id=c.person_id(None, f.player_reference),
            date=f.transfer_date.isoformat() if f.transfer_date else None,
            from_club=c.teams.get(f.from_team_id),
            to_club=c.teams.get(f.to_team_id),
        )

    return dict(
        games=record.games,
        wins=record.wins,
        draws=record.draws,
        losses=record.losses,
        goals_for=record.goals_for,
        goals_against=record.goals_against,
        league_titles=record.league_titles,
        cups=record.cups,
        awards=record.awards,
        players_bought=record.players_bought,
        players_sold=record.players_sold,
        players_released=record.players_released,
        money_spent=record.money_spent,
        agent_fees=record.agent_fees,
        club_jobs=record.club_jobs,
        record_signing=fee(record.highest_fee_paid),
        record_sale=fee(record.highest_fee_received),
    )


def _label(coded):
    """A CodedValue's label as words, or None for an unknown code."""
    if coded is None:
        return None
    label = getattr(coded, "label", None)
    if label is None or getattr(label, "value", 0) == -1:
        return None
    return label.name.replace("_", " ").capitalize()


def club_now(s, clubs, club_uid, players, comp_name, comp_db):
    """The current club as the save has it today: ground, money, tactics, squad, table."""
    club = clubs[club_uid]
    team_ids = {t.team_id for t in club.teams if not t.is_affiliate}
    first_team = next((t.team_id for t in club.teams if t.slot == 0), None)
    club_by_team = {t.team_id: c.uid for c in clubs.values() for t in c.teams if not t.is_affiliate}

    stadium = next((x for x in s.stadiums() if club_uid in (x.home_club_uids or ())), None)
    months = sorted((f for f in s.finances() if f.club_uid == club_uid), key=lambda f: f.month)
    latest = months[-1] if months else None
    sponsors = [x for x in s.sponsorships() if x.club_uid == club_uid]
    facilities = next((x for x in s.facilities() if x.club_uid == club_uid), None)
    tactics = [
        dict(name=x.name, style=x.style_name, mentality=_label(x.mentality))
        for x in s.tactics()
        if x.club_uid == club_uid and x.team_id == first_team
    ]
    contracts = {c.player_uid: c for c in s.contracts() if c.club_uid == club_uid}
    squad = []
    for uid, p in players.items():
        if p.club_uid != club_uid:
            continue
        c = contracts.get(uid)
        squad.append(
            dict(
                name=p.name,
                person_id=p.unique_id or uid + 1,
                age=p.age,
                positions=" ".join(str(x) for x in (p.natural_positions or ())) or None,
                ability=p.ability.current if p.ability else None,
                potential=p.ability.potential if p.ability else None,
                value=p.transfer_value,
                wage=c.wage if c else None,
                contract_end=c.end.isoformat() if c and c.end else None,
                status=_label(c.squad_status) if c else None,
                joined=p.club_join_date.isoformat() if p.club_join_date else None,
                on_loan=bool(p.on_loan),
                first_team=p.team_id == first_team,
            )
        )
    squad.sort(key=lambda x: (not x["first_team"], -(x["ability"] or 0)))
    # the live table of the league the first team plays in
    table = None
    for lt in s.league_tables():
        if any(r.team_id == first_team for r in lt.rows) and (table is None or lt.club_count > table.club_count):
            table = lt
    live = None
    if table is not None:
        live = dict(
            competition=comp_name.get(table.competition_id) or table.competition_name,
            competition_db=comp_db.get(table.competition_id),
            rows=[
                dict(
                    position=r.position,
                    club_uid=club_by_team.get(r.team_id),
                    club=clubs[club_by_team[r.team_id]].name if r.team_id in club_by_team else None,
                    me=r.team_id in team_ids,
                    played=r.played,
                    won=r.won,
                    drawn=r.drawn,
                    lost=r.lost,
                    goals_for=r.goals_for,
                    goals_against=r.goals_against,
                    points=r.points,
                )
                for r in sorted(table.rows, key=lambda r: r.position)
            ],
        )
    affiliates = sorted(
        {
            name
            for g in s.affiliates()
            if club_uid in g.club_uids
            for uid, name in zip(g.club_uids, g.club_names, strict=False)
            if uid != club_uid
        }
    )
    return dict(
        club=club.name,
        club_uid=club_uid,
        stadium=dict(
            name=stadium.name,
            capacity=stadium.all_seater_capacity,
            built=stadium.built_date.year if stadium.built_date else None,
        )
        if stadium
        else None,
        finances=dict(
            month=latest.month.isoformat(),
            balance=latest.balance,
            transfer_budget=latest.transfer_budget_allocated,
            transfer_left=latest.transfer_budget_remaining,
            wage_budget=latest.wage_budget_weekly,
            wage_payroll=latest.wage_payroll_weekly,
        )
        if latest
        else None,
        balance_history=[
            dict(month=f.month.isoformat(), balance=f.balance, income=f.total_income, spend=f.total_expenditure)
            for f in months
        ],
        sponsors=dict(count=len(sponsors), annual=sum(x.annual_value or 0 for x in sponsors)),
        corporate_facilities=_label(facilities.corporate_facilities) if facilities else None,
        tactics=tactics,
        squad=squad,
        live_table=live,
        affiliates=affiliates,
        staff=sum(1 for x in s.staff() if x.club_uid == club_uid),
    )
