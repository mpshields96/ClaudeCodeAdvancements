"""Check future-availability selection using chronological waits for actual quotes."""
from bisect import bisect_left
import collections,csv,datetime as dt,io,json,hashlib,zipfile
from replay import PRIVATE,ROOT,MODES,SESSION,date_info,signals,replay_day,summarize

def year_minutes():
    bars = {}
    n = 0
    for m in range(1,13):
        p=PRIVATE/f'xauusd_2023_{m:02d}_tick.zip'
        assert hashlib.sha256(p.read_bytes()).hexdigest()==json.loads(p.with_suffix('.json').read_text())['sha256']
        with zipfile.ZipFile(p) as z,z.open(next(n for n in z.namelist() if n.endswith('.csv'))) as f:
            for stamp,bid,ask,_v in csv.reader(io.TextIOWrapper(f,encoding='ascii')):
                day,clock=stamp.split()
                date,_dst=date_info(day)
                key=date.toordinal()*1440+int(clock[:2])*60+int(clock[2:4])
                bid,ask=float(bid),float(ask)
                if not 0 < bid <= ask:raise RuntimeError(f'Invalid quote {stamp}')
                sp=round(ask-bid,6)
                b=bars.get(key)
                if b is None:
                    bars[key]=[bid,bid,bid,bid,sp,sp]
                else:
                    b[1]=max(b[1],bid)
                    b[2]=min(b[2],bid)
                    b[3]=bid
                    b[5]=sp
                n+=1
    return bars,n

def main():
    market,count=year_minutes()
    times=sorted(market)
    data=[]
    for offset in range(365):
        day=dt.date(2023,1,1)+dt.timedelta(days=offset)
        if day.weekday()>4:continue
        _,dst=date_info(day.strftime('%Y%m%d'))
        start=day.toordinal()*1440+480-dst
        slots=[market.get(t) for t in range(start,start+SESSION)]
        complete=all(x is not None for x in slots)
        observed=sum(x is not None for x in slots)
        delayed=0
        if slots[-1] is None:
            i=bisect_left(times,start+475)
            if i<len(times):
                key=times[i]
                delayed=key-start-475
                slots[-1]=list(market[key])+[key-start]
        data.append((day,slots,signals(slots),complete,observed,delayed))
    out={'quote_count':count,'scheduled_days':len(data),'with_any_session_quote':sum(1 for x in data if x[4]),'coverage_counts':{},'results':{}}
    gold=json.loads((ROOT/'quote_year_summary.json').read_text())['results']
    for month in range(1,13):
        selected=[r for r in data if r[0].month==month]
        out['coverage_counts'][month]={'scheduled':len(selected),'any':sum(x[4]>0 for x in selected),'complete':sum(x[3] for x in selected)}
    with (ROOT/'daily_causal_results.csv').open('w',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['day','mode','observed_minutes','net_dollars','baskets','fills','gap_exits','max_blind_hold_minutes','delayed_clock_exit_minutes'])
        for mode in MODES:
            rows=[]
            incomplete=[]
            complete_rows=[]
            unresolved=[]
            for day,bars,breaks,complete,observed,delayed in data:
                r=replay_day(day,bars,breaks,mode,None,.05)
                if r.get('unresolved_basket'):
                    unresolved.append((str(day),r['unresolved_oz']))
                    continue
                rows.append((day,r))
                (complete_rows if complete else incomplete).append((day,r))
                writer.writerow([day,mode,observed,r['pnl'],r['baskets'],r['fills'],r['gap_exits_with_exposure'],r['max_blind_hold_minutes'],r['eod_delay_if_exposed']])
            s=summarize(rows,True)
            s['unresolved_positions']=unresolved
            s['on_incomplete_days']=summarize(incomplete,False)
            s['on_complete_days']=summarize(complete_rows,False)
            s['exact_match_previous_complete_subset']=all(s['on_complete_days'][k]==v for k,v in gold[mode]['0.05'].items() if k not in ('weekly_block_mean_95','execution_cost_vs_mid'))
            assert s['exact_match_previous_complete_subset']
            s['gap_exits_with_exposure']=sum(r['gap_exits_with_exposure'] for _,r in rows)
            s['max_blind_hold_minutes']=max(r['max_blind_hold_minutes'] for _,r in rows)
            s['delayed_eod_exits_with_exposure']=sum(r['eod_delay_if_exposed']>0 for _,r in rows)
            s['max_eod_delay_minutes']=max(r['eod_delay_if_exposed'] for _,r in rows)
            out['results'][mode]=s
    (ROOT/'causal_summary.json').write_text(json.dumps(out,indent=2)+'\n')
    print('scheduled',len(data),'quotes',count,flush=True)
if __name__=='__main__':main()
