"""The pure parts of collect: league levels, club spells, manager lookup, names, helpers."""

import datetime as dt
import inspect
import re
from types import SimpleNamespace as NS

import pytest

from fmcareer.collect import (
    COLLECT_STEPS,
    _norm,
    collect,
    find_manager,
    league_levels,
    list_managers,
    manager_steps,
    manager_stints,
    move_kind,
    pyramid_of,
    read_names,
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
