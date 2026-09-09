import subprocess,sys,tempfile,unittest
from pathlib import Path

SCRIPT=Path(__file__).parents[1]/'tools/check_unreal_engine_smoke.py'
class EngineSmokeCheckerTest(unittest.TestCase):
 def test_empty_directory_is_rejected_without_fabricating_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   run=subprocess.run([sys.executable,str(SCRIPT),d],capture_output=True,text=True)
   self.assertEqual(run.returncode,1)
   self.assertIn('engine_run_valid',run.stdout)
   self.assertIn('cannot read',run.stdout)
