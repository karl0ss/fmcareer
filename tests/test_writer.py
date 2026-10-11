"""The AI writer's facts, its checks on what the model writes, and the endpoint calls."""

import json

import pytest

from fmcareer import writer


def test_season_facts_follow_the_report(sample):
    facts = dict(writer.season_facts(sample))
    title = facts["2031/32"]
    assert title["champions"] and title["promoted"] and title["league_finish"] == "1st"
    assert title["manager_awards"] == ["won Second Division Manager of the Season"]
    assert title["transfers"]["biggest_signing"] == {"player": "Sam Striker", "fee": "£1.50M", "from": "Big City"}
    later = facts["2032/33"]
    assert later["previous_season"]["league_finish"] == "1st" and not later["champions"]
    assert later["cups"] == [{"competition": "National Cup", "result": "knocked out",
                              "knocked_out_by": "Big City", "how": "on penalties"}]
    assert later["top_scorer"] == {"name": "Sam Striker", "goals": 21}


def test_overview_facts(sample):
    facts = writer.overview_facts(sample)
    assert facts["manager"] == "Alex Example" and facts["promotions"] == 1
    assert facts["league_titles"] == ["Second Division (2031/32)"]
    assert facts["best_league_finish"]["competition"] == "First Division"


def test_numbers_the_facts_do_not_have_are_caught():
    facts = {"season": "2024/25", "points": 111, "fee": "£1.50M", "score": "5-1"}
    assert writer.unsupported_numbers(["They won 2024/25 with 111 points and a 5-1 win; £1.50M."], facts) == []
    assert writer.unsupported_numbers(["A club record 112 points."], facts) == ["112"]


def test_tidy_drops_thinking_and_markdown():
    assert writer.tidy("<think>plan</think>## Title\n**Bold** start.\n\n\nNext  para.") == ["Title Bold start.", "Next para."]


class FakeEndpoint:
    def __init__(self, monkeypatch, replies):
        self.replies, self.sent = list(replies), []
        monkeypatch.setattr(writer, "_request", self.request)

    def request(self, endpoint, token, path, body=None, timeout=300):
        self.sent.append((endpoint, token, path, body))
        if path == "/models":
            return {"data": [{"id": "b"}, {"id": "a"}]}
        return {"choices": [{"message": {"content": self.replies.pop(0)}}]}


def test_chat_and_models(monkeypatch):
    fake = FakeEndpoint(monkeypatch, ["Hello."])
    assert writer.list_models("http://x/v1/", "t") == ["a", "b"]
    assert writer.chat("http://x/v1", "t", "m", "system", {"a": 1}) == ["Hello."]
    _, token, path, body = fake.sent[-1]
    assert token == "t" and path == "/chat/completions" and body["model"] == "m"
    assert json.loads(body["messages"][1]["content"]) == {"a": 1}


def test_an_invented_number_is_retried_then_dropped(monkeypatch):
    facts = {"points": 50}
    FakeEndpoint(monkeypatch, ["They got 51 points.", "They got 50 points."])
    assert writer.checked_chat("http://x/v1", "", "m", "s", facts) == ["They got 50 points."]
    FakeEndpoint(monkeypatch, ["51 points.", "52 points."])
    assert writer.checked_chat("http://x/v1", "", "m", "s", facts) is None


def test_write_reuses_known_text(monkeypatch, sample):
    fake = FakeEndpoint(monkeypatch, ["Intro."] + ["Season text."] * 3)
    steps, known = [], {}
    out = writer.write(sample, "http://x/v1", "", "m", steps.append, known)
    assert out["overview"] == ["Intro."] and set(out["seasons"]) == {"2029/30", "2031/32", "2032/33"}
    assert len(steps) == writer.pieces(sample) == 4
    before = len(fake.sent)
    again = writer.write(sample, "http://x/v1", "", "m", steps.append, known)
    assert again == out and len(fake.sent) == before                    # nothing asked twice


def test_an_empty_answer_is_an_error(monkeypatch):
    FakeEndpoint(monkeypatch, ["<think>only thinking</think>"])
    with pytest.raises(writer.WriterError, match="wrote nothing"):
        writer.chat("http://x/v1", "", "m", "s", {})


def test_comparison_is_spelt_out():
    a = {"club": "X", "competition": "L", "tier": 1, "position": 12, "points": 50}
    assert writer.comparison(a, dict(a, position=11, points=45)) == \
        "finished higher in the same division than the previous season, with fewer points"
    assert writer.comparison(a, dict(a, competition="M", tier=2)) == "played a division lower than the previous season"
    assert writer.comparison(a, dict(a, club="Y")) == "a different club from the previous season"
