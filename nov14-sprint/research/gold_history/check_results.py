"""Cross-check net cash, per-session returns and end positions from the final simulated fills."""
import collections,csv,datetime as dt,json
from decimal import Decimal
from replay import PRIVATE,ROOT,YEARS,MODES,signals,replay_day

def assert_cash_rolls():
    groups={}
    with (PRIVATE/'final_base_fills.csv').open() as f:
        for row in csv.DictReader(f):
            group=(row['date'],row['mode'])
            cash,pos,total=groups.get(group,(Decimal(0),0,0))
            qty=int(row['signed_oz'])
            pos+=qty
            cash-=qty*Decimal(row['modeled_fill'])
            assert pos==int(row['net_oz']) and abs(pos)<=7
            groups[group]=(cash,pos,total+1)
    checked=0
    with (ROOT/'daily_results.csv').open() as f:
        for row in csv.DictReader(f):
            if not row['date'].startswith('2023') or row['cost']!='base':continue
            cash,pos,n=groups.get((row['date'],row['mode']),(Decimal(0),0,0))
            assert pos==0 and cash==Decimal(row['net_dollars']) and n==int(row['fills'])
            checked+=1
    return checked,sum(n for cash,pos,n in groups.values())

def timing():
    # One clear swing high centered at five-minute bar 6. Bars 7–12 cannot break it by definition.
    candles=[]
    for i in range(95):
        o,c=100,100
        h=103 if i==6 else 101
        if i==13:c=104; h=105
        for j in range(5):
            candles.append((o,h,99,c if j==4 else 100))
    candles.append((101,101,101,101))
    sig=signals(candles)
    assert sig=={69:1},sig
    class Log:
        fills=[]
        @classmethod
        def writerow(cls,row):
            cls.fills.append(row)
    r=replay_day(dt.date(2023,1,3),candles,sig,'single',.30,.05,Log)
    assert Log.fills[0][1:5]==[70,'signal',1,100.35]
    assert Log.fills[-1][1:5]==[475,'clock',-1,100.95]
    assert r['pnl']==.60 and r['fills']==2

if __name__=='__main__':
    timing()
    print('Decimal reconciliation; mode-days and fills',assert_cash_rolls())
