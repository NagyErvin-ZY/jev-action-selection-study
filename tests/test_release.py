import json, tempfile, unittest, zipfile, sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reproduce import ROOT,extract,sha
from rerun import Budget,verify_response,MODEL

class Tests(unittest.TestCase):
    def test_model_drift_halts_fake_response(self):
        with tempfile.TemporaryDirectory() as d:
            b=Budget(Path(d)/'budget.json','1',RuntimeError)
            verify_response({'model':MODEL,'provider':'TypeSafe'},b,RuntimeError)
            self.assertFalse(b.data['halted'])
            with self.assertRaises(RuntimeError):verify_response({'model':'different-revision','provider':'TypeSafe'},b,RuntimeError)
            self.assertTrue(b.data['halted'])
    def test_budget_retains_uncertain_and_enforces_cap(self):
        with tempfile.TemporaryDirectory() as d:
            b=Budget(Path(d)/'budget.json','0.004',RuntimeError)
            b.reserve('first');b.settle('first',None);b.reserve('second')
            with self.assertRaises(RuntimeError):b.reserve('third')
            b.settle('second','0.0001')
            self.assertEqual(b.exposure(),Decimal('0.0021'))
            with self.assertRaises(RuntimeError):b.reserve('fourth')
    def test_unexpected_charge_halts(self):
        with tempfile.TemporaryDirectory() as d:
            b=Budget(Path(d)/'budget.json','1',RuntimeError)
            b.reserve('first');b.settle('first','0.0021')
            with self.assertRaises(RuntimeError):b.reserve('second')
    def test_archive_sources_and_redaction(self):
        manifest=json.loads((ROOT/'public-manifest.json').read_text())
        with zipfile.ZipFile(ROOT/'evidence.zip') as z:
            self.assertEqual(set(z.namelist()),set(manifest))
            for name in z.namelist():
                value=z.read(name)
                self.assertEqual(sha(value),manifest[name]['public_sha256'])
                self.assertNotIn(b'/Users/',value)
                self.assertNotIn(b'gen-dec-',value)
                if name.endswith('.py'):self.assertEqual(value,(ROOT/'study'/name).read_bytes())
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):extract(d)

if __name__=='__main__':unittest.main()
