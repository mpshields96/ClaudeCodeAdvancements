"""Retrieve the twelve published XAU/USD tick archives once, in sequence."""
import hashlib
import json
import pathlib
import time

from fetch import download

root = pathlib.Path(__file__).resolve().parent / 'private'
for month in range(1, 13):
    archive = root / f'xauusd_2023_{month:02d}_tick.zip'
    receipt = archive.with_suffix('.json')
    if archive.is_file() and receipt.is_file():
        recorded = json.loads(receipt.read_text())['sha256']
        if hashlib.sha256(archive.read_bytes()).hexdigest() == recorded:
            continue
    download(2023, month)
    time.sleep(1)
