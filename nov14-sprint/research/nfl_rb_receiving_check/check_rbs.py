"""Registered, week-ordered forecast test for 22.5 receiving yards conditional on taking an offensive snap."""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'private'
checks = Counter()
def rows(name):
    with gzip.open(RAW / (name + '.csv.gz'), 'rt') as stream:
        return list(csv.DictReader(stream))

def unique_ids():
    refs = defaultdict(set)
    for row in rows('players'):
        if row['gsis_id'] and row['pfr_id']:
            refs[row['pfr_id']].add(row['gsis_id'])
    return {key: next(iter(ids)) for key, ids in refs.items() if len(ids)==1}

def appearances(year, ids):
    maxweek = 9 if year == 2026 else 18
    stats = {}
    coverage = Counter()
    for r in rows(f'stats_player_week_{year}'):
        if r['season_type'] != 'REG' or int(r['week']) > maxweek:
            continue
        k = (r['game_id'],r['team'],r['player_id'])
        assert k not in stats, k
        stats[k] = r
        coverage[k[:2]] += 1
    games = defaultdict(set)
    weeks = defaultdict(dict)
    for r in rows(f'snap_counts_{year}'):
        week = int(r['week'])
        if r['game_type'] != 'REG' or week > maxweek:
            continue
        games[week].add(r['team'])
        if r['position'] not in ('RB','HB') or int(float(r['offense_snaps'] or 0)) < 1:
            continue
        checks['positive_snap_rows'] += 1
        if (r['game_id'],r['team']) not in coverage:
            checks['absent_stat_team_game'] += 1
            continue
        gsis = ids.get(r['pfr_player_id'])
        if not gsis:
            checks['unmapped_or_ambiguous'] += 1
            continue
        stat = stats.get((r['game_id'],r['team'],gsis))
        if not stat:
            checks['inferred_zero_no_stat_line'] += 1
        elif not stat['targets'] or not stat['receiving_yards']:
            checks['missing_numeric_with_stat_line'] += 1
            continue
        yards = int(float(stat['receiving_yards'])) if stat else 0
        targets = int(float(stat['targets'])) if stat else 0
        if targets == 0 and yards > 0:
            checks['positive_official_yards_zero_targets'] += 1
        assert gsis not in weeks[week], (gsis,week)
        weeks[week][gsis] = (week, r['team'], targets, yards, r['player'])
    return weeks, games

def role(history):
    avg = statistics.mean(x[2] for x in history[-5:])
    return 'under_one' if avg<1 else 'one_to_under_three' if avg<3 else 'three_plus'

def probs(history, counts):
    bucket = role(history)
    def rate(pair):
        hit, n = pair
        return (hit + .5) / (n + 1)
    def last(n):
        h=history[-n:]
        return rate((sum(x[3]>22.5 for x in h),len(h)))
    prior=rate(counts[bucket])
    recent=history[-10:]
    return {'base':rate(counts['all']), 'last5':last(5),'last10':last(10),'role':prior,
            'shrunken':(sum(x[3]>22.5 for x in recent)+5*prior)/(len(recent)+5)}

def brier(p,y):return (p-y)**2
def logloss(p,y):return -math.log(p if y else 1-p)
def score(forecasts):
    result = {}
    weeks=sorted({r[0] for r in forecasts})
    rng=random.Random(20261115)
    # Sample consecutive pairs of adjacent observed weeks (circular moving blocks).
    draws=[]
    for _ in range(5000):
        block=[]
        while len(block)<len(weeks):
            i=rng.randrange(len(weeks))
            block.extend([weeks[i],weeks[(i+1)%len(weeks)]])
        draws.append(block[:len(weeks)])
    for name in forecasts[0][2]:
        by_week=defaultdict(list)
        for w,_pid,p,y in forecasts:
            by_week[w].append(brier(p[name],y)-brier(p['base'],y))
        total={w:sum(vals) for w,vals in by_week.items()}
        ci=sorted(sum(total[w] for w in draw)/sum(len(by_week[w]) for w in draw) for draw in draws)
        result[name]={'brier':round(statistics.mean(brier(p[name],y) for _,_,p,y in forecasts),5),
                      'logloss':round(statistics.mean(logloss(p[name],y) for _,_,p,y in forecasts),5),
                      'brier_diff_vs_base_95': [round(ci[124],5),round(ci[4874],5)]}
    return result
def main():
    ids=unique_ids()
    counts=defaultdict(lambda:[0,0])
    forecasts=[]
    without=0
    train=0
    for year in (2024,2025,2026):
        history=defaultdict(list)
        weeks,games=appearances(year,ids)
        for week,current in sorted(weeks.items()):
            observed=[]
            for gsis,h in history.items():
                if len(h)<2 or week-h[-1][0]>4:
                    continue
                if gsis not in current:
                    if year==2026 and h[-1][1] in games[week]:
                        without+=1
                    continue
                y=int(current[gsis][3]>22.5)
                if year==2026:
                    forecasts.append((week,gsis,probs(h,counts),y))
                else:
                    train+=1
                observed.append((role(h),y))
            for group,y in observed:
                for selected in ('all',group):
                    counts[selected][0]+=y
                    counts[selected][1]+=1
            for gsis,appearance in current.items():
                history[gsis].append(appearance)
    bands = []
    for low,high in ((0,.25),(.25,.5),(.5,.6),(.6,.75),(.75,1.01)):
        group = [(p['shrunken'],y) for _,_,p,y in forecasts if low<=p['shrunken']<high]
        if group:
            bands.append({'lower':low,'upper':high,'rows':len(group),'predicted':round(statistics.mean(p for p,y in group),3),'over':sum(y for p,y in group)})
    warren=next(h for h in history.values() if h[-1][4]=='Jaylen Warren')
    observations=[(w,yd) for w,_team,_tar,yd,_name in warren]
    out={'protocol_sha256':hashlib.sha256((ROOT/'protocol.md').read_bytes()).hexdigest(),'qc':dict(checks),
         'calibration_rows_2024_25':train,'eval_weeks':sorted({x[0] for x in forecasts}),
         'evaluation_rows':len(forecasts),'unique_2026_rbs':len({r[1] for r in forecasts}),
         'prior_eligible_without_qualified_appearance_on_old_team_game_week':without,
         'calibration_bands_post_test_diagnostic':bands,
         'positives':sum(r[3] for r in forecasts),'scores':score(forecasts),
         'warren_appearances_by_week_and_yards':observations,
         'warren_conditional_recent_rates':{str(n):[sum(r[3]>22.5 for r in warren[-n:]),len(warren[-n:])] for n in (5,10)},
         'warren_week10_model_forecasts':probs(warren,counts)}
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
