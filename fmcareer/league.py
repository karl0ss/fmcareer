"""Each league season's level, movement and place in the pyramid, worked out from the career's
league rows alone. fm-careers runs these over stored reports an older fmcareer got wrong, so,
like page.py, this module needs no save.
"""

from fmcareer._types import Record


def mark_seasons(league: list[Record]) -> None:
    """Each season's level, champion / promoted / relegated (by the club's level the next season)
    and moved (a new club next), in place; `league` is in season order."""
    # a league played in stages (Portugal's third division: regional groups, then a final stage)
    # is two competitions in one season. No club moves from a first stage to another league the
    # next season, so the levels put it at the top; but a club plays at one level a season, so
    # a season's stages share the deepest level among them.
    season_tier: dict[tuple[int, int], int] = {}
    for r in league:
        if r["tier"]:
            key = (r["club_uid"], r["end_year"])
            season_tier[key] = max(season_tier.get(key, 0), r["tier"])
    for r in league:
        r["tier"] = season_tier.get((r["club_uid"], r["end_year"]), r["tier"])
    for i, r in enumerate(league):
        # the next season's row: a season's other stage says nothing about going up or down
        nxt = next((x for x in league[i + 1 :] if x["end_year"] > r["end_year"]), None)
        same = nxt is not None and nxt["club_uid"] == r["club_uid"]
        up_down = nxt["tier"] - r["tier"] if same and nxt and nxt["tier"] and r["tier"] else 0
        r["champion"] = r["position"] == 1
        r["promoted"] = up_down < 0
        r["relegated"] = up_down > 0
        r["moved"] = nxt is not None and not same


def rank(league: list[Record], level_size: dict[int, int]) -> None:
    """Each season's overall rank in the pyramid, in place: the clubs in the levels above, then its
    position. `level_size` is each level's number of clubs."""
    for r in league:
        lv = r["tier"]
        r["rank"] = sum(level_size.get(x, 0) for x in range(1, lv)) + r["position"] if lv else None
