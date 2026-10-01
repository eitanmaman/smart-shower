import tempfile
import unittest
from pathlib import Path
from backend import Ledger, parse_event, score

class ScoringTests(unittest.TestCase):
    def test_normal_boundaries(self):
        for seconds, expected in [(0,0),(179,0),(180,2),(599,2),(600,1),(899,1),(900,0),(5999,0)]:
            with self.subTest(seconds=seconds):
                self.assertEqual(score(seconds,0)[0], expected)
    def test_demo_boundaries(self):
        for seconds, expected in [(2,0),(3,2),(9,2),(10,1),(14,1),(15,0)]:
            self.assertEqual(score(seconds,0,'demo')[0],expected)
    def test_handover(self):
        for mode in ['normal','demo']:
            self.assertEqual(score(300,1,mode)[0],0)
    def test_parser(self):
        self.assertEqual(parse_event('DATA,04abcdef,180,0'),('04ABCDEF',180,0))
        self.assertEqual(parse_event('DATA,01020304050607,180,0')[0],'01020304050607')
    def test_bad_frames(self):
        for line in ['DATA,x,180,0','DATA,04ABCDEF,-1,0','DATA,04ABCDEF,1,2',
                     'DATA,04ABCDEF,1.5,0','DATA,04ABCDEF,6000,0','DATA,04ABCDEF,1,0,extra']:
            with self.assertRaises(ValueError): parse_event(line)

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(':memory:')
    def tearDown(self):
        self.ledger.close()
    def event(self,start,duration=300,penalty=0,uid='01020304',mode='normal'):
        return self.ledger.record(uid,duration,penalty,mode,now=start+duration)
    def test_exact_twelve_hour_boundary(self):
        self.assertEqual(self.event(100000)['earned'],2)
        self.assertEqual(self.event(100000+43199)['earned'],0)
        self.assertEqual(self.event(100000+43200)['earned'],2)
    def test_zero_point_first_session_consumes_window(self):
        self.assertEqual(self.event(100000,10)['earned'],0)
        self.assertEqual(self.event(100400)['earned'],0)
    def test_handover_consumes_window(self):
        self.assertEqual(self.event(100000,300,1)['earned'],0)
        self.assertEqual(self.event(100400)['earned'],0)
    def test_separate_users(self):
        self.event(100000)
        self.assertEqual(self.event(100000,uid='05060708')['earned'],2)
    def test_demo_no_cooldown_and_separate_balance(self):
        self.assertEqual(self.event(100000,5,mode='demo')['total_points'],2)
        self.assertEqual(self.event(100010,5,mode='demo')['total_points'],4)
        self.assertEqual(self.event(100100)['total_points'],2)
    def test_reject_out_of_order(self):
        self.event(100000)
        with self.assertRaises(ValueError):self.event(99000)
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'test.sqlite3')
            ledger=Ledger(path);ledger.record('01020304',300,0,now=100300);ledger.close()
            ledger=Ledger(path)
            self.assertEqual(ledger.record('01020304',300,0,now=100700)['earned'],0)
            self.assertEqual(ledger.record('01020304',300,0,now=143500)['total_points'],4)
            ledger.close()

if __name__ == '__main__':unittest.main()
