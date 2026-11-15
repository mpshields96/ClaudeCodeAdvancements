"""Fetch a public HistData download form as supplied by its publisher. No login or raw data distribution."""
import argparse, datetime, hashlib, http.cookiejar, json, pathlib, urllib.parse, urllib.request, zipfile
from html.parser import HTMLParser

class PublicDownload(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action=None
        self.fields={}
        self.active=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='form':
            self.active=a.get('id')=='file_down'
            if self.active:
                assert a.get('method','').upper()=='POST'
                self.action=a['action']
        elif self.active and tag=='input' and a.get('name'):
            self.fields[a['name']]=a.get('value','')
    def handle_endtag(self,tag):
        if tag=='form':self.active=False

def download(year, tick_month=None):
    root=pathlib.Path(__file__).resolve().parent/'private'
    root.mkdir(exist_ok=True)
    period=str(year) if tick_month is None else f'{year}/{tick_month}'
    timeframe='1-minute-bar-quotes' if tick_month is None else 'tick-data-quotes'
    url=f'https://www.histdata.com/download-free-forex-historical-data/?/ascii/{timeframe}/xauusd/{period}'
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders=[('User-Agent','GoldHistoryResearch/1.0 (personal historical research)')]
    form=PublicDownload()
    with op.open(url,timeout=35) as response:form.feed(response.read().decode('utf-8'))
    if not form.action:raise RuntimeError(f'Missing published form at {url}')
    endpoint=urllib.parse.urljoin(url, form.action)
    if urllib.parse.urlparse(endpoint).netloc!='www.histdata.com':raise ValueError(endpoint)
    req=urllib.request.Request(endpoint,data=urllib.parse.urlencode(form.fields).encode('ascii'),headers={'Referer':url})
    with op.open(req,timeout=60) as response:data=response.read()
    if data[:4]!=b'PK\x03\x04':raise RuntimeError(f'No ZIP response for {url}, received {len(data)} bytes')
    name=f'xauusd_{year}'+(f'_{tick_month:02d}_tick' if tick_month is not None else '_M1')
    path=root/(name+'.zip')
    path.write_bytes(data)
    with zipfile.ZipFile(path) as z:
        names=[i.filename for i in z.infolist()]
        assert z.testzip() is None
    receipt={'provider':'HistData.com','url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'archive_entries':names}
    (root/(name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(name,len(data),receipt['sha256'],names,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('year',type=int,nargs='+')
    p.add_argument('--tick-month',type=int)
    args=p.parse_args()
    for y in args.year:download(y,args.tick_month)
