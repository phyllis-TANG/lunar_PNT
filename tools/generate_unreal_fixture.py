"""Generate a deterministic, text-only Unreal MVP interface fixture."""
from __future__ import annotations
import argparse, csv, json, math, shutil
from pathlib import Path
import numpy as np
from unreal_coordinates import Transform, antenna_position, matrix_to_quaternion_wxyz

SCHEMA = "unreal-mvp-interface-v1"

def rz(yaw):
    c,s=math.cos(yaw),math.sin(yaw); return np.array([[c,-s,0.],[s,c,0.],[0.,0.,1.]])

def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(rows)

def generate(root: Path):
    if root.exists(): shutil.rmtree(root)
    (root/'metadata').mkdir(parents=True); (root/'truth').mkdir(); (root/'imu').mkdir(); (root/'lidar/frames').mkdir(parents=True); (root/'external').mkdir()
    calibration={"schema_version":SCHEMA,"quaternion_order":"wxyz","transform_semantics":"p_parent=R_parent_child*p_child+t_parent_child","camera_left":{"model":"pinhole","width":1024,"height":1024,"fx_px":610.,"fy_px":610.,"cx_px":511.5,"cy_px":511.5,"distortion":[0,0,0,0]},"camera_right":{"width":1024,"height":1024},"extrinsics":{"T_B_C0":{"translation_m":[0.8,0.155,0.7],"quaternion_wxyz":[0.5,-0.5,0.5,-0.5]},"T_B_C1":{"translation_m":[0.8,-0.155,0.7],"quaternion_wxyz":[0.5,-0.5,0.5,-0.5]},"T_B_L":{"translation_m":[0.5,0,0.8],"quaternion_wxyz":[1,0,0,0]},"T_B_I":{"translation_m":[0,0,0],"quaternion_wxyz":[1,0,0,0]},"T_B_A":{"translation_m":[1,0,1],"quaternion_wxyz":[1,0,0,0]}}}
    simulation={"schema_version":SCHEMA,"fixture_kind":"deterministic_synthetic_partial","fixed_step_s":0.1,"gravity_N_mps2":[0,0,-1.625],"truth_rate_hz":10,"imu_rate_hz":10,"lidar_rate_hz":2,"lidar":{"channels":4,"scan_period_ns":500000000},"sensor_noise":{"camera":{"model":"disabled-v1"},"lidar":{"model":"disabled-v1"},"imu":{"model":"disabled-v1"}}}
    scene={"schema_version":SCHEMA,"scene_id":"deterministic_text_fixture","extent_m":[20,20],"route_N_m":[[0,0],[1,0],[1,1]],"limitations":"Synthetic interface fixture; not an Unreal export or lunar terrain."}
    for name,data in [('calibration',calibration),('simulation',simulation),('scene',scene)]: (root/f'metadata/{name}.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    truth=[]; imu=[]; clocks=[]; sats=[]; ranges=[]
    lever=np.array([1.,0.,1.]); sigma=0.5; rng=np.random.default_rng(20260908)
    for i in range(31):
        t=i*100_000_000; sec=i/10
        if sec <= 1: p=np.array([0.,0.,0.6]); v=np.zeros(3); yaw=0.; omega=0.
        elif sec <= 2: p=np.array([sec-1,0.,0.6]); v=np.array([1.,0.,0.]); yaw=0.; omega=0.
        else: p=np.array([1.,0.,0.6]); v=np.zeros(3); yaw=(sec-2)*math.pi/2; omega=math.pi/2
        r=rz(yaw); q=matrix_to_quaternion_wxyz(r); pa=antenna_position(p,r,lever)
        truth.append(dict(timestamp_ns=t,frame_index=i,p_N_B_x_m=p[0],p_N_B_y_m=p[1],p_N_B_z_m=p[2],q_N_B_w=q[0],q_N_B_x=q[1],q_N_B_y=q[2],q_N_B_z=q[3],v_N_B_x_mps=v[0],v_N_B_y_mps=v[1],v_N_B_z_mps=v[2],omega_B_x_radps=0,omega_B_y_radps=0,omega_B_z_radps=omega))
        # Specific force at a body-coincident IMU: R_BN(a_N-g_N); a_N is zero in each segment sample.
        f=r.T @ np.array([0.,0.,1.625])
        imu.append(dict(timestamp_ns=t,frame_index=i,omega_I_x_radps=0,omega_I_y_radps=0,omega_I_z_radps=omega,specific_force_I_x_mps2=f[0],specific_force_I_y_mps2=f[1],specific_force_I_z_mps2=f[2]))
        bias=10.+0.02*sec; clocks.append(dict(timestamp_ns=t,receiver_clock_range_bias_m=bias,receiver_clock_range_drift_mps=0.02,model_id='deterministic_linear',random_seed=20260908))
        for sid,ps in [('SAT01',np.array([1000.,2000.,1500.])),('SAT02',np.array([-1200.,900.,1800.]))]:
            satclk=2. if sid=='SAT01' else -1.; d=ps-pa; geom=float(np.linalg.norm(d)); los=d/geom
            sats.append(dict(timestamp_ns=t,satellite_id=sid,p_N_sat_x_m=ps[0],p_N_sat_y_m=ps[1],p_N_sat_z_m=ps[2],satellite_clock_range_bias_m=satclk,visible_geometry_only='true'))
            ideal=geom+bias-satclk; noise=float(rng.normal(0,sigma)); ranges.append(dict(timestamp_ns=t,satellite_id=sid,pseudorange_ideal_m=ideal,pseudorange_m=ideal+noise,sigma_pseudorange_m=sigma,los_N_x=los[0],los_N_y=los[1],los_N_z=los[2],geometry_visible='true',measurement_available='true',noise_m=noise))
    write_csv(root/'truth/trajectory.csv',truth[0].keys(),truth); write_csv(root/'imu/data.csv',imu[0].keys(),imu)
    write_csv(root/'external/receiver_clock.csv',clocks[0].keys(),clocks); write_csv(root/'external/satellite_state.csv',sats[0].keys(),sats); write_csv(root/'external/pseudorange.csv',ranges[0].keys(),ranges)
    scans=[]
    for k,i in enumerate(range(0,31,5)):
        t=i*100_000_000; rel=f'lidar/frames/{t}.csv'; pts=[dict(x_m=4,y_m=0,z_m=0,intensity=.5,ring=j,time_offset_ns=j*100_000_000,return_id=0,semantic_id=1) for j in range(4)]
        write_csv(root/rel,pts[0].keys(),pts); scans.append(dict(timestamp_ns=t,frame_index=k,points_path=rel,scan_start_ns=t,scan_end_ns=t+500_000_000))
    write_csv(root/'lidar/index.csv',scans[0].keys(),scans)
    write_csv(root/'events.csv',['timestamp_ns','sensor','event_type','expected_frame_index','reason'],[])
    (root/'coverage.json').write_text(json.dumps({"scope":"synthetic","covered":["truth","imu","lidar","external_navigation"],"not_covered":["camera_rgb","camera_depth","Unreal engine conventions"]},indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); generate(a.output); print(a.output)
if __name__=='__main__': main()
