"""Aggregate 2023 quote series privately and replay on the identical eligible sessions."""
import collections,csv,json,time
from quote_check import aggregate
from replay import PRIVATE,ROOT,MODES,signals,read_sessions,replay_day,summarize

minutes,_=read_sessions(2023)
quality={}
data=[]
for m in range(1,13):
    # A separate process may still be pulling the monthly public archives.
    archive=PRIVATE/f'xauusd_2023_{m:02d}_tick.json'
    if not archive.exists():
        raise RuntimeError(f'Missing published monthly download {m}')
    ord_month,dq=aggregate(m)
    data.extend(ord_month)
    quality[str(m)]=dq
    print('read',m,dq['all_quotes'],dq['eligible'],flush=True)
assert len(set(d for d,rows in data))==len(data)
data.sort(key=lambda d:d[0])
breaks={day:signals(bars) for day,bars in data}
overlap=collections.Counter()
for d,bars in data:
    if d not in minutes:continue
    overlap['common_sessions']+=1
    for tick,candle in zip(bars,minutes[d]):
        overlap['compared_ohlc']+=1
        if any(abs(a-b)>0.000001 for a,b in zip(tick[:4],candle)):
            overlap['ohlc_mismatches']+=1
overlap['only_candles']=len(set(minutes)-set(breaks))
overlap['only_ticks']=len(set(breaks)-set(minutes))
stats={}
with (ROOT/'daily_quote_results.csv').open('w',newline='') as f:
    writer=csv.writer(f)
    writer.writerow(['date','mode','slip_per_side','net_dollars','baskets','fills','turnover_oz','day_drawdown'])
    for mode in MODES:
        stats[mode]={}
        for slip in (0,.05,.25):
            rows=[(d,replay_day(d,bars,breaks[d],mode,None,slip)) for d,bars in data]
            stats[mode][str(slip)]=summarize(rows,slip==.05)
            for d,r in rows:
                writer.writerow([d,mode,slip,r['pnl'],r['baskets'],r['fills'],r['turnover_oz'],r['intraday_dd']])
out={'monthly_quality':quality,'minute_data_crosscheck':dict(overlap),'results':stats}
(ROOT/'quote_year_summary.json').write_text(json.dumps(out,indent=2)+'\n')
