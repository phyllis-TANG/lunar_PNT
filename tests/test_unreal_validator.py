import csv,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from generate_unreal_fixture import generate
from validate_unreal_dataset import validate

class ValidatorTest(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)/'fixture'; generate(self.root)
    def tearDown(self): self.tmp.cleanup()
    def reset_fixture(self):
        self.tmp.cleanup()
        self.setUp()
    def rewrite(self,rel,mutate):
        p=self.root/rel
        with p.open(newline='') as f: r=csv.DictReader(f); rows=list(r); fields=r.fieldnames
        mutate(rows,fields)
        with p.open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(rows)
    def messages(self): return ' '.join(x['message'] for x in validate(self.root).errors)
    def test_fixture_passes_partial_and_complete_rejects_missing_images(self):
        report=validate(self.root); self.assertTrue(report.data()['valid']); self.assertTrue(report.warnings)
        self.assertFalse(validate(self.root,'complete').data()['valid'])
    def test_bad_quaternion(self):
        self.rewrite('truth/trajectory.csv',lambda rows,_: rows[0].update(q_N_B_w='0',q_N_B_x='0',q_N_B_y='0',q_N_B_z='0'))
        self.assertIn('quaternion',self.messages())
    def test_missing_field(self):
        p=self.root/'external/pseudorange.csv'; text=p.read_text().replace(',sigma_pseudorange_m',''); p.write_text(text)
        self.assertIn('missing fields',self.messages())
    def test_time_mismatch_and_duplicate_satellite_key(self):
        self.rewrite('external/receiver_clock.csv',lambda rows,_: rows.pop())
        self.assertIn('truth/clock correspondence',self.messages())
        self.reset_fixture()
        self.rewrite('external/pseudorange.csv',lambda rows,_: rows.append(rows[0].copy()))
        self.assertIn('duplicate record key',self.messages())
    def test_unexplained_sampling_gap(self):
        self.rewrite('imu/data.csv',lambda rows,_: rows.pop(1))
        self.assertIn('without a matching dropped_frame event',self.messages())
    def test_lidar_offset_and_missing_or_escaping_path(self):
        self.rewrite('lidar/frames/0.csv',lambda rows,_: rows[0].update(time_offset_ns='500000001'))
        self.assertIn('outside scan interval',self.messages())
        self.reset_fixture(); self.rewrite('lidar/index.csv',lambda rows,_: rows[0].update(points_path='../escape.csv'))
        self.assertIn('escapes dataset root',self.messages())
    def test_wrong_los_direction(self):
        self.rewrite('external/pseudorange.csv',lambda rows,_: rows[0].update(los_N_x='1',los_N_y='0',los_N_z='0'))
        self.assertIn('LOS direction disagrees',self.messages())
    def test_earth_specific_force_rejected_for_lunar_gravity(self):
        self.rewrite('imu/data.csv',lambda rows,_: rows[0].update(specific_force_I_z_mps2='9.80665'))
        self.assertIn('configured gravity',self.messages())
    def test_bad_antenna_lever_arm_exposes_geometry_disagreement(self):
        p=self.root/'metadata/calibration.json'; d=json.loads(p.read_text()); d['extrinsics']['T_B_A']['translation_m']=[0,0,0]; p.write_text(json.dumps(d))
        self.assertIn('LOS direction disagrees',self.messages())

    def test_generator_refuses_existing_nonempty_output(self):
        marker=self.root/'keep.txt'; marker.write_text('user data')
        with self.assertRaises(FileExistsError): generate(self.root)
        self.assertEqual(marker.read_text(),'user data')
        self.assertTrue((self.root/'truth/trajectory.csv').is_file())

    def test_complete_rejects_empty_files_and_directories(self):
        camera=self.root/'camera'; camera.mkdir()
        for name in ('left.png','right.png','depth.exr'): (camera/name).touch()
        index=camera/'frames.csv'
        index.write_text(
            'timestamp_ns,frame_index,left_rgb_path,right_rgb_path,left_depth_path\n'
            '0,0,camera/left.png,camera/right.png,camera/depth.exr\n'
        )
        report=validate(self.root,'complete')
        self.assertFalse(report.data()['valid'])
        self.assertTrue(any('file is empty' in e['message'] for e in report.errors))
        (camera/'left.png').unlink(); (camera/'left.png').mkdir()
        report=validate(self.root,'complete')
        self.assertTrue(
            any('not a regular file' in e['message'] for e in report.errors)
        )
