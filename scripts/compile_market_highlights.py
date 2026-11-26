"""Select and retain market highlights from reviewed public hourly editions."""
import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

DATA = Path(__file__).resolve().parents[1] / 'site/data'
ARCHIVE = DATA / 'market-highlights.json'
WATCHLIST = 'https://notwins.github.io/market-intelligence-hub/data/desk-data.json'
SGT = timezone(timedelta(hours=8))
ALIASES = {'GOOGL': ['Alphabet', 'Google'], 'BRK.B': ['Berkshire Hathaway'],
           'TSM': ['TSMC', 'Taiwan Semiconductor'], 'META': ['Meta'], 'AMZN': ['AWS'],
           'MU': ['Micron'], 'BABA': ['Alibaba'], 'D05.SI': ['DBS'], 'U11.SI': ['UOB']}
MAJORS = ('Oracle', 'CoreWeave', 'OpenAI', 'SoftBank', 'SK Hynix', 'Samsung', 'ASML',
          'JPMorgan', 'Citigroup', 'Goldman Sachs', 'Morgan Stanley', 'Bank of America',
          'BNP Paribas', 'HSBC', 'OCBC', 'UBS', 'UniCredit', 'Commerzbank', 'Deutsche Bank',
          'Visa', 'Mastercard', 'Exxon', 'Saudi Aramco', 'Volkswagen', 'Tencent',
          'CrowdStrike', 'Zscaler', 'Sanofi', 'Bayer', 'BlackRock')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def has(pattern, text):
    return bool(re.search(r'\b(?:' + pattern + r')\b', text, re.I))

def named(names, title, tags):
    return any(n.casefold() in tags or has(re.escape(n), title) for n in names if n)

def signals(story, watchlist):
    title = story['headline']
    topic = story.get('topic', '')
    tags = {tag.strip().casefold() for tag in topic.split('/')}
    text = title + ' / ' + topic
    reasons = []
    def score(points, label):
        reasons.append((points, label))
    if has(r'delinquen\w*|arrears|charge[- ]offs?|non[- ]performing loans?|loan losses|defaults?|credit stress|systemic.bank capital|bank capital buffer|bankruptc\w*|credit losses|loan.loss provisions?|loan impairments?|refinancing risks?|credit spreads?|credit default swaps?', title):
        score(12, 'Credit stress')
    policy_banks = r'Fed|Federal Reserve|FOMC|SNB|Swiss National Bank|MAS|Monetary Authority of Singapore'
    policy_subject = has(policy_banks, title) or (has(policy_banks, topic) and has(r'policy|rate cuts?|rate hikes?|tighten\w*|interventions?|FOMC|central bank', title))
    if policy_subject and has(r'rates?|policy|inflation|tighten\w*|eas(?:e|ing)|liquidity|intervention\w*|capital|financial stability|guidance', text):
        score(10, 'Fed, SNB or MAS policy')
    if has(r'treasur(?:y|ies)|UST', text) and has(r'yields?|auctions?|issuance|curve|holdings|repo|refundings?|interventions?|term premia|term premium|basis trade', text):
        score(9, 'Treasury markets')
    if has(r'corporate credit|sovereign bonds?|bank credit|bonds?|debt sale|credit rating|downgrade|refinancing|yield spread', title) and (has(r'corporate credit|sovereign bonds?|global banks|systemic|investment.grade|high.yield|borrowers|bond market|treasur(?:y|ies)', text) or named(MAJORS, title, tags)):
        score(8, 'Bonds and credit')
    companies = [r['ticker'] for r in watchlist if named([r['name'], *ALIASES.get(r['ticker'], [])], title, tags)
                 or r['ticker'].casefold() in tags or r['ticker'] in story.get('tickers', []) or
                 (len(r['ticker']) >= 3 and re.search(r'\b'+re.escape(r['ticker'])+r'\b', title))]
    material = has(r'earnings|profit\w*|revenue|sales|outlook|guidance|capital|bonds?|credit|funding|invest\w*|acqui\w*|takeover|merger|deal|capex|financ\w*|regulat\w*|approv\w*|inquir\w*|investigat\w*|export\w*|sanction\w*|tariffs?|suppl\w*|production|disruption|risk\w*|loss\w*|exposure|cyber|default\w*|contract|launch|chips?|growth|layoffs?|combination|buybacks?', text)
    if companies and material:
        score(8, 'Watchlist · ' + ', '.join(companies[:3]))
        if has(r'bonds?|credit|debt|borrowing', title):
            score(8, 'Company financing')
    elif material and named(MAJORS, title, tags):
        score(7, 'Major companies')
    if has(r'ECB|BOJ|BOE|Bank of Korea|Bank of Japan|European Central Bank|Bank of England|PBOC', text) and has(r'rates?|monetary|hike\w*|tightening|inflation|rate cuts?', title):
        score(6, 'Global rates')
    return sum(points for points, _ in reasons), [label for _, label in reasons]

def end_of_window(value):
    morning = value.astimezone(SGT).replace(hour=8, minute=0, second=0, microsecond=0)
    if value <= morning:
        return morning
    evening = morning + timedelta(hours=12)
    return evening if value <= evening else morning + timedelta(days=1)

def compile_archive(feed, watchlist, previous, now):
    due = end_of_window(now)
    if due > now:
        due -= timedelta(hours=12)
    entries = {row['id']: row for row in previous.get('entries', [])}
    latest = {}
    for edition in feed['editions']:
        cutoff = datetime.fromisoformat(edition['cutoff'])
        window = end_of_window(cutoff)
        if window > due:
            continue
        for story in edition['stories']:
            key = story['story_id']
            if key not in latest or story['version'] > latest[key][0]['version']:
                latest[key] = story, edition, window
    windows = defaultdict(list)
    for key, (story, edition, window) in latest.items():
        version = story['version']
        if key in entries and entries[key]['version'] >= version:
            continue
        points, reasons = signals(story, watchlist)
        if not reasons and key not in entries:
            continue
        href = next((url for url in story['source_urls'] if url.startswith('https://')), None)
        if not href:
            continue
        source = next((s for s in edition['sources'] if s['url'] == href), {})
        row = dict(id=key, version=version, headline=story['headline'], href=href, topic=story['topic'],
                   cutoff=edition['cutoff'], published=source.get('published_at') or source.get('published_date'),
                   selected=window.isoformat(), reasons=reasons, score=points)
        if key in entries:
            row['selected'] = entries[key]['selected']
            if not reasons:
                row['reasons'], row['score'] = entries[key]['reasons'], entries[key]['score']
            entries[key] = row
        else:
            windows[window.isoformat()].append(row)
    urls = {row['href'].split('#')[0] for row in entries.values()}
    for window, candidates in sorted(windows.items()):
        available = 5 - sum(r['selected'] == window for r in entries.values())
        for row in sorted(candidates, key=lambda r: (r['score'], r['cutoff'], r['id']), reverse=True):
            url = row['href'].split('#')[0]
            if available <= 0:
                break
            if url not in urls:
                entries[row['id']] = row
                urls.add(url)
                available -= 1
    return dict(schema_version=1, through=due.isoformat(), entries=sorted(entries.values(), key=lambda r: (r['selected'], r['score'], r['cutoff'], r['id']), reverse=True))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watchlist', type=Path, help='Local copy of the public Hub desk-data.json')
    args = parser.parse_args()
    if args.watchlist:
        desk = read(args.watchlist)
    else:
        with urlopen(WATCHLIST, timeout=30) as response:
            desk = json.load(response)
    watchlist = desk['watchlist']
    if not watchlist or not all(r.get('name') and r.get('ticker') for r in watchlist):
        raise ValueError('Public Hub watchlist unavailable')
    previous = read(ARCHIVE) if ARCHIVE.exists() else {}
    result = compile_archive(read(DATA/'hourly-news.json'), watchlist, previous, datetime.now(SGT))
    if previous and result['through'] < previous['through']:
        raise ValueError('Refusing to roll back a completed selection window')
    if result != previous:
        temp = ARCHIVE.with_suffix('.tmp')
        temp.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        temp.replace(ARCHIVE)
    print(f"{len(result['entries'])} retained highlights through {result['through']}")
