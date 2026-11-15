"""Independently mark the frozen, private 2023 gold simulation at every quoted tick.

Run with python3 -B work/gold_intraday_check.py PATH_TO_FROZEN_GOLD_EXPERIMENT.
A 100% or 50% collateral hurdle is a sensitivity, not a broker margin schedule.
"""
import collections
import csv
import datetime as dt
import io
import json
import pathlib
import sys
import zipfile
from bisect import bisect_left

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from causal_stress import year_minutes
from replay import PRIVATE, SESSION, date_info, replay_day, signals


def quote_minute(day, clock):
    date, _dst = date_info(day)
    return date.toordinal() * 1440 + int(clock[:2]) * 60 + int(clock[2:4])


class FillTimes:
    def __init__(self, start, close_minute):
        self.start = start
        self.close_minute = close_minute
        self.items = []

    def writerow(self, row):
        _day, offset, event, quantity, price, _position, _equity = row
        minute = self.close_minute if offset == SESSION - 1 else self.start + offset
        self.items.append((minute, event, quantity, price))


def collect_trades():
    market, count = year_minutes()
    times = sorted(market)
    events = collections.defaultdict(list)
    expected_net = 0.0
    for offset in range(365):
        day = dt.date(2023, 1, 1) + dt.timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        _, dst = date_info(day.strftime('%Y%m%d'))
        start = day.toordinal() * 1440 + 480 - dst
        bars = [market.get(start + i) for i in range(SESSION)]
        close_minute = start + SESSION - 1
        if bars[-1] is None:
            idx = bisect_left(times, close_minute)
            if idx < len(times):
                close_minute = times[idx]
                bars[-1] = list(market[close_minute]) + [close_minute - start]
        fills = FillTimes(start, close_minute)
        summary = replay_day(day, bars, signals(bars), 'escalating', None, .05, fills)
        assert not summary['unresolved_oz']
        expected_net += summary['pnl']
        for minute, event, qty, price in fills.items:
            events[minute].append((day.isoformat(), event, qty, price))
    expected = json.loads((root / 'causal_summary.json').read_text())['results']['escalating']
    assert round(expected_net, 2) == round(expected['pnl'], 2)
    assert sum(map(len, events.values())) == expected['fills']
    return events, expected, count


def audit(events, expected, count):
    cash = peak = drawdown = max_notional = 0.0
    position = filled = observations = 0
    previous_minute = None
    worst_basket_mark = 0.0
    basket_cash = 0.0
    active_basket = False
    collateral = {ratio: {'max_starting_balance_needed': 0, 'breach_origination_days': {balance: set() for balance in (500, 2000, 10000)}} for ratio in (1.0, .5)}
    def observe(bid, ask, origin_day):
        nonlocal peak, drawdown, max_notional, worst_basket_mark
        mark = cash + position * (bid if position >= 0 else ask)
        peak = max(peak, mark)
        drawdown = max(drawdown, peak - mark)
        if active_basket:
            worst_basket_mark = min(worst_basket_mark, mark - basket_cash)
        if position:
            gross = abs(position) * (ask if position > 0 else bid)
            max_notional = max(max_notional, gross)
            for ratio, metrics in collateral.items():
                requirement = ratio * gross - mark
                metrics['max_starting_balance_needed'] = max(metrics['max_starting_balance_needed'], requirement)
                for balance, dates in metrics['breach_origination_days'].items():
                    if requirement > balance:
                        dates.add(origin_day)
    origin_day = None
    for month in range(1, 13):
        path = PRIVATE / f'xauusd_2023_{month:02d}_tick.zip'
        with zipfile.ZipFile(path) as archive, archive.open(next(name for name in archive.namelist() if name.endswith('.csv'))) as stream:
            for stamp, bid_raw, ask_raw, _volume in csv.reader(io.TextIOWrapper(stream, encoding='ascii')):
                day, clock = stamp.split()
                minute = quote_minute(day, clock)
                first = minute != previous_minute
                previous_minute = minute
                observations += 1
                if not position and not (first and minute in events):
                    continue
                bid, ask = float(bid_raw), float(ask_raw)
                observe(bid, ask, origin_day)
                if first and minute in events:
                    for origin_day, event, quantity, price in events.pop(minute):
                        assert abs(price - (ask + .05 if quantity > 0 else bid - .05)) < .00001
                        if event == 'signal' and not active_basket:
                            basket_cash = cash
                            active_basket = True
                        cash -= quantity * price
                        position += quantity
                        filled += 1
                        observe(bid, ask, origin_day)
                        if event != 'signal':
                            active_basket = False
    assert not events and position == 0 and observations == count and filled == expected['fills']
    assert abs(cash - expected['pnl']) < .001
    for metrics in collateral.values():
        metrics['max_starting_balance_needed'] = round(metrics['max_starting_balance_needed'], 2)
        metrics['breach_origination_days'] = {balance: len(days) for balance, days in metrics['breach_origination_days'].items()}
    return dict(quote_records=observations, modeled_fills=filled, final_net=round(cash, 2), tick_drawdown=round(drawdown, 2), minute_open_close_drawdown=expected['dd'], worst_open_or_closed_basket_mark=round(worst_basket_mark, 2), peak_net_position_notional=round(max_notional, 2), hypothetical_collateral=collateral)


if __name__ == '__main__':
    events, expected, count = collect_trades()
    result = audit(events, expected, count)
    print(json.dumps(result, indent=2))
