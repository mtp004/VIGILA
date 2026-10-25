"""Run: python -m pytest test_auto_trigger.py"""
from datetime import date, timedelta

from auto_trigger import (alert_group_key, build_series, compute_trigger, count_episodes, effective_trigger,
                          window_maxima)


def test_lingering_deal_counts_once():
    assert count_episodes([9, 9, 9, None, 9, 5, 9], 9) == 3
    assert count_episodes([9.0] * 65, 9) == 1


def test_series_skips_days_without_runs_and_starts_at_first_record():
    days = [date(2026, 1, 1) + timedelta(i) for i in range(6)]
    run_days = days[:2] + days[3:]                     # scraper down on day 3
    best = {days[1]: 9.0, days[4]: 7.0}                # day 1 not yet tracked; day 6 ran, no rows
    assert build_series(run_days, best) == [9.0, None, 7.0, None]
    assert build_series(run_days, best, since=days[4]) == [7.0, None]   # lookback cutoff


def test_window_maxima():
    series = [5, 9, None, 6, 7, None, 8, 5, 6, 4]
    assert window_maxima(series, 3) == [9, 9, 7, 7, 8, 8, 8, 6]
    assert window_maxima([None, None, 3], 2) == [float("-inf"), 3]


def test_worked_example():
    # 3-day windows; maxima 9,9,7,7,8,8,8,6 -> 7 of 8 windows reach 7%
    series = [5, 9, None, 6, 7, None, 8, 5, 6, 4]
    assert compute_trigger(series, 3) == {
        "computedTrigger": 7, "episodes": 3, "historyDays": 10, "autoStatus": "active"}


def test_flat_price_is_one_episode():
    # Always available, but a single unbroken run never meets MIN_EPISODES
    assert compute_trigger([5.0] * 90, 30)["autoStatus"] == "insufficient_data"


def test_single_spike_is_blocked():
    series = [None] * 60
    series[30] = 9.0                                   # in ~97% of windows, but only once
    assert compute_trigger(series, 30)["autoStatus"] == "insufficient_data"


def test_collecting_until_two_t_days():
    assert compute_trigger([9.0] * 59, 30)["autoStatus"] == "collecting"


def test_effective_trigger_falls_back_to_manual():
    alert = {"minDiscountPercent": 8, "computedTrigger": 9.4, "autoStatus": "active"}
    assert effective_trigger(alert, "1m") == 9.4
    assert effective_trigger(alert, "manual") == 8.0
    assert effective_trigger({**alert, "autoStatus": "collecting"}, "3m") == 8.0


def test_group_key():
    url_to_brand = {"https://gcx.app/x": "x", "https://cardcash.com/x": "x", "https://carddepot.com/y": "y"}
    alert = {"minCardValue": 20, "maxCardValue": 100,
             "urls": {"gcx": "https://gcx.app/x/", "cardcash": "https://CardCash.com/x", "carddepot": "https://carddepot.com/y"},
             "platforms": {"gcx": {"active": True}, "cardcash": {"active": True}, "carddepot": {"active": False}}}
    assert alert_group_key(alert, url_to_brand) == ("x", 20.0, 100.0, ("cardcash", "gcx"))
    alert["platforms"]["carddepot"]["active"] = True   # now maps to two brands
    assert alert_group_key(alert, url_to_brand) is None
