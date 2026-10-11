"""Shared fixtures: a small made-up career that exercises every page of the report."""

import copy

import pytest

SAMPLE = {
    "manager": {
        "name": "Alex Example", "club": "Example Town", "spell_start": 2030,
        "game_date": "2033-12-01", "birth_date": "1985-03-17", "age": 48, "wage": 5000,
        "contract_start": "2031-07-01", "contract_end": "2035-06-30", "human": True,
        "person_id": 101, "nation_id": 139,
    },
    "stints": [
        {"club": "Old Rovers", "club_uid": 10, "start": "2029-07-01", "end": "2030-11-01"},
        {"club": "Example Town", "club_uid": 20, "start": "2030-11-02", "end": None},
    ],
    "league": [
        {"season": "2029/30", "end_year": 2030, "club": "Old Rovers", "club_uid": 10,
         "competition": "Second Division", "competition_id": 2, "competition_db": 902, "tier": 2,
         "rank": 23, "position": 3, "teams": 24, "played": 46, "won": 25, "drawn": 10, "lost": 11,
         "goals_for": 70, "goals_against": 45, "points": 85,
         "champion": False, "promoted": False, "relegated": False, "moved": True},
        {"season": "2031/32", "end_year": 2032, "club": "Example Town", "club_uid": 20,
         "competition": "Second Division", "competition_id": 2, "competition_db": 902, "tier": 2,
         "rank": 21, "position": 1, "teams": 24, "played": 46, "won": 30, "drawn": 8, "lost": 8,
         "goals_for": 90, "goals_against": 40, "points": 98,
         "champion": True, "promoted": True, "relegated": False, "moved": False},
        {"season": "2032/33", "end_year": 2033, "club": "Example Town", "club_uid": 20,
         "competition": "First Division", "competition_id": 1, "competition_db": 901, "tier": 1,
         "rank": 12, "position": 12, "teams": 20, "played": 38, "won": 13, "drawn": 10, "lost": 15,
         "goals_for": 50, "goals_against": 55, "points": 49,
         "champion": False, "promoted": False, "relegated": False, "moved": False},
    ],
    "levels": [{"level": 1, "name": "First Division", "size": 20},
               {"level": 2, "name": "Second Division", "size": 24}],
    "tables": {
        "2032/33": [
            {"position": 1, "club": "Big City", "club_uid": 30, "me": False, "played": 38, "won": 28,
             "drawn": 5, "lost": 5, "goals_for": 80, "goals_against": 30, "points": 89},
            {"position": 12, "club": None, "club_uid": None, "me": True, "played": 38, "won": 13,
             "drawn": 10, "lost": 15, "goals_for": 50, "goals_against": 55, "points": 49,
         "champion": False, "promoted": False, "relegated": False, "moved": False},
            {"position": 13, "club": None, "club_uid": None, "me": False, "played": 38, "won": 12,
             "drawn": 9, "lost": 17, "goals_for": 44, "goals_against": 60, "points": 45},
        ],
    },
    "honours": [{"season": "2031/32", "end_year": 2032, "club": "Example Town",
                 "competition_db": 902, "name": "Second Division"}],
    "cups": [
        {"season": "2032/33", "end_year": 2033, "club": "Example Town", "competition_db": 905,
         "opponent_uid": 30, "competition": "National Cup", "youth": False, "won": False,
         "league_stage": False, "position": None, "opponent": "Big City", "method": "on penalties"},
    ],
    "awards": [{"season": "2031/32", "end_year": 2032, "name": "Second Division Manager of the Season",
                "placing": "Winner", "age": 46, "club": "Example Town"}],
    "best_eleven": {
        "2032/33": [
            {"slot": 0, "name": "Gary Keeper", "person_id": 201, "current": True, "apps": 38, "goals": 0, "rating": 6.9},
            {"slot": 9, "name": "Sam Striker", "person_id": 202, "current": False, "apps": 36, "goals": 21, "rating": 7.3},
        ],
    },
    "squad_stats": {
        "2031/32": [
            {"name": "Sam Striker", "person_id": 202, "current": False, "apps": 40, "starts": 38, "subs": 2,
             "goals": 25, "assists": 7, "minutes": 3300, "pom": 6, "yellow": 3, "red": 0, "rating": 7.4},
        ],
        "2032/33": [
            {"name": "Gary Keeper", "person_id": 201, "current": True, "apps": 38, "starts": 38, "subs": 0,
             "goals": 0, "assists": 0, "minutes": 3420, "pom": 2, "yellow": 1, "red": 0, "rating": 6.9},
            {"name": "Sam Striker", "person_id": 202, "current": False, "apps": 36, "starts": 33, "subs": 3,
             "goals": 21, "assists": 5, "minutes": 2900, "pom": 5, "yellow": 2, "red": 0, "rating": 7.3},
            {"name": "Old Retiree", "person_id": None, "current": False, "apps": 12, "goals": 1, "rating": 6.6,
             "starts": None, "subs": None, "assists": None, "minutes": None, "pom": None, "yellow": None,
             "red": None, "partial": True},
        ],
    },
    "transfers": [
        {"date": "2031-07-10", "season": "2031/32", "end_year": 2032, "club": "Example Town", "direction": "in",
         "type": "Transfer", "kind": "signing", "staff": False, "fee": 1500000, "player": "Sam Striker", "person_id": 202,
         "other": "Big City", "other_uid": 30},
        {"date": "2032-01-05", "season": "2031/32", "end_year": 2032, "club": "Example Town", "direction": "in",
         "type": "Trial", "kind": None, "staff": False, "fee": None, "player": "Tom Trialist", "person_id": 203,
         "other": None, "other_uid": None},
        {"date": "2033-07-01", "season": "2033/34", "end_year": 2034, "club": "Example Town", "direction": "out",
         "type": "Transfer", "kind": "sale", "staff": False, "fee": 9000000, "player": "Sam Striker", "person_id": 202,
         "other": "Big City", "other_uid": 30},
        {"date": "2032-08-01", "season": "2032/33", "end_year": 2033, "club": "Example Town", "direction": "in",
         "type": "Staff joined", "kind": None, "staff": True, "fee": None, "player": "Staff member", "person_id": None,
         "other": None, "other_uid": None},
    ],
    "players_bought": 1,
    "squad": [{"name": "Gary Keeper", "age": 30, "person_id": 201}],
    "notable_matches": [{"date": "2032-03-01", "season": "2031/32", "opponent": "Big City",
                         "goals_for": 5, "goals_against": 0, "competition": "Second Division"}],
    "career": {"games": 180, "wins": 90, "draws": 40, "losses": 50, "goals_for": 300, "goals_against": 200,
               "league_titles": 1, "cups": 0, "awards": 3, "players_bought": 12, "players_sold": 5,
               "players_released": 7, "money_spent": 4000000, "agent_fees": 100000, "club_jobs": 2,
               "record_signing": {"player": "Sam Striker", "person_id": 202, "fee": 1500000,
                                  "date": "2031-07-10", "from_club": "Big City", "to_club": "Example Town"},
               "record_sale": None},
    "club_today": {
        "club": "Example Town", "club_uid": 20,
        "stadium": {"name": "Example Park", "capacity": 12000, "built": 1990},
        "finances": {"month": "2033-11-01", "balance": -250000, "transfer_budget": 2000000,
                     "transfer_left": 1500000, "wage_budget": 90000, "wage_payroll": 85000},
        "balance_history": [{"month": "2033-09-01", "balance": 100000, "income": 1, "spend": 1},
                            {"month": "2033-10-01", "balance": -50000, "income": 1, "spend": 1},
                            {"month": "2033-11-01", "balance": -250000, "income": 1, "spend": 1}],
        "sponsors": {"count": 2, "annual": 500000}, "corporate_facilities": "Good",
        "tactics": [{"name": "Balanced 4-4-2", "style": "Control", "mentality": "Balanced"}],
        "squad": [{"name": "Gary Keeper", "person_id": 201, "age": 30, "positions": "GK", "ability": 120,
                   "potential": 125, "value": 2000000, "wage": 4000, "contract_end": "2035-06-30",
                   "status": "Regular starter", "joined": "2030-07-01", "on_loan": False, "first_team": True}],
        "live_table": {"competition": "First Division", "competition_db": 901, "rows": [
            {"position": 1, "club_uid": 30, "club": "Big City", "me": False, "played": 14, "won": 10,
             "drawn": 2, "lost": 2, "goals_for": 30, "goals_against": 10, "points": 32},
            {"position": 9, "club_uid": 20, "club": "Example Town", "me": True, "played": 14, "won": 5,
             "drawn": 4, "lost": 5, "goals_for": 18, "goals_against": 19, "points": 19}]},
        "affiliates": [], "staff": 25,
    },
    "options": {"sections": ["me", "seasons", "players", "records", "honours", "transfers", "club"],
                "show": {"Loan": False, "Trial": False, "Youth intake": False, "Released": True, "staff": False}},
}


@pytest.fixture
def sample():
    """A fresh deep copy of the sample career, safe to modify."""
    return copy.deepcopy(SAMPLE)
