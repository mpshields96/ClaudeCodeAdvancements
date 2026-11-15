"""Reproduce the preregistered gold proxy experiment. stdlib only, Python 3.9+."""
import collections
import csv
import datetime as dt
import functools
import hashlib
import io
import json
import math
import pathlib
import random
import statistics
import zipfile
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
PRIVATE = ROOT / 'private'
YEARS = (2021, 2022, 2023)
MODES = ('cash', 'single', 'fixed', 'escalating', 'alternating')
COSTS = {'zero': (0, 0), 'base': (.30, .05), 'double': (.60, .10), 'severe': (1.00, .25)}
US_EASTERN = ZoneInfo('America/New_York')
SESSION = 476
SWING = 6

@functools.lru_cache(maxsize=1200)
def date_info(day):
    date = dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    dst_minutes = int(dt.datetime.combine(date, dt.time(12), US_EASTERN).dst().total_seconds() / 60)
    return date, dst_minutes

def read_sessions(year):
    archive = PRIVATE / f'xauusd_{year}_M1.zip'
    receipt = json.loads(archive.with_suffix('.json').read_text())
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == receipt['sha256']
    by_day = {}
    bad_day = set()
    dq = collections.Counter()
    first = last = None
    prev = None
    with zipfile.ZipFile(archive) as z, z.open(next(n for n in z.namelist() if n.endswith('.csv'))) as f:
        for stamp, o, h, l, c, v in csv.reader(io.TextIOWrapper(f, encoding='ascii'), delimiter=';'):
            day, clock = stamp.split()
            dq['rows'] += 1
            if first is None: first = stamp
            last = stamp
            if prev and stamp <= prev: dq['nonincreasing_rows_archive'] += 1
            prev = stamp
            date, dst_minutes = date_info(day)
            minute = int(clock[:2])*60 + int(clock[2:4]) + dst_minutes - 480
            if date.weekday() > 4 or not 0 <= minute < SESSION: continue
            dq['session_rows'] += 1
            values = tuple(map(float, (o, h, l, c)))
            op, high, low, close = values
            slot = by_day.setdefault(date, {})
            if minute in slot or clock[4:] != '00' or not all(math.isfinite(v) and v>0 for v in values) or low > min(op,close) or high < max(op,close):
                bad_day.add(date)
            slot[minute] = values
    use = {day: [bars[k] for k in range(SESSION)] for day, bars in by_day.items() if len(bars)==SESSION and day not in bad_day}
    weekdays = [dt.date(year,1,1) + dt.timedelta(days=i) for i in range((dt.date(year+1,1,1)-dt.date(year,1,1)).days)]
    weekdays = [d for d in weekdays if d.weekday()<5]
    dq['calendar_weekdays'] = len(weekdays)
    dq['days_no_rows'] = len(set(weekdays)-set(by_day))
    dq['days_incomplete'] = sum(len(bars)<SESSION for bars in by_day.values())
    dq['days_invalid_or_duplicate'] = len(bad_day)
    dq['included_days'] = len(use)
    return use, {**dq, 'first_label_fixed_EST':first, 'last_label_fixed_EST':last, 'sha256':receipt['sha256']}

def signals(minutes):
    agg = []
    out = {}
    last_high = last_low = None
    for start in range(0,475,5):
        chunk = minutes[start:start+5]
        if any(b is None for b in chunk):
            agg = []
            last_high = last_low = None
            continue
        bar = (chunk[0][0], max(b[1] for b in chunk), min(b[2] for b in chunk), chunk[-1][3])
        agg.append(bar)
        if len(agg) < SWING*2+1: continue
        window = agg[-(SWING*2+1):]
        p = window[SWING]
        neighbors = window[:SWING] + window[SWING+1:]
        if p[1] > max(b[1] for b in neighbors): last_high = p[1]
        if p[2] < min(b[2] for b in neighbors): last_low = p[2]
        up = last_high is not None and bar[3] > last_high
        down = last_low is not None and bar[3] < last_low
        if up: last_high = None
        if down: last_low = None
        if up != down: out[start+4] = 1 if up else -1
    return out

def replay_day(day, minutes, breaks, mode, spread, slip, writer=None):
    cash = 0.0
    position = 0
    legs = []
    basket_base = 0.0
    fills = 0
    baskets = 0
    turnover = 0
    execution_cost = 0.0
    peak = 0.0
    dd = 0.0
    trough = 0.0
    max_pos = 0
    exits = collections.Counter()
    pending = None
    last_fresh = None
    gap_exit_count = 0
    max_blind_hold_minutes = 0
    eod_delay_if_exposed = 0
    def mark(bid, current_spread):
        return cash + position * (bid + (current_spread if position < 0 else 0))
    def register_equity(val):
        nonlocal peak, dd, trough
        peak = max(peak,val)
        dd = max(dd,peak-val)
        trough = min(trough,val)
    def transact(q, bid, current_spread, t, event):
        nonlocal position,cash,turnover,fills,max_pos,execution_cost
        if not q: return
        price=bid+current_spread+slip if q>0 else bid-slip
        cash -= q*price
        position += q
        turnover += abs(q)
        execution_cost += abs(q) * (current_spread / 2 + slip)
        fills += 1
        max_pos=max(max_pos,abs(position))
        if writer:
            writer.writerow([str(day),t,event,q,round(price,6),position,round(mark(bid,current_spread),6)])
    for t,bar in enumerate(minutes):
        if bar is None:
            if pending and pending[0] == 'entry':
                pending = None
            if legs and not pending:
                pending = ('exit','gap')
            continue
        actual_t = bar[6] if len(bar) > 6 else t
        if position and last_fresh is not None and actual_t > last_fresh + 1:
            gap_exit_count += 1
            max_blind_hold_minutes = max(max_blind_hold_minutes, actual_t - last_fresh)
        if t==475 and position and actual_t > 475:
            eod_delay_if_exposed = actual_t - 475
        last_fresh = actual_t
        op,high,low,close=bar[:4]
        open_spread,close_spread = bar[4:6] if spread is None else (spread,spread)
        register_equity(mark(op,open_spread))
        if (pending and pending[0]=='exit') or (t==475 and legs):
            reason = pending[1] if pending and pending[0]=='exit' else 'clock'
            transact(-position,op,open_spread,t,reason)
            exits[reason] += 1
            baskets += 1
            legs=[]
            basket_base=cash
        elif pending and t<475:
            direction,qty=pending[1],pending[2]
            if not legs:basket_base=cash
            transact(direction*qty,op,open_spread,t,'signal')
            legs.append(direction)
        pending=None
        register_equity(mark(op,open_spread))
        if t==475:break
        val=mark(close,close_spread)
        register_equity(val)
        if mode=='cash':continue
        pnl=round(val-basket_base,8)
        if legs and (pnl>=3 or pnl<=-6):
            pending=('exit','target' if pnl>=3 else 'stop')
            continue
        direction=breaks.get(t,0)
        if not direction or t==474:continue
        cap=1 if mode=='single' else 3
        if len(legs)>=cap:continue
        if mode=='alternating' and legs and direction==legs[-1]:continue
        qty=2**len(legs) if mode in ('escalating','alternating') else 1
        pending=('entry',direction,qty)
    if position or legs:
        return {'unresolved_oz':position,'unresolved_basket':True}
    return {'unresolved_oz':0,'gap_exits_with_exposure':gap_exit_count,'max_blind_hold_minutes':max_blind_hold_minutes,'eod_delay_if_exposed':eod_delay_if_exposed,'pnl':round(cash,6),'baskets':baskets,'fills':fills,'turnover_oz':turnover,'execution_cost':round(execution_cost,6),'peak':round(peak,6),'trough':round(trough,6),'intraday_dd':round(dd,6),'max_net_oz':max_pos,'exits':dict(exits)}

def interval(rows):
    weeks=collections.defaultdict(list)
    for date, r in rows:
        weeks[date.isocalendar()[:2]].append(r['pnl'])
    weeks=[(sum(v),len(v)) for v in weeks.values()]
    r=random.Random(20261115)
    sims=[]
    for _ in range(4000):
        sample=r.choices(weeks,k=len(weeks))
        sims.append(sum(x[0] for x in sample)/sum(x[1] for x in sample))
    sims.sort()
    return [round(sims[99],4), round(sims[3899],4)]

def summarize(rows,with_ci):
    pnl=[r['pnl'] for _,r in rows]
    peak=equity=dd=0.0
    for _,r in rows:
        dd=max(dd,r['intraday_dd'],peak-(equity+r['trough']))
        peak=max(peak,equity+r['peak'])
        equity+=r['pnl']
    s={'days':len(rows),'pnl':round(sum(pnl),4),'mean':round(statistics.mean(pnl),4),'median':round(statistics.median(pnl),4),'worst':min(pnl),'best':max(pnl),'positive_days':sum(x>0 for x in pnl),'no_fill_days':sum(r['fills']==0 for _,r in rows),'dd':round(dd,4),'max_net_oz':max(r['max_net_oz'] for _,r in rows)}
    for name in ['baskets','fills','turnover_oz']:s[name]=sum(r[name] for _,r in rows)
    s['execution_cost_vs_mid']=round(sum(r['execution_cost'] for _,r in rows),4)
    if with_ci:s['weekly_block_mean_95']=interval(rows)
    return s

def main():
    final = {'protocol_sha256':hashlib.sha256((ROOT/'PREREGISTRATION.md').read_bytes()).hexdigest(),'quality':{},'results':{}}
    with (PRIVATE/'final_base_fills.csv').open('w',newline='') as fill_file, (ROOT/'daily_results.csv').open('w',newline='') as ledger:
        detail=csv.writer(fill_file)
        detail.writerow(['date','mode','minute_from_0800_ET','event','signed_oz','modeled_fill','net_oz','marked_day_pnl'])
        daily=csv.writer(ledger)
        daily.writerow(['date','mode','cost','net_dollars','baskets','fills','turnover_oz','marked_day_drawdown'])
        for year in YEARS:
            sessions,dq=read_sessions(year)
            final['quality'][year]=dq
            ordered=sorted(sessions.items())
            breaks={d:signals(rows) for d,rows in ordered}
            final['results'][year]={}
            for mode in MODES:
                final['results'][year][mode]={}
                for cost,(spread,slip) in COSTS.items():
                    all_rows=[]
                    for day,minutes in ordered:
                        class Detail:
                            @staticmethod
                            def writerow(row):
                                detail.writerow([row[0],mode,*row[1:]])
                        writer=Detail if year==2023 and cost=='base' else None
                        r=replay_day(day,minutes,breaks[day],mode,spread,slip,writer)
                        daily.writerow([day,mode,cost,r['pnl'],r['baskets'],r['fills'],r['turnover_oz'],r['intraday_dd']])
                        all_rows.append((day,r))
                    final['results'][year][mode][cost]=summarize(all_rows,cost=='base')
            print(year, dq['included_days'], flush=True)
    (ROOT/'summary.json').write_text(json.dumps(final,indent=2)+'\n')
if __name__=='__main__': main()
