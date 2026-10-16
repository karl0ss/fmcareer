"""The pure parts of collect: league levels, club spells, manager lookup, names, helpers."""

import datetime as dt
import inspect
import re
from types import SimpleNamespace as NS

import pytest

from fmcareer.collect import (
    CAREER_TOTALS,
    COLLECT_STEPS,
    _live_squad_stats,
    _norm,
    career_record,
    club_colours,
    club_tint,
    collect,
    countries,
    find_manager,
    league_levels,
    list_managers,
    manager_steps,
    manager_stints,
    mark_seasons,
    move_kind,
    name_levels,
    pyramid_of,
    read_names,
    report_gaps,
    running_sponsors,
    season_end_of,
    season_label,
    team_competitions,
    team_names,
)


def row(index, year, comp, position, teams=20, played=38):
    return NS(
        history_index=index,
        season_year=year,
        competition_id=comp,
        position=position,
        total_teams=teams,
        games_played=played,
    )


def test_season_helpers():
    assert season_label(2025) == "2024/25"
    assert season_end_of(dt.date(2024, 7, 1)) == 2025
    assert season_end_of(dt.date(2025, 6, 30)) == 2025


def test_norm_ignores_case_accents_and_spacing():
    assert _norm("  Uroš   KOREN ") == "uros koren"
    assert _norm(None) == ""


# A three-level pyramid (A over B over C) plus a parallel division C2 beside C.
# Clubs finishing in the top third go up next season, the bottom third go down.
PYRAMID = [
    row(1, 2030, "B", 0),
    row(1, 2031, "A", 10),  # B champion promoted to A
    row(2, 2030, "B", 1),
    row(2, 2031, "A", 12),
    row(3, 2030, "A", 19),
    row(3, 2031, "B", 5),  # A relegated to B
    row(4, 2030, "A", 18),
    row(4, 2031, "B", 8),
    row(5, 2030, "C", 0),
    row(5, 2031, "B", 3),  # C champion promoted
    row(6, 2030, "C", 1),
    row(6, 2031, "B", 9),
    row(7, 2030, "C2", 0),
    row(7, 2031, "B", 4),  # parallel division also feeds B
    row(8, 2030, "C2", 1),
    row(8, 2031, "B", 6),
    row(9, 2030, "Z", 0),
    row(9, 2031, "Z", 0),  # an unconnected league that never moves
]


def test_league_levels_from_club_movement():
    level, above = league_levels(PYRAMID)
    assert level["A"] == 1 and level["B"] == 2
    assert level["C"] == 3 and level["C2"] == 3  # parallel divisions share a level
    assert level["Z"] == 1  # no evidence: top of its own pyramid
    assert pyramid_of(above, {"C"}) == {"A", "B", "C", "C2"}
    assert pyramid_of(above, {"Z"}) == {"Z"}


def test_a_single_move_is_not_enough_evidence():
    level, _ = league_levels([row(1, 2030, "X", 0), row(1, 2031, "Y", 0)])
    assert level == {"X": 1, "Y": 1}


def test_position_only_rows_are_ignored():
    rows = [row(1, 2030, "B", 0, played=255), row(1, 2031, "A", 0)] * 3
    level, _ = league_levels(rows)
    assert level["B"] == 1


def season(year, club, tier, position=5):
    return dict(end_year=year, club_uid=club, tier=tier, position=position)


def test_a_league_in_stages_is_one_level():
    # Portugal's third division: a regional group (which the levels put at the top, as no club
    # moves on from it), then the final stage, in the same season
    league = [
        season(2026, 1, 1, 10),
        season(2026, 1, 3, 2),
        season(2027, 1, 1, 3),
        season(2027, 1, 3, 1),
        season(2028, 1, 2),
    ]
    mark_seasons(league)
    assert [r["tier"] for r in league] == [3, 3, 3, 3, 2]
    assert not any(r["relegated"] for r in league)  # not "down" from the group to the final stage
    assert [r["promoted"] for r in league] == [False, False, True, True, False]


def test_seasons_up_down_and_moves():
    league = [season(2030, 1, 2, 1), season(2031, 1, 1, 18), season(2032, 1, 2), season(2033, 2, 1)]
    mark_seasons(league)
    assert [(r["champion"], r["promoted"], r["relegated"], r["moved"]) for r in league] == [
        (True, True, False, False),
        (False, False, True, False),
        (False, False, False, True),
        (False, False, False, False),
    ]


def played(year, club, comp, tier, name=None, db=None):
    return dict(
        end_year=year, club_uid=club, competition_id=comp, tier=tier, competition=name or comp, competition_db=db
    )


def test_a_move_abroad_is_a_new_country():
    # Portugal: a regional group G and the final stage P3, which no club moves between; Spain: S1
    above = {"G": {"P2"}, "P3": {"P2"}, "S2": {"S1"}}
    league = [
        played(2026, 1, "G", 3),
        played(2026, 1, "P3", 3),
        played(2027, 1, "P3", 3),
        played(2031, 2, "S1", 1),
        played(2032, 3, "S2", 2),
    ]
    assert countries(league, above) == [0, 0, 0, 1, 1]  # S2's club is another Spanish club


def test_levels_are_named_per_country_latest_first():
    league = [
        played(2026, 1, "G", 3, "Third Division - South", 900),
        played(2026, 1, "P3", 3, "Third Division", 901),
        played(2027, 1, "P1", 1, "Primeira Liga", 902),
        played(2031, 2, "S1", 1, "Spanish First Division", 67),
    ]
    levels = name_levels(
        league, [0, 0, 0, 1], {1: 20, 2: 22, 3: 20}, lambda lv: (None, 68) if lv == 2 else (None, None)
    )
    assert levels == [
        dict(level=1, name="Spanish First Division / Primeira Liga", competition_db=67, size=20),
        dict(level=2, name="Level 2", competition_db=68, size=22),  # never played: the save's league there, unnamed
        dict(level=3, name="Third Division", competition_db=901, size=20),  # a tie: the shorter, the final stage
    ]


class SpellSave:
    """A fake Save offering manager_spells."""

    def __init__(self, spells, managed=()):
        self._spells, self._managed = spells, managed

    def manager_spells(self, uid):
        return self._spells

    def managed_clubs(self):
        return list(self._managed)


def spell(team, start, end):
    return NS(team_id=team, start_date=start, end_date=end)


D = dt.date


def test_stints_come_from_manager_spells():
    s = SpellSave(
        [
            spell(1, None, D(2025, 5, 1)),
            spell(99, D(2025, 6, 1), D(2026, 1, 1)),
            spell(2, D(2026, 7, 1), D(2027, 1, 10)),
            spell(2, D(2027, 1, 11), None),
        ]
    )
    stints = manager_stints(s, NS(uid=7), None, [], {1: 10, 2: 20}, D(2030, 1, 1))
    # team 99 is a national team (no club); the two back-to-back spells at club 20 join
    assert stints == [
        dict(club_uid=10, start=None, end=D(2025, 5, 1)),
        dict(club_uid=20, start=D(2026, 7, 1), end=None),
    ]


def test_spells_at_one_club_with_a_gap_stay_apart():
    s = SpellSave([spell(1, D(2020, 7, 1), D(2021, 1, 1)), spell(1, D(2024, 7, 1), None)])
    stints = manager_stints(s, NS(uid=7), None, [], {1: 10}, D(2030, 1, 1))
    assert len(stints) == 2


def test_stints_fall_back_without_manager_spells():
    class Old:
        def managed_clubs(self):
            return [NS(manager_staff_uid=7, club_uid=20)]

    window = NS(team_id=1, start_date=D(2020, 7, 1), end_date=D(2022, 5, 1))
    record = NS(longest_club_spell=window, shortest_club_spell=None)
    events = [NS(team_id=2, event_date=D(2023, 1, 1)), NS(team_id=2, event_date=D(2024, 1, 1))]
    stints = manager_stints(Old(), NS(uid=7), record, events, {1: 10, 2: 20}, D(2025, 1, 1))
    assert stints == [
        dict(club_uid=10, start=D(2020, 7, 1), end=D(2022, 5, 1)),
        dict(club_uid=20, start=D(2023, 1, 1), end=None),
    ]


class StaffSave:
    def __init__(self, staff, careers):
        self._staff, self._careers = staff, careers

    def staff(self):
        return self._staff

    def manager_career(self, uid):
        return self._careers.get(uid)


def person(uid, name, human=False, common=None):
    first, _, last = name.partition(" ")
    return NS(
        uid=uid,
        name=common or name,
        full_name=name,
        common_name=common,
        first_name=first,
        last_name=last,
        is_human_manager=human,
        club_name="Club",
    )


def test_find_manager_by_name_ignoring_case_and_accents():
    s = StaffSave([person(1, "Uroš Koren"), person(2, "Sam Other")], {})
    assert find_manager(s, "uros koren").uid == 1


def test_find_manager_by_common_name():
    s = StaffSave([person(1, "Robson de Souza", common="Robinho")], {})
    assert find_manager(s, "Robinho").uid == 1


def test_find_manager_prefers_the_human_then_a_manager():
    s = StaffSave([person(1, "John Smith"), person(2, "John Smith", human=True)], {})
    assert find_manager(s, "John Smith").uid == 2
    s = StaffSave([person(1, "John Smith"), person(2, "John Smith")], {2: object()})
    assert find_manager(s, "John Smith").uid == 2


def test_find_manager_errors():
    s = StaffSave([person(1, "John Smith"), person(2, "John Smith")], {})
    with pytest.raises(SystemExit, match="matches several"):
        find_manager(s, "John Smith")
    with pytest.raises(SystemExit, match="no staff member"):
        find_manager(s, "Nobody Here")


def test_read_names(tmp_path):
    assert read_names(None) == ({}, {}, None)
    assert read_names(str(tmp_path)) == ({}, {}, None)
    (tmp_path / "competition_names.csv").write_text("13,League One\n7,Premier League\n", encoding="utf-8")
    (tmp_path / "award_names.csv").write_text(
        "award_index,database_id,name\n0,5,Manager of the Year\n", encoding="utf-8"
    )
    comps, awards, path = read_names(str(tmp_path))
    assert comps == {13: "League One", 7: "Premier League"}
    assert awards == {0: "Manager of the Year"}
    assert path.endswith("competition_names.csv")


def test_step_counts_match_the_progress_calls():
    """The app's progress bar relies on these counts."""
    assert len(re.findall(r"\bprogress\(", inspect.getsource(collect))) == COLLECT_STEPS

    class Empty:
        def staff(self):
            return []

        def career_manager_records(self):
            return []

        def history_people(self):
            return []

    for everyone in (False, True):
        seen = []
        list_managers(Empty(), seen.append, everyone=everyone)
        assert len(seen) == manager_steps(everyone)


def test_a_new_saves_manager_is_listed_before_his_first_game():
    """Pre-season, the record holds no games (friendlies don't count) but he is still there."""

    def person(uid, human, unique_id):
        return NS(uid=uid, name=f"P{uid}", club_name="C", club_uid=7, is_human_manager=human, unique_id=unique_id)

    def rec(ref, games):
        return NS(reference=ref, games=games, wins=0, draws=0, losses=0, club_jobs=1)

    me, other = person(1, True, 11), person(2, False, 22)
    records = {1: rec(101, 0), 2: rec(102, 0)}

    class Save:
        def staff(self):
            return [me, other]

        def manager_career(self, uid):
            return records[uid]

        def career_manager_records(self):
            return list(records.values())

        def history_people(self):
            return [NS(reference=101, unique_id=11), NS(reference=102, unique_id=22)]

    for everyone in (False, True):
        assert [m["staff_uid"] for m in list_managers(Save(), everyone=everyone)] == [1]


def totals(games, wins, draws, losses, signing=None):
    return NS(
        **(dict.fromkeys(CAREER_TOTALS, 0) | dict(games=games, wins=wins, draws=draws, losses=losses, club_jobs=1)),
        highest_fee_paid=signing,
        highest_fee_received=None,
    )


def test_the_record_adds_the_womens_career_to_the_mens():
    def fee(amount):
        return NS(player_reference=1, fee=amount, transfer_date=None, from_team_id=None, to_team_id=None)

    womens = totals(10, 6, 2, 2, fee(500))
    record = NS(**vars(totals(100, 50, 30, 20, fee(200))), womens_career=womens)
    c = NS(record=record, person=lambda uid, ref: "P", person_id=lambda uid, ref: 1, teams={})

    out = career_record(c)
    assert (out["games"], out["wins"], out["draws"], out["losses"], out["club_jobs"]) == (110, 56, 32, 22, 2)
    assert out["record_signing"]["fee"] == 500  # the larger of the two careers'
    assert out["womens"] == dict(games=10, wins=6, draws=2, losses=2)
    record.womens_career = None
    assert career_record(c)["womens"] is None and career_record(c)["games"] == 100


def test_move_kinds():
    assert move_kind("in", "Transfer", "Big City") == "signing"
    assert move_kind("in", "Free", None) == "signing"
    assert move_kind("in", "Loan", "Big City") is None
    assert move_kind("out", "Transfer", "Big City") == "sale"
    assert move_kind("out", "Free", "Big City") == "free_departure"
    assert move_kind("out", "Free", None) is None  # released with no club to go to
    assert move_kind("out", "Released", None) is None


def test_teams_are_named_by_what_they_play():
    club = NS(
        teams=[NS(team_id=t, slot=i, is_affiliate=False) for i, t in enumerate([10, 11, 12, 13, 14])]
        + [NS(team_id=99, slot=5, is_affiliate=True)]
    )
    fixtures = [
        NS(competition_id=1, competition_name=None, home_team_id=10, away_team_id=50),
        NS(competition_id=5, competition_name=None, home_team_id=11, away_team_id=54),
        NS(competition_id=2, competition_name=None, home_team_id=12, away_team_id=51),
        NS(competition_id=3, competition_name=None, home_team_id=52, away_team_id=13),
        NS(competition_id=4, competition_name=None, home_team_id=14, away_team_id=53),
    ]
    names = {
        1: "Example League",
        5: "Example Reserve League",
        2: "Example Pro League u21",
        3: "Example FA Youth Cup",
        4: "Friendly",
    }
    teams = team_names(club, team_competitions(NS(fixtures=lambda: fixtures), names))
    assert teams == {
        10: (0, "First team"),
        11: (1, "Reserves"),
        12: (2, "Under-21s"),
        13: (3, "Youth team"),
        14: (4, "Team 5"),
    }  # friendlies don't name a team


def test_age_groups_come_from_any_u_number_oldest_first():
    club = NS(teams=[NS(team_id=1, slot=0, is_affiliate=False), NS(team_id=2, slot=1, is_affiliate=False)])
    plays = {2: {"Example U20 Division A", "Example U18 Cup"}}
    assert team_names(club, plays)[2] == (1, "Under-20s")


def test_an_event_log_that_cannot_be_walked_leaves_the_extras_out(caplog):
    import fmsave

    from fmcareer.collect import manager_events

    def broken(uid):
        raise fmsave.CorruptSaveError("event entry at 3350 does not carry the 0x15 mark")

    human, other = NS(uid=7, is_human_manager=True), NS(uid=8, is_human_manager=False)
    assert manager_events(NS(manager_events=broken), human) == []
    assert "0x15 mark" in caplog.text
    assert manager_events(NS(manager_events=lambda uid: iter(["e"])), human) == ["e"]
    assert manager_events(NS(manager_events=broken), other) == []


def test_an_optional_part_that_fails_is_left_out_and_named(caplog):
    from fmcareer.collect import optional

    problems = []

    def breaks(c):
        return {}[126108]

    assert optional("Honours", problems, ([], [], []), breaks, None) == ([], [], [])
    assert optional("Transfers", problems, [], lambda c: ["move"], None) == ["move"]
    assert problems == [{"part": "Honours", "error": "KeyError: 126108"}]
    assert "Honours could not be read" in caplog.text and "Traceback" in caplog.text


def test_report_gaps_count_each_unnamed_thing_once():
    data = {
        "manager": {"name": "Alex"},
        "league": [{"competition": "Competition 1301392"}, {"competition": "Competition 1301392"}],
        "cups": [{"competition": "Stage 412", "opponent": "Club 7"}, {"competition": "FA Cup"}],
        "awards": [{"name": "Award 56"}],
        "transfers": [{"player": "Unknown player (881)"}],
        "levels": [{"name": "Level 3"}],
        "ai": {"career": {"paragraphs": ["Competition 99"]}},  # articles aren't searched
    }
    gaps = {g["kind"]: g for g in report_gaps(data)}
    assert gaps["competitions"]["count"] == 3
    assert gaps["competitions"]["examples"] == ["Competition 1301392", "Stage 412", "Level 3"]
    assert gaps["awards"]["count"] == gaps["clubs"]["count"] == gaps["players"]["count"] == 1
    assert "managers" not in gaps
    assert report_gaps({"league": [{"competition": "Premier League 2"}]}) == []


def test_sponsorship_income_counts_only_running_contracts():
    today = dt.date(2033, 12, 1)
    rows = [
        NS(club_uid=1, end=dt.date(2035, 6, 30), annual_value=400),  # running
        NS(club_uid=1, end=dt.date(2031, 6, 30), annual_value=900),  # ended, value kept
        NS(club_uid=1, end=None, annual_value=100),  # no end date: kept
        NS(club_uid=2, end=dt.date(2035, 6, 30), annual_value=50),  # another club
    ]
    assert [x.annual_value for x in running_sponsors(rows, 1, today)] == [400, 100]


def test_the_season_in_progress_comes_from_the_live_stats():
    import fmsave

    kind = fmsave.SeasonStatsKind

    def stats(uid, kind, team, apps, goals=0, rating=7.0):
        return NS(
            player_uid=uid,
            player_name=f"Player {uid}",
            kind=kind,
            team_id=team,
            rated_appearances=apps,
            starts=apps,
            substitute_appearances=0,
            goals=goals,
            assists=0,
            minutes=90 * apps,
            average_rating=rating if apps else None,
            player_of_the_match=0,
            yellow_cards=0,
            red_cards=0,
        )

    rows = [
        stats(1, kind.LEAGUE, 500, 2, goals=1, rating=7.5),
        stats(1, kind.CUP, 500, 1, rating=6.0),
        stats(1, kind.OVERALL, 500, 3, goals=1),  # the season total, not added again
        stats(1, kind.NON_COMPETITIVE, 500, 4),  # friendlies
        stats(2, kind.LEAGUE, 501, 3),  # the reserves
        stats(3, kind.LEAGUE, 500, 0),  # in the squad, not yet played
    ]
    c = NS(
        s=NS(player_season_stats=lambda: rows),
        game_date=dt.date(2025, 8, 31),
        current_uids={1},
        in_career=lambda club, end_year: (club, end_year) == (77, 2026),
        person=lambda uid, ref, fallback=None: fallback,
        person_id=lambda uid, ref: uid + 1000,
    )
    season, live = _live_squad_stats(c, {500: 77})
    assert season == "2025/26"
    assert live == [
        dict(
            name="Player 1",
            current=True,
            person_id=1001,
            apps=3,
            starts=3,
            subs=0,
            goals=1,
            assists=0,
            minutes=270,
            pom=0,
            yellow=0,
            red=0,
            rating=7.0,
        )
    ]


def test_club_colours_are_kept_for_the_managers_clubs_only():
    rows = [
        NS(club_uid=10, first_colour="#26488B", second_colour="#FAFAFA"),
        NS(club_uid=99, first_colour="#CF1C2C", second_colour="#FAFAFA"),
    ]
    c = NS(s=NS(club_colours=lambda: rows), stints=[{"club_uid": 10}, {"club_uid": 20}])
    assert club_colours(c) == {"10": ["#26488B", "#FAFAFA"]}


def test_the_club_tint_is_a_colour_white_text_reads_on():
    assert club_tint("#26488B", "#FAFAFA") == "rgb(38,72,139)"  # Fethiyespor: the navy as it is
    assert club_tint("#FFE252", "#2D68B5") == "rgb(45,104,181)"  # St Albans: the blue, not dark yellow
    assert club_tint("#FAFAFA", "#3CB571") == "rgb(42,129,80)"  # Celtic: only the green, darkened
    assert club_tint("#FAFAFA", "#1E2021") == "rgb(30,32,33)"  # Juventus: the black
    assert club_tint("#FAFAFA", "#E6E6E6") is None  # two whites: the badge decides
