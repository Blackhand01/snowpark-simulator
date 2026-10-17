"""Copy calibrated RGB/poses and initialize from training camera rays only.

Brush 0.3 random initialization uses the camera AABB, which is degenerate for
a planar camera ring. No ground-truth mesh, depth, test image or test pose is
used for the initial point cloud.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zlib
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--initial-cloud-from',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve();out=a.output.resolve();root=Path(__file__).resolve().parents[1]
    assert source.is_relative_to(root/'outputs') and out.is_relative_to(root/'outputs');out.mkdir(exist_ok=False);(out/'images').mkdir()
    train=json.loads((source/'transforms_train.json').read_text());test=json.loads((source/'transforms_test.json').read_text())
    # Least-squares intersection of training optical axes.
    origins=[];lhs=np.zeros((3,3));rhs=np.zeros(3)
    for f in train['frames']:
        mat=np.asarray(f['transform_matrix'],dtype=np.float64);origin=mat[:3,3];direction=-mat[:3,2];direction/=np.linalg.norm(direction)
        projector=np.eye(3)-np.outer(direction,direction);lhs+=projector;rhs+=projector@origin;origins.append(origin)
    center=np.linalg.solve(lhs,rhs);radius=float(np.median(np.linalg.norm(np.asarray(origins)-center,axis=1))*.35)
    rng=np.random.default_rng(1729);count=10000;positions=center+rng.uniform(-radius,radius,(count,3));colors=rng.integers(40,216,(count,3))
    ply=out/'init.ply'
    previous_init=None
    if a.initial_cloud_from:
        previous=a.initial_cloud_from.resolve();assert previous.is_relative_to(root/'outputs')
        previous_init=json.loads((previous/'preparation.json').read_text());assert not previous_init['random_init']['uses_ground_truth_geometry'] and not previous_init['random_init']['uses_test_poses_or_images']
        old_train=json.loads((previous/'transforms_train.json').read_text());new_poses={json.dumps(f['transform_matrix']) for f in train['frames']};assert all(json.dumps(f['transform_matrix']) in new_poses for f in old_train['frames'])
        assert hashlib.sha256((previous/'init.ply').read_bytes()).hexdigest()==previous_init['init_sha256'];shutil.copy2(previous/'init.ply',ply)
    else:
        with ply.open('x') as f:
            f.write(f'ply\nformat ascii 1.0\nelement vertex {count}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n')
            for xyz,rgb in zip(positions,colors):f.write(' '.join([*(f'{v:.8f}' for v in xyz),*(str(v) for v in rgb)])+'\n')
    copied={};container_padding=[]
    for data in [train,test]:
        for f in data['frames']:
            original=(source/f['file_path']).resolve();assert original.is_relative_to(source)
            dest=out/'images'/original.name
            if not dest.exists():shutil.copy2(original,dest)
            assert hashlib.sha256(original.read_bytes()).digest()==hashlib.sha256(dest.read_bytes()).digest()
            # Brush 0.3 get_image_data uses read_exact(16387), even for smaller PNGs.
            # Append a standard ancillary tEXt chunk before IEND, leaving IDAT intact.
            raw=dest.read_bytes()
            if len(raw)<16387:
                assert raw.startswith(b'\x89PNG\r\n\x1a\n') and raw[-8:-4]==b'IEND'
                data=b'SnowparkCompatibility\0'+b' '*32768;kind=b'tEXt'
                chunk=struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
                dest.write_bytes(raw[:-12]+chunk+raw[-12:])
                from PIL import Image
                with Image.open(original) as before,Image.open(dest) as after:assert before.mode==after.mode and before.size==after.size and before.tobytes()==after.tobytes()
                container_padding.append(dict(file=dest.name,source_bytes=len(raw),padded_bytes=dest.stat().st_size,pixels_unchanged=True))
            f['file_path']='./images/'+dest.name;copied[dest.name]=hashlib.sha256(dest.read_bytes()).hexdigest()
    train['ply_file_path']='init.ply'
    (out/'transforms_train.json').write_text(json.dumps(train,indent=2)+'\n');(out/'transforms_test.json').write_text(json.dumps(test,indent=2)+'\n')
    train_paths={f['file_path'] for f in train['frames']};test_paths={f['file_path'] for f in test['frames']};assert not train_paths&test_paths
    result=dict(status='PREPARED',source=str(source.relative_to(root)),train_views=len(train_paths),test_views=len(test_paths),image_sha256=copied,lossless_png_container_padding=container_padding,random_init=dict(seed=1729,count=count,center_from_training_optical_axes=center.tolist(),half_extent_from_training_camera_radius_m=radius,uses_ground_truth_geometry=False,uses_test_poses_or_images=False),init_sha256=hashlib.sha256(ply.read_bytes()).hexdigest(),reason='Nondegenerate camera-only random 3D initialization for a planar calibrated camera ring')
    if previous_init:
        result['random_init']=previous_init['random_init'];result['random_init_reused_from']=str(previous.relative_to(root));result['identical_init_for_view_count_comparison']=True
    (out/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');print('PREPARED',len(train_paths),'training,',len(test_paths),'test views')


if __name__=='__main__':main()
