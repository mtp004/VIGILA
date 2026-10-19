"""Run: python -m pytest test_auto_trigger.py"""
import math
from datetime import date, timedelta

import pytest

from auto_trigger import (MIN_EPISODES, alert_group_key, build_series, compute_trigger,
                          count_episodes, effective_trigger, required_rate)


def days(n, start=date(2026, 1, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def test_required_rate():
    assert required_rate(30) == pytest.approx(-math.log(0.2) / 30)


def test_lingering_deal_counts_once():
    assert count_episodes([9, 9, 9, None, 9, 5, 9], 9) == 3
    assert count_episodes([9, 9, 9, None, 9, 5, 9], 5) == 2


def test_missing_run_days_are_bridged_not_breaks():
    run_days = days(5)
    del run_days[2]                              # scraper down on day 3
    best = {d: 9.0 for d in run_days}
    series = build_series(run_days, best)
    assert series == [9.0] * 4                   # 4 history days, not 5
    assert count_episodes(series, 9) == 1


def test_run_day_without_brand_rows_is_no_deal():
    run_days = days(4)
    best = {run_days[0]: 7.0, run_days[1]: None, run_days[3]: 7.0}   # day 3: ran, nothing for brand
    assert build_series(run_days, best) == [7.0, None, None, 7.0]


def test_history_starts_at_group_first_day():
    run_days = days(10)
    best = {d: 5.0 for d in run_days[6:]}
    assert len(build_series(run_days, best)) == 4
    assert build_series(run_days, {}) == []


def test_collecting_until_two_t_days():
    result = compute_trigger([9.0, None] * 29, 30)  # 58 days < 60
    assert result["autoStatus"] == "collecting"
    assert result["computedTrigger"] is None
    assert result["historyDays"] == 58


def test_picks_highest_x_meeting_rate():
    # 60 days. 10% hit twice (too rare), 8% hit 5 times, 5% always.
    series = [5.0] * 60
    for i in (3, 40):
        series[i] = 10.0
    for i in (10, 20, 30, 50, 55):
        series[i] = 8.0
    # λ* for 1m ≈ 0.0536/day → need ≥ 3.22 episodes in 60 days
    result = compute_trigger(series, 30)
    assert result == {"computedTrigger": 8.0, "episodes": 7, "historyDays": 60, "autoStatus": "active"}


def test_always_available_deal_is_one_episode():
    # A deal that never goes away is a single episode, so it can't meet the rate
    assert compute_trigger([5.0] * 60, 30)["autoStatus"] == "insufficient_data"


def test_no_deals_is_insufficient():
    assert compute_trigger([None] * 200, 90)["autoStatus"] == "insufficient_data"


def test_min_episodes_guardrail(monkeypatch):
    # 2 episodes in 60 days clears a lowered rate, but not the episode minimum
    import auto_trigger
    monkeypatch.setattr(auto_trigger, "CONFIDENCE", 0.5)
    series = [None] * 60
    series[5] = series[30] = 9.0
    assert 2 / 60 >= auto_trigger.required_rate(30)
    assert MIN_EPISODES == 3
    assert compute_trigger(series, 30)["autoStatus"] == "insufficient_data"


def test_effective_trigger():
    alert = {"minDiscountPercent": 8, "computedTrigger": 9.4, "autoStatus": "active"}
    assert effective_trigger(alert, "1m") == (9.4, True)
    assert effective_trigger(alert, "manual") == (8.0, False)
    assert effective_trigger({**alert, "autoStatus": "collecting"}, "3m") == (8.0, False)
    assert effective_trigger({"minDiscountPercent": 8}, "6m") == (8.0, False)


def test_group_key_sorts_platforms_and_requires_one_brand():
    url_to_brand = {"https://gcx.app/buy-x": "x", "https://cardcash.com/x": "x", "https://carddepot.com/y": "y"}
    alert = {"minCardValue": 20, "maxCardValue": 100,
             "urls": {"gcx": "https://gcx.app/buy-x/", "cardcash": "https://CardCash.com/x", "carddepot": ""},
             "platforms": {"gcx": {"active": True}, "cardcash": {"active": True}, "carddepot": {"active": False}}}
    assert alert_group_key(alert, url_to_brand) == ("x", 20.0, 100.0, ("cardcash", "gcx"))

    mixed = {**alert, "urls": {**alert["urls"], "carddepot": "https://carddepot.com/y"},
             "platforms": {**alert["platforms"], "carddepot": {"active": True}}}
    assert alert_group_key(mixed, url_to_brand) is None

    unmapped = {**alert, "urls": {**alert["urls"], "gcx": "https://gcx.app/other"}}
    assert alert_group_key(unmapped, url_to_brand) is None
