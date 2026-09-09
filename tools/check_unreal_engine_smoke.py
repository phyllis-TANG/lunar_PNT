#!/usr/bin/env python3
"""Human-acceptance gate for an actual Unreal smoke-test export.

This does not synthesize sensor files.  It rejects missing/empty/malformed evidence
and emits a JSON report suitable for attaching to a later engine-run PR.
"""
from __future__ import annotations
import argparse,csv,json,math,struct
from pathlib import Path

def main():
 p=argparse.ArgumentParser(); p.add_argument('run',type=Path); p.add_argument('--report',type=Path); a=p.parse_args(); root=a.run.resolve(); errors=[]; checks=[]
 def err(path,msg,row=None): errors.append({'path':str(path),'row':row,'message':msg})
 def read_csv(rel,fields):
  path=root/rel
  try:
   with path.open(newline='',encoding='utf-8') as f: rd=csv.DictReader(f); rows=list(rd); missing=set(fields)-set(rd.fieldnames or [])
   if missing: err(rel,'missing fields: '+', '.join(sorted(missing)))
   return rows
  except Exception as e: err(rel,f'cannot read: {e}'); return []
 try:
  cfg=json.loads((root/'engine_config.json').read_text()); checks.append({'name':'engine_config','value':cfg})
  if not cfg.get('engine_version') or cfg.get('engine_version')=='TBD': err('engine_config.json','actual engine_version is required')
  if cfg.get('sensor_plugin') in (None,'TBD','not configured by exporter'): err('engine_config.json','actual sensor plugin/version configuration is required for complete evidence')
 except Exception as e: err('engine_config.json',f'cannot read: {e}'); cfg={}
 raw=read_csv('raw/actor.csv','timestamp_ns frame_index action x_u_cm y_u_cm z_u_cm q_u_x q_u_y q_u_z q_u_w'.split())
 truth=read_csv('truth/trajectory.csv','timestamp_ns frame_index action p_N_B_x_m p_N_B_y_m p_N_B_z_m q_N_B_w q_N_B_x q_N_B_y q_N_B_z'.split())
 required={'stationary','translate_native_x','plus_90_yaw_native_z','plus_90_pitch_native_y','plus_90_roll_native_x'}
 actions={x.get('action') for x in raw}; missing=required-actions
 if missing: err('raw/actor.csv','missing measured actions: '+', '.join(sorted(missing)))
 for rel,rows,qfields in [('raw/actor.csv',raw,['q_u_x','q_u_y','q_u_z','q_u_w']),('truth/trajectory.csv',truth,['q_N_B_w','q_N_B_x','q_N_B_y','q_N_B_z'])]:
  last=-1
  for line,row in enumerate(rows,2):
   try:
    t=int(row['timestamp_ns']); q=[float(row[x]) for x in qfields]
    if t<=last: err(rel,'timestamps must be strictly increasing integers',line)
    if not all(math.isfinite(x) for x in q) or abs(sum(x*x for x in q)-1)>1e-5: err(rel,'quaternion must be finite and normalized',line)
    last=t
   except Exception: err(rel,'invalid integer timestamp or numeric quaternion',line)
 if raw and truth and [x['timestamp_ns'] for x in raw] != [x['timestamp_ns'] for x in truth]: err('truth/trajectory.csv','timestamps do not exactly match raw actor export')
 camera=read_csv('camera/frames.csv','timestamp_ns frame_index left_rgb_path right_rgb_path left_depth_path'.split())
 lidar=read_csv('lidar/index.csv','timestamp_ns frame_index points_path scan_start_ns scan_end_ns'.split())
 read_csv('imu/data.csv','timestamp_ns frame_index omega_I_x_radps omega_I_y_radps omega_I_z_radps specific_force_I_x_mps2 specific_force_I_y_mps2 specific_force_I_z_mps2'.split())
 def safe_file(rel,rownum,kind):
  try: path=(root/rel).resolve(); path.relative_to(root)
  except Exception: err(kind,f'path escapes run: {rel}',rownum); return
  if not path.is_file() or path.stat().st_size==0: err(kind,f'missing or empty file: {rel}',rownum); return
  data=path.read_bytes()[:8]
  if path.suffix.lower()=='.png' and data!=b'\x89PNG\r\n\x1a\n': err(kind,f'not a PNG: {rel}',rownum)
  if path.suffix.lower()=='.exr' and data[:4]!=struct.pack('<I',20000630): err(kind,f'not an EXR: {rel}',rownum)
 for n,row in enumerate(camera,2):
  for key in ('left_rgb_path','right_rgb_path','left_depth_path'): safe_file(row.get(key,''),n,'camera/frames.csv')
 for n,row in enumerate(lidar,2): safe_file(row.get('points_path',''),n,'lidar/index.csv')
 result={'schema_version':'unreal-mvp-interface-v1','engine_run_valid':not errors,'errors':errors,'checks':checks,'limitations':['File signatures do not validate RGB/depth content or units.','Euler signs, angular-velocity handedness, sensor frames, synchronization, and fixed-step behavior require the recorded manual comparisons.']}
 text=json.dumps(result,indent=2); print(text)
 if a.report: a.report.write_text(text+'\n')
 raise SystemExit(0 if not errors else 1)
if __name__=='__main__': main()
