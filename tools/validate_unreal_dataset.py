"""Validate unreal-mvp-interface-v1 text exports."""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path
import numpy as np
from unreal_coordinates import Transform, antenna_position, quaternion_wxyz_to_matrix

SCHEMA="unreal-mvp-interface-v1"
class Report:
 def __init__(self,scope): self.scope=scope; self.errors=[]; self.warnings=[]; self.covered=[]
 def error(self,path,msg,row=None): self.errors.append({"path":str(path),"row":row,"message":msg})
 def warn(self,path,msg): self.warnings.append({"path":str(path),"message":msg})
 def data(self): return {"schema_version":SCHEMA,"scope":self.scope,"valid":not self.errors,"errors":self.errors,"warnings":self.warnings,"covered":sorted(set(self.covered))}

def load_json(root,rel,report):
 p=root/rel
 try: d=json.loads(p.read_text())
 except Exception as e: report.error(rel,f"cannot read JSON: {e}"); return {}
 if d.get('schema_version')!=SCHEMA: report.error(rel,f"schema_version must be {SCHEMA}")
 return d

def table(root,rel,required,report,key=None):
 p=root/rel
 try:
  with p.open(newline='',encoding='utf-8') as f: rd=csv.DictReader(f); rows=list(rd); fields=rd.fieldnames or []
 except Exception as e: report.error(rel,f"cannot read CSV: {e}"); return []
 missing=[x for x in required if x not in fields]
 if missing: report.error(rel,f"missing fields: {', '.join(missing)}"); return []
 seen=set(); last=None
 for n,row in enumerate(rows,2):
  try: t=int(row['timestamp_ns'])
  except Exception: report.error(rel,"timestamp_ns must be an integer",n); continue
  if last is not None and t<last: report.error(rel,"timestamps are not ordered",n)
  last=t; k=(t,row[key]) if key else t
  if k in seen: report.error(rel,"duplicate record key",n)
  seen.add(k); row['_timestamp']=t; row['_row']=n
 return rows

def f(row,name,rel,report):
 try:
  x=float(row[name]); assert math.isfinite(x); return x
 except Exception: report.error(rel,f"{name} must be finite",row.get('_row')); return math.nan

def safe_path(root,value,rel,report,row):
 try:
  p=(root/value).resolve(); p.relative_to(root.resolve())
 except Exception: report.error(rel,f"path escapes dataset root: {value}",row); return None
 if not p.exists(): report.error(rel,f"referenced file does not exist: {value}",row)
 return p

def check_regular(rows, rate, rel, sensor, event_rows, report):
 if not rows or not rate: return
 expected=round(1_000_000_000/float(rate))
 for before,after in zip(rows,rows[1:]):
  if after['_timestamp']-before['_timestamp'] != expected:
   explained=any(e['sensor']==sensor and before['_timestamp']<e['_timestamp']<after['_timestamp'] and e['event_type']=='dropped_frame' for e in event_rows)
   if not explained: report.error(rel,f"sampling interval differs from declared {rate} Hz without a matching dropped_frame event",after['_row'])
  if 'frame_index' in after and int(after['frame_index']) != int(before['frame_index'])+1:
   report.error(rel,'frame_index is not consecutive',after['_row'])

def validate(root:Path,scope='synthetic'):
 r=Report(scope); cal=load_json(root,'metadata/calibration.json',r); sim=load_json(root,'metadata/simulation.json',r); load_json(root,'metadata/scene.json',r)
 if cal.get('quaternion_order')!='wxyz': r.error('metadata/calibration.json','quaternion_order must be wxyz')
 extr=cal.get('extrinsics',{})
 cam=cal.get('camera_left',{})
 for key in ['width','height','fx_px','fy_px','cx_px','cy_px']:
  if not isinstance(cam.get(key),(int,float)) or not math.isfinite(cam[key]): r.error('metadata/calibration.json',f'camera_left.{key} must be finite')
 if cam.get('width',0)<=0 or cam.get('height',0)<=0 or cam.get('fx_px',0)<=0 or cam.get('fy_px',0)<=0: r.error('metadata/calibration.json','camera dimensions and focal lengths must be positive')
 transforms={}
 for name in ['T_B_C0','T_B_C1','T_B_L','T_B_I','T_B_A']:
  try:
   e=extr[name]; transforms[name]=Transform(quaternion_wxyz_to_matrix(e['quaternion_wxyz']),e['translation_m'])
  except Exception as ex: r.error('metadata/calibration.json',f'invalid {name}: {ex}')
 if 'T_B_C0' in transforms and 'T_B_C1' in transforms:
  baseline=np.linalg.norm(transforms['T_B_C0'].translation-transforms['T_B_C1'].translation)
  if not np.isclose(baseline,.310,atol=1e-6): r.error('metadata/calibration.json',f'stereo baseline is {baseline}, expected 0.310 m')
 events=table(root,'events.csv','timestamp_ns sensor event_type expected_frame_index reason'.split(),r)
 truth_req='timestamp_ns frame_index p_N_B_x_m p_N_B_y_m p_N_B_z_m q_N_B_w q_N_B_x q_N_B_y q_N_B_z v_N_B_x_mps v_N_B_y_mps v_N_B_z_mps omega_B_x_radps omega_B_y_radps omega_B_z_radps'.split()
 truth=table(root,'truth/trajectory.csv',truth_req,r); truth_by={x['_timestamp']:x for x in truth}; rotations={}
 check_regular(truth,sim.get('truth_rate_hz'),'truth/trajectory.csv','truth',events,r)
 for row in truth:
  q=[f(row,x,'truth/trajectory.csv',r) for x in ['q_N_B_w','q_N_B_x','q_N_B_y','q_N_B_z']]
  if np.all(np.isfinite(q)):
   if not np.isclose(np.linalg.norm(q),1,atol=1e-6): r.error('truth/trajectory.csv','quaternion is not normalized',row['_row'])
   else: rotations[row['_timestamp']]=quaternion_wxyz_to_matrix(q)
 r.covered.append('truth')
 imu_req='timestamp_ns frame_index omega_I_x_radps omega_I_y_radps omega_I_z_radps specific_force_I_x_mps2 specific_force_I_y_mps2 specific_force_I_z_mps2'.split()
 imu=table(root,'imu/data.csv',imu_req,r)
 check_regular(imu,sim.get('imu_rate_hz'),'imu/data.csv','imu',events,r)
 g=np.asarray(sim.get('gravity_N_mps2',[]),float); gmag=np.linalg.norm(g) if g.shape==(3,) else math.nan
 if not math.isfinite(gmag): r.error('metadata/simulation.json','gravity_N_mps2 must be a finite 3-vector')
 for row in imu:
  if row['_timestamp'] not in truth_by: r.error('imu/data.csv','timestamp has no truth correspondence',row['_row']); continue
  sf=np.array([f(row,x,'imu/data.csv',r) for x in ['specific_force_I_x_mps2','specific_force_I_y_mps2','specific_force_I_z_mps2']])
  if scope=='synthetic' and np.all(np.isfinite(sf)) and math.isfinite(gmag) and not np.isclose(np.linalg.norm(sf),gmag,atol=.02): r.error('imu/data.csv','specific-force magnitude inconsistent with configured gravity for this zero-acceleration fixture',row['_row'])
 r.covered.append('imu')
 idx=table(root,'lidar/index.csv','timestamp_ns frame_index points_path scan_start_ns scan_end_ns'.split(),r)
 channels=int(sim.get('lidar',{}).get('channels',0))
 for row in idx:
  p=safe_path(root,row['points_path'],'lidar/index.csv',r,row['_row']); start=int(row['scan_start_ns']); end=int(row['scan_end_ns'])
  if p and p.exists():
   with p.open(newline='') as fh: rd=csv.DictReader(fh); pts=list(rd); missing=set('x_m y_m z_m intensity ring time_offset_ns return_id semantic_id'.split())-set(rd.fieldnames or [])
   if missing: r.error(row['points_path'],f"missing fields: {', '.join(sorted(missing))}")
   for n,pt in enumerate(pts,2):
    try: ring=int(pt['ring']); off=int(pt['time_offset_ns'])
    except Exception: r.error(row['points_path'],'ring/time_offset_ns must be integers',n); continue
    if not 0<=ring<channels: r.error(row['points_path'],'ring outside configured channel range',n)
    if not 0<=off<=end-start: r.error(row['points_path'],'point time offset outside scan interval',n)
 r.covered.append('lidar')
 clocks=table(root,'external/receiver_clock.csv','timestamp_ns receiver_clock_range_bias_m receiver_clock_range_drift_mps model_id random_seed'.split(),r)
 sats=table(root,'external/satellite_state.csv','timestamp_ns satellite_id p_N_sat_x_m p_N_sat_y_m p_N_sat_z_m satellite_clock_range_bias_m visible_geometry_only'.split(),r,key='satellite_id')
 obs=table(root,'external/pseudorange.csv','timestamp_ns satellite_id pseudorange_m sigma_pseudorange_m los_N_x los_N_y los_N_z geometry_visible measurement_available'.split(),r,key='satellite_id')
 clock_t={x['_timestamp'] for x in clocks}; clock={x['_timestamp']:x for x in clocks}; sat={(x['_timestamp'],x['satellite_id']):x for x in sats}
 for row in obs:
  key=(row['_timestamp'],row['satellite_id'])
  if row['_timestamp'] not in truth_by or row['_timestamp'] not in clock_t: r.error('external/pseudorange.csv','timestamp has no truth/clock correspondence',row['_row'])
  if key not in sat: r.error('external/pseudorange.csv','no matching satellite state',row['_row'])
  available=row['measurement_available'].lower()=='true'; visible=row['geometry_visible'].lower()=='true'
  if available and not visible: r.error('external/pseudorange.csv','available observation cannot be geometrically invisible',row['_row'])
  sigma=f(row,'sigma_pseudorange_m','external/pseudorange.csv',r); los=np.array([f(row,x,'external/pseudorange.csv',r) for x in ['los_N_x','los_N_y','los_N_z']])
  if available and sigma<=0: r.error('external/pseudorange.csv','available observation sigma must be positive',row['_row'])
  if available and not np.isclose(np.linalg.norm(los),1,atol=1e-6): r.error('external/pseudorange.csv','LOS must be a unit vector',row['_row'])
  if key in sat and row['_timestamp'] in truth_by and 'T_B_A' in transforms:
   tr=truth_by[row['_timestamp']]; p=np.array([float(tr[x]) for x in ['p_N_B_x_m','p_N_B_y_m','p_N_B_z_m']]); rot=rotations.get(row['_timestamp'])
   if rot is not None:
    pa=antenna_position(p,rot,transforms['T_B_A'].translation); sr=sat[key]; ps=np.array([float(sr[x]) for x in ['p_N_sat_x_m','p_N_sat_y_m','p_N_sat_z_m']]); expected=(ps-pa)/np.linalg.norm(ps-pa)
    if not np.allclose(los,expected,atol=1e-6): r.error('external/pseudorange.csv','LOS direction disagrees with truth, antenna lever arm, and satellite state',row['_row'])
    if 'pseudorange_ideal_m' in row and row['_timestamp'] in clock:
     ideal=np.linalg.norm(ps-pa)+float(clock[row['_timestamp']]['receiver_clock_range_bias_m'])-float(sr['satellite_clock_range_bias_m'])
     if not np.isclose(float(row['pseudorange_ideal_m']),ideal,atol=1e-8): r.error('external/pseudorange.csv','ideal pseudorange violates geometric+receiver-clock-satellite-clock model',row['_row'])
 r.covered.append('external_navigation')
 if scope=='complete':
  cams=table(root,'camera/frames.csv','timestamp_ns frame_index left_rgb_path right_rgb_path left_depth_path'.split(),r)
  for row in cams:
   for x in ['left_rgb_path','right_rgb_path','left_depth_path']: safe_path(root,row[x],'camera/frames.csv',r,row['_row'])
  if not cams: r.error('camera/frames.csv','complete scope requires camera/depth records and real referenced files')
  r.covered.append('camera_files_exist')
 else: r.warn('camera/frames.csv','not covered by synthetic scope: RGB/depth files and their contents')
 r.warn('engine-adapter','Unreal Euler signs, plugin-native frames, rendered file contents, and timestamp behavior require in-engine validation')
 return r

def main():
 p=argparse.ArgumentParser(); p.add_argument('dataset',type=Path); p.add_argument('--scope',choices=['synthetic','complete'],default='synthetic'); p.add_argument('--report',type=Path); a=p.parse_args(); r=validate(a.dataset,a.scope); d=r.data(); text=json.dumps(d,indent=2); print(text)
 if a.report: a.report.write_text(text+'\n')
 raise SystemExit(0 if d['valid'] else 1)
if __name__=='__main__': main()
