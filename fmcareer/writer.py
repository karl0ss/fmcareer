"""Season summaries and the career introduction written by a language model.

Optional: the report's own templated text is always there, and is what the report shows
when no model is set or a call fails. Any OpenAI-compatible chat endpoint works (OpenAI,
llama.cpp / llama-swap, Ollama, LM Studio, vLLM, ...): the model is handed only facts
taken from the collected career and told to use nothing else.
"""

import hashlib
import json
import re
import urllib.error
import urllib.request

PROMPT_VERSION = 4  # bump when the prompts or facts change, so cached text is rewritten

SEASON_PROMPT = """You write the season review in a Football Manager career report.
Write from the JSON facts the user gives you and nothing else: never invent players, \
scores, dates, rounds, transfers or events, and leave out anything the facts don't say.
Rules: every name, number, trophy and achievement you mention must be in the facts. \
Never call anything a record, historic, first or best unless the facts say so. Never say \
whether a match was home or away. Write every number as digits, exactly as given. \
A manager award placing other than "Winner" means he did not win it.
Style: British English, past tense, third person, like a club historian. Two or three \
short paragraphs separated by blank lines, 130 words at most in all. No headings, lists, bullet points or markdown. \
Money is already written the way it should appear."""

OVERVIEW_PROMPT = """You write the introduction to a Football Manager manager's career report.
Write from the JSON facts the user gives you and nothing else: never invent players, \
scores, dates, clubs or events, and leave out anything the facts don't say. The \
league_titles list is complete: no other league was won.
Rules: every name, number, trophy and achievement you mention must be in the facts. \
Never call anything a record, historic, first or best unless the facts say so. Never say \
whether a match was home or away. Write every number as digits, exactly as given. \
A manager award placing other than "Winner" means he did not win it.
Style: British English, third person, like a club historian. Exactly two short paragraphs \
separated by a blank line (the journey, then the honours and record), 130 words at most in all. No headings, lists, bullet points or markdown."""


class WriterError(Exception):
    """The endpoint could not be reached or gave no usable answer."""


def money(n):
    if n is None:
        return None
    sign, n = ("-" if n < 0 else ""), abs(n)
    if n >= 1_000_000:
        return f"{sign}£{n / 1_000_000:.2f}M".replace(".00M", "M")
    if n >= 1_000:
        return f"{sign}£{n / 1_000:.0f}k"
    return f"{sign}£{n}"


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---- facts

def comparison(prev, r):
    """How a season compares with the one before, spelt out so the model needn't work it out."""
    if prev["club"] != r["club"]:
        return "a different club from the previous season"
    if prev["competition"] != r["competition"]:
        up = (r.get("tier") or 99) < (prev.get("tier") or 99)
        return f"played a division {'higher' if up else 'lower'} than the previous season"
    place = ("finished higher" if r["position"] < prev["position"] else
             "finished lower" if r["position"] > prev["position"] else "finished in the same place")
    points = ("more points" if r["points"] > prev["points"] else
              "fewer points" if r["points"] < prev["points"] else "the same points")
    return f"{place} in the same division than the previous season, with {points}"


def award_phrase(a):
    if a["placing"] == "Winner":
        return f"won {a['name']}"
    return f"{a['placing'].lower()} for {a['name']} (did not win it)"


_SIGNING = {"Transfer", "Free", "Signing"}


def season_facts(data):
    """[(season, facts)] for every league season, in order."""
    league, manager = data.get("league", []), data.get("manager", {}).get("name")
    out = []
    for i, r in enumerate(league):
        prev, nxt = (league[i - 1] if i else None), (league[i + 1] if i + 1 < len(league) else None)
        same = nxt is not None and nxt["club_uid"] == r["club_uid"]
        season = r["season"]
        facts = {
            "season": season, "manager": manager, "club": r["club"],
            "competition": r["competition"],
            "top_division": r.get("tier") == 1,
            "league_finish": ordinal(r["position"]), "teams": r["teams"],
            "played": r["played"], "won": r["won"], "drawn": r["drawn"], "lost": r["lost"],
            "goals_for": r["goals_for"], "goals_against": r["goals_against"], "points": r["points"],
            "champions": r["position"] == 1,
            "promoted": bool(same and nxt.get("tier") and r.get("tier") and nxt["tier"] < r["tier"]),
            "relegated": bool(same and nxt.get("tier") and r.get("tier") and nxt["tier"] > r["tier"]),
            "manager_left_for_another_club_after": bool(nxt and not same),
        }
        if prev:
            facts["previous_season"] = {"club": prev["club"], "competition": prev["competition"],
                                        "league_finish": ordinal(prev["position"]), "points": prev["points"]}
            facts["compared_with_previous_season"] = comparison(prev, r)
        cups = []
        for c in data.get("cups", []):
            if c["season"] != season or c.get("youth") or c.get("league_stage"):
                continue
            cup = {"competition": c["competition"], "result": "won the final" if c["won"] else "knocked out"}
            if c.get("opponent"):
                cup["final_opponent" if c["won"] else "knocked_out_by"] = c["opponent"]
            if c.get("method"):
                cup["how"] = c["method"]
            cups.append(cup)
        if cups:
            facts["cups"] = cups
        honours = [h["name"] for h in data.get("honours", []) if h["season"] == season]
        if honours:
            facts["trophies"] = honours
        awards = [award_phrase(a) for a in data.get("awards", []) if a["season"] == season]
        if awards:
            facts["manager_awards"] = awards
        xi = data.get("best_eleven", {}).get(season) or []
        if xi:
            top = max(xi, key=lambda p: p.get("goals") or 0)
            most = max(xi, key=lambda p: p.get("apps") or 0)
            if top.get("goals"):
                facts["top_scorer"] = {"name": top["name"], "goals": top["goals"]}
            facts["most_appearances"] = {"name": most["name"], "appearances": most["apps"]}
            rated = [p for p in xi if p.get("rating")]
            if rated:
                star = max(rated, key=lambda p: p["rating"])
                facts["best_average_rating"] = {"name": star["name"], "rating": round(star["rating"], 2)}
        moves = [t for t in data.get("transfers", []) if t["season"] == season and not t.get("staff")]
        ins = [t for t in moves if t["direction"] == "in" and t["type"] in _SIGNING]
        outs = [t for t in moves if t["direction"] == "out" and t["type"] in ("Transfer", "Free") and t.get("other")]
        if ins or outs:
            market = {"signings": len(ins), "departures_to_other_clubs": len(outs)}
            spent = sum(t["fee"] or 0 for t in moves if t["direction"] == "in")
            got = sum(t["fee"] or 0 for t in moves if t["direction"] == "out")
            if spent:
                market["spent"] = money(spent)
            if got:
                market["received"] = money(got)
            paid = [t for t in ins if t.get("fee")]
            if paid:
                t = max(paid, key=lambda t: t["fee"])
                market["biggest_signing"] = {"player": t["player"], "fee": money(t["fee"]), "from": t.get("other")}
            sold = [t for t in outs if t.get("fee")]
            if sold:
                t = max(sold, key=lambda t: t["fee"])
                market["biggest_sale"] = {"player": t["player"], "fee": money(t["fee"]), "to": t.get("other")}
            facts["transfers"] = market
        notable = [{"opponent": m["opponent"], "score": f"{m['goals_for']}-{m['goals_against']}",
                    "competition": m.get("competition")}
                   for m in data.get("notable_matches", []) if m["season"] == season and m.get("opponent")]
        if notable:
            facts["notable_results"] = notable[:4]
        out.append((season, facts))
    return out


def overview_facts(data):
    league, m, career = data.get("league", []), data.get("manager", {}), data.get("career") or {}
    stints = [{"club": s["club"], "from": (s["start"] or "")[:4] or None, "to": (s["end"] or "")[:4] or "present"}
              for s in data.get("stints", [])]
    facts = {"manager": m.get("name"), "clubs": stints, "seasons_completed": len(league)}
    if league:
        first, last = league[0], league[-1]
        facts["first_season"] = {"season": first["season"], "club": first["club"], "competition": first["competition"],
                                 "league_finish": ordinal(first["position"])}
        facts["latest_season"] = {"season": last["season"], "club": last["club"], "competition": last["competition"],
                                  "league_finish": ordinal(last["position"]), "top_division": last.get("tier") == 1}
        tiers = [r for r in league if r.get("rank")]
        if tiers:
            best = min(tiers, key=lambda r: r["rank"])
            facts["best_league_finish"] = {"season": best["season"], "club": best["club"],
                                           "competition": best["competition"], "league_finish": ordinal(best["position"])}
        promoted = sum(1 for a, b in zip(league, league[1:])
                       if a["club_uid"] == b["club_uid"] and a.get("tier") and b.get("tier") and b["tier"] < a["tier"])
        facts["promotions"] = promoted
        facts["league_titles"] = [f"{r['competition']} ({r['season']})" for r in league if r["position"] == 1]
    cups_won = [f"{c['competition']} ({c['season']})" for c in data.get("cups", []) if c.get("won") and not c.get("youth")]
    if cups_won:
        facts["cups_won"] = cups_won
    wins = [f"{a['name']} ({a['season']})" for a in data.get("awards", []) if a["placing"] == "Winner"]
    near = [f"{a['placing'].lower()} for {a['name']} ({a['season']})" for a in data.get("awards", [])
            if a["placing"] != "Winner"]
    if near:
        facts["manager_awards_not_won"] = near
    if wins:
        facts["manager_awards_won"] = wins
    if career.get("games"):
        facts["record"] = {k: career.get(k) for k in ("games", "wins", "draws", "losses")}
    for key in ("record_signing", "record_sale"):
        rec = career.get(key)
        if rec and rec.get("fee"):
            facts[key] = {"player": rec.get("player"), "fee": money(rec["fee"])}
    return facts


# ---- the endpoint

def _base(endpoint):
    return endpoint.rstrip("/")


def _request(endpoint, token, path, body=None, timeout=300):
    req = urllib.request.Request(_base(endpoint) + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        raise WriterError(f"the endpoint answered {e.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise WriterError(f"could not reach {endpoint}: {getattr(e, 'reason', e)}") from None
    except ValueError:
        raise WriterError("the endpoint did not answer with JSON") from None


def list_models(endpoint, token):
    found = _request(endpoint, token, "/models", timeout=20)
    return sorted(m["id"] for m in found.get("data", []) if isinstance(m, dict) and m.get("id"))


def tidy(text):
    """Model output as plain paragraphs: no thinking blocks, markdown or headings."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M)
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    return [p for p in paras if p]


def chat(endpoint, token, model, system, facts):
    answer = _request(endpoint, token, "/chat/completions", {
        "model": model, "temperature": 0.3, "max_tokens": 4000,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}]})
    try:
        text = answer["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise WriterError("the endpoint's answer had no message") from None
    paras = tidy(text)
    if not paras:
        raise WriterError("the model wrote nothing (a reasoning model may need a larger token limit)")
    return paras


_NUMBER = re.compile(r"\d[\d,.]*")


def unsupported_numbers(paras, facts):
    """Numbers in the text that the facts don't contain (a sign the model made something up)."""
    known = json.dumps(facts, ensure_ascii=False)
    pool = set(_NUMBER.findall(known)) | {n.replace(",", "") for n in _NUMBER.findall(known)}
    pool |= {str(int(y) % 100).zfill(2) for y in re.findall(r"\b(?:19|20)\d\d\b", known)}  # 2024/25
    bad = []
    for n in _NUMBER.findall(" ".join(paras)):
        n = n.rstrip(".,")
        if n and n not in pool and n.replace(",", "") not in pool:
            bad.append(n)
    return bad


def checked_chat(endpoint, token, model, system, facts, tries=2):
    """chat(), asked again when the text has numbers the facts don't; None if it never fits."""
    for _ in range(tries):
        paras = chat(endpoint, token, model, system, facts)
        if not unsupported_numbers(paras, facts):
            return paras
    return None


def text_key(model, endpoint, system, facts):
    raw = json.dumps([PROMPT_VERSION, _base(endpoint), model, system, facts], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def write(data, endpoint, token, model, step, known=None):
    """The model's text for the career: {"model", "overview", "seasons": {season: [paragraphs]}}.

    `known` maps text keys to paragraphs written before (updated in place), so unchanged
    seasons are not rewritten. `step` is called once per piece of text. Raises WriterError
    on the first failure; what was written by then is in `known`.
    """
    known = {} if known is None else known
    jobs = [("overview", OVERVIEW_PROMPT, overview_facts(data))]
    jobs += [(season, SEASON_PROMPT, facts) for season, facts in season_facts(data)]
    out = {"model": model, "overview": None, "seasons": {}}
    for name, system, facts in jobs:
        key = text_key(model, endpoint, system, facts)
        label = "the career introduction" if name == "overview" else f"the {name} summary"
        if key in known:
            step(f"Using {label} written before")
        else:
            step(f"Writing {label} with {model}")
            known[key] = checked_chat(endpoint, token, model, system, facts)
        if known[key] is None:  # it kept adding facts of its own: the plain summary stays
            continue
        if name == "overview":
            out["overview"] = known[key]
        else:
            out["seasons"][name] = known[key]
    return out


def pieces(data):
    """How many pieces of text write() produces (and progress steps it reports)."""
    return 1 + len(data.get("league", []))
