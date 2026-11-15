"""Fetch the public nflverse tables with provenance in the private scratch directory."""
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from datetime import datetime, timezone

folder=Path(__file__).parent/'private'
folder.mkdir(exist_ok=True)
root='https://github.com/nflverse/nflverse-data/releases/download/'
paths=['players/players.csv.gz']
for season in (2024,2025,2026):
    paths.extend([f'snap_counts/snap_counts_{season}.csv.gz', f'stats_player/stats_player_week_{season}.csv.gz'])

def fetch(remote):
    url=root+remote
    with urlopen(url,timeout=30) as response:
        raw=response.read()
    path=folder/remote.split('/')[-1]
    path.write_bytes(raw)
    return {'name':path.name,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
with ThreadPoolExecutor(max_workers=4) as pool:
    manifest=list(pool.map(fetch,paths))
(folder/'manifest.json').write_text(json.dumps({'retrieved_utc':datetime.now(timezone.utc).isoformat(),'files':manifest},indent=2))
