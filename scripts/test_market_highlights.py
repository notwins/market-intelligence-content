import unittest
from datetime import datetime
from compile_market_highlights import SGT, compile_archive, signals

class MarketHighlightTests(unittest.TestCase):
    def test_topics(self):
        def why(title, topic=''):
            return signals({'headline': title, 'topic': topic}, [dict(ticker='NVDA', name='NVIDIA')])[1]
        self.assertIn('Credit stress', why('Mortgage delinquencies rise'))
        self.assertIn('Treasury markets', why('US Treasury auction draws weak demand'))
        self.assertIn('Fed, SNB or MAS policy', why('MAS holds monetary policy steady'))
        self.assertFalse(why('Treasury sanctions four officials'))
        self.assertFalse(why('Small issuer opens a branch'))
        self.assertTrue(why('Nvidia revises export guidance'))

    def test_retention_window_cutoff_and_retries(self):
        def edition(hour, ids):
            stories = [dict(story_id=str(i), version=1, topic='Credit', headline='Mortgage delinquencies rise', source_urls=['https://example.com/'+str(i)]) for i in ids]
            return dict(cutoff=f'2026-11-26T{hour}:00:00+08:00', stories=stories, sources=[])
        feed = dict(editions=[edition('10', [7]), edition('07', range(6))])
        eight = datetime(2026,11,26,8,tzinfo=SGT)
        first = compile_archive(feed, [], {}, eight)
        self.assertEqual(len(first['entries']), 5)
        self.assertNotIn('7', [r['id'] for r in first['entries']])
        self.assertEqual(first, compile_archive(feed, [], first, eight))
        sunset = compile_archive(feed, [], first, eight.replace(hour=20))
        self.assertEqual(len(sunset['entries']), 6)
        self.assertEqual(sunset['entries'][1:], first['entries'])
