"""Bounded official-source recheck; no guessed SDK download locations."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'evidence').mkdir(exist_ok=True)
class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.links=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip+=1
        if tag == 'a': self.links += [v for k,v in attrs if k=='href']
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

urls = ['https://trymira.com/docs/api-reference','https://trymira.com/docs/quickstart',
        'https://trymira.com/docs/phone-companion','https://trymira.com/docs/packaging',
        'https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/',
        'https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters/']
receipts=[]
for url in urls:
    with urlopen(Request(url, headers={'User-Agent':'hermes-mira-doc-check/0.1'}), timeout=30) as response:
        parser=Text();parser.feed(response.read().decode())
        text='\n'.join(parser.parts)
        name=url.rstrip('/').split('/')[-1]
        (ROOT/'evidence'/f'official-{name}.txt').write_text(text)
        links=sorted({link for link in parser.links if any(term in link.lower() for term in ('.zip','.rs','.tar','validate.py','package.py','github.com'))})
        receipts.append({'url':url,'status':response.status,'asset_candidates':links})
print(json.dumps(receipts,indent=2))
(ROOT/'evidence'/'official-sources.json').write_text(json.dumps(receipts,indent=2))
