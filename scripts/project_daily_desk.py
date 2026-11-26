"""Project the two most recent completed editions into the public Daily Desk feed."""
import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from public_data_projection import private_url

TOPICS = ('news', 'bonds', 'earnings', 'economy')
FEED = Path(__file__).resolve().parents[1] / 'site/data/daily-desk.json'


def prose(value):
    if not isinstance(value, str) or not value.strip() or private_url(value):
        raise ValueError('Missing or private reader text')
    return value.strip()


def report(value):
    result = {key: prose(value[key]) for key in ('summary', 'coverage')}
    for key in ('happened', 'key_points', 'watch'):
        if not isinstance(value[key], list):
            raise ValueError('Expected a list of points')
        result[key] = [prose(point) for point in value[key]]
    if not isinstance(value['sources'], list):
        raise ValueError('Expected source links')
    sources = []
    for source in value['sources']:
        url = prose(source['url'])
        dest = urlsplit(url)
        if dest.scheme != 'https' or not dest.hostname or dest.username or dest.password:
            raise ValueError('Expected a public HTTPS source')
        sources.append({'title': prose(source['title']), 'url': url})
    if not sources and any(result[k] for k in ('happened', 'key_points', 'watch')):
        raise ValueError('Reported developments require sources')
    result['sources'] = sources
    return result


def project(source, previous):
    if source['schema_version'] != 1 or not source['editions']:
        raise ValueError('Expected Daily Desk editions')
    rows = sorted(source['editions'], key=lambda e: e['date'], reverse=True)
    if len({r['date'] for r in rows}) != len(rows):
        raise ValueError('Duplicate edition date')
    by_date = {e['date']: e for e in previous['editions']}
    if by_date and rows[0]['date'] < max(by_date):
        raise ValueError('Input predates the published edition')
    for row in rows[:2]:
        day = date.fromisoformat(row['date'])
        cutoff = datetime.fromisoformat(row['cutoff'])
        if day != cutoff.date() or cutoff.utcoffset() != timedelta(hours=8):
            raise ValueError('Cutoff must fall on the edition date in Singapore')
        old = by_date.get(row['date'])
        if old and datetime.fromisoformat(old['cutoff']) > cutoff:
            raise ValueError('Cutoff would move backwards')
        by_date[row['date']] = {'date': day.isoformat(), 'cutoff': row['cutoff'],
                                'reports': {key: report(row['reports'][key]) for key in TOPICS}}
    return {'schema_version': 1, 'editions': [by_date[day] for day in sorted(by_date, reverse=True)[:2]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    previous = json.loads(FEED.read_bytes()) if FEED.exists() else {'editions': []}
    result = project(json.loads(args.input.read_bytes()), previous)
    if result != previous:
        with NamedTemporaryFile(dir=FEED.parent, delete=False) as tmp:
            tmp.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode())
        os.replace(tmp.name, FEED)
    print('Public dashboard editions:', ', '.join(e['date'] for e in result['editions']))


if __name__ == '__main__':
    main()
