"""Run the frozen supplementary January replay with actual bid and ask."""
import collections,csv,datetime as dt,hashlib,io,json,pathlib,statistics,zipfile
from replay import PRIVATE,ROOT,SESSION,MODES,date_info,read_sessions,replay_day,signals,summarize

def aggregate(month=1):
    p=PRIVATE/f'xauusd_2023_{month:02d}_tick.zip'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==json.loads(p.with_suffix('.json').read_text())['sha256']
    results={}
    spreads=collections.defaultdict(collections.Counter)
    counts=collections.Counter()
    first=None
    last=None
    bad_days=set()
    previous=''
    with zipfile.ZipFile(p) as z, z.open(next(n for n in z.namelist() if n.endswith('.csv'))) as f:
        for stamp,bid,ask,_v in csv.reader(io.TextIOWrapper(f,encoding='ascii')):
            day,clock=stamp.split()
            counts['all_quotes']+=1
            first=first or stamp
            last=stamp
            date,dst=date_info(day)
            t=int(clock[:2])*60+int(clock[2:4])+dst-480
            if date.weekday()>=5 or not 0<=t<SESSION:continue
            counts['session_quotes']+=1
            # Simultaneous ticks are in file order. Refuse reversals or crossed quotes.
            if stamp<previous or float(ask)<float(bid) or float(bid)<=0:bad_days.add(date)
            previous=stamp
            bid,ask=float(bid),float(ask)
            spread=round(ask-bid,6)
            minutes=results.setdefault(date,{})
            spreads[date][spread]+=1
            if t not in minutes:
                minutes[t]=[bid,bid,bid,bid,spread,spread]
            else:
                b=minutes[t]
                b[1]=max(b[1],bid)
                b[2]=min(b[2],bid)
                b[3]=bid
                b[5]=spread
    accepted={day:[m[t] for t in range(SESSION)] for day,m in results.items() if len(m)==SESSION and day not in bad_days}
    ordered=sorted(accepted.items())
    firstday=ordered[0][0] if ordered else None
    freqs=spreads[firstday] if firstday else {}
    n=sum(freqs.values())
    def percentile(prob):
        total=0
        for x,ng in sorted(freqs.items()):
            total+=ng
            if total>=prob*n:return x
    first_stats={'date':str(firstday),'quotes':n,'spread_usd_per_oz_median':percentile(.5),'spread_usd_per_oz_p95':percentile(.95),'spread_usd_per_oz_max':max(freqs)} if n else None
    dq={**counts,'first_stamp_EST':first,'last_stamp_EST':last,'eligible':len(ordered), 'with_any':len(results),'invalid_dates':sorted(map(str,bad_days)),'first_day_quote_spreads':first_stats}
    return ordered,dq

def main():
    ordered,dq=aggregate()
    all_minute,_=read_sessions(2023)
    compare=collections.Counter()
    for day,ticks in ordered:
        if day not in all_minute:continue
        compare['overlap_days']+=1
        for a,b in zip(ticks,all_minute[day]):
            compare['compared_minutes']+=1
            if any(abs(x-y)>0.000001 for x,y in zip(a[:4],b)):compare['disagreeing_bid_ohlc']+=1
    results={}
    for mode in MODES:
        results[mode]={}
        for slip in (0,.05,.25):
            rows=[(d,replay_day(d,minutes,signals(minutes),mode,None,slip)) for d,minutes in ordered]
            results[mode][str(slip)]=summarize(rows,False)
    out={'quality':dq,'minute_data_crosscheck':compare,'results':results}
    (ROOT/'quote_summary.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dq))
if __name__=='__main__':main()
