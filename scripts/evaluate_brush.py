"""Verify actual exported Gaussians/eval images and measure documented RGB metrics."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


def read_ply(path):
    types={'float':'<f4','float32':'<f4','double':'<f8','uchar':'u1','uint8':'u1','int':'<i4','uint':'<u4'}
    with path.open('rb') as stream:
        assert stream.readline().strip()==b'ply';fields=[];count=None;fmt=None
        while True:
            line=stream.readline().decode('ascii').strip();parts=line.split()
            if line=='end_header':break
            assert line
            if parts[:1]==['format']:fmt=parts[1]
            elif parts[:2]==['element','vertex']:count=int(parts[2])
            elif parts[:1]==['property']:
                assert len(parts)==3 and parts[1] in types
                fields.append((parts[2],types[parts[1]]))
        assert fmt=='binary_little_endian' and count and count>0
        data=np.frombuffer(stream.read(),dtype=np.dtype(fields),count=count).copy()
    return data


def metrics(a,b):
    aa=np.asarray(a,dtype=np.float64)/255;bb=np.asarray(b,dtype=np.float64)/255
    mse=float(np.mean((aa-bb)**2));psnr=10*math.log10(1/mse) if mse else None
    ssim=float(structural_similarity(aa,bb,data_range=1.0,channel_axis=2,gaussian_weights=True,sigma=1.5,win_size=11,use_sample_covariance=False))
    return dict(mse_rgb_0_1=mse,psnr_db=psnr,ssim_skimage=ssim)


def relocated(path,root):
    p=Path(path)
    if p.exists():return p
    # Historic reports may predate a checkout move. Keep relocation inside outputs.
    assert 'outputs' in p.parts,'Unknown path relocation'
    candidate=root.joinpath(*p.parts[p.parts.index('outputs'):]).resolve()
    assert candidate.is_relative_to(root/'outputs') and candidate.exists()
    return candidate


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();out=a.run.resolve();root=Path(__file__).resolve().parents[1];assert out.is_relative_to(root/'outputs')
    config=json.loads((out/'config.json').read_text());execution=json.loads((out/'execution.json').read_text());dataset=relocated(config['command'][1],root);n=config['total_steps'];text=(out/'train.log').read_text();checks={}
    checks['process_exit_0']=execution['exit_code']==0
    checks['actual_apple_metal_adapter']='backend: Metal' in text and 'Apple M1' in text
    checks['logged_expected_partition']=f"Loaded dataset with {config['train_views']} training, {config['test_views']} eval views" in text
    checks['training_reached_completion']='Done training!' in text and f'Running evaluation for iteration {n}' in text
    model=out/f'model_{n}.ply';data=read_ply(model);checks['finite_gaussian_parameters']=all(np.isfinite(data[name]).all() for name in data.dtype.names)
    required=['x','y','z','opacity',*[f'rot_{i}' for i in range(4)],*[f'scale_{i}' for i in range(3)],*[f'f_dc_{i}' for i in range(3)]];checks['real_gaussian_parameter_schema']=all(x in data.dtype.names for x in required)
    norm=np.sqrt(sum(data[f'rot_{i}'].astype(np.float64)**2 for i in range(4)));checks['nonzero_quaternions']=bool(np.min(norm)>1e-8)
    checks['positive_finite_covariance_scales']=all(np.isfinite(np.exp(data[f'scale_{i}'].astype(np.float64))).all() and np.min(np.exp(data[f'scale_{i}'].astype(np.float64)))>0 for i in range(3))
    transforms=json.loads((dataset/'transforms_test.json').read_text());views=[]
    for f in transforms['frames']:
        original=dataset/f['file_path'];pred=out/f'eval_{n}'/(original.stem+'.png')
        with Image.open(original) as gt,Image.open(pred) as reconstruction:
            gt.load();reconstruction.load();checks[original.stem+'_dimensions']=gt.size==reconstruction.size
            value=metrics(gt.convert('RGB'),reconstruction.convert('RGB'))
        views.append(dict(camera=original.stem,reference=str(original),prediction=str(pred),prediction_sha256=hashlib.sha256(pred.read_bytes()).hexdigest(),**value))
    checks['two_finite_evaluation_metrics']=len(views)==2 and all(v['psnr_db'] is not None and math.isfinite(v['psnr_db']) and math.isfinite(v['ssim_skimage']) for v in views)
    result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),gaussians=len(data),views=views,mean_psnr_db=float(np.mean([v['psnr_db'] for v in views])),mean_ssim_skimage=float(np.mean([v['ssim_skimage'] for v in views])),metric_implementation=dict(psnr='10*log10(1 / mean RGB squared error), uint8 PNG mapped to [0,1], no linear-light conversion',ssim='skimage structural_similarity, channel_axis=2, Gaussian sigma=1.5, 11x11 window, data_range=1, population covariance',skimage_version=importlib.metadata.version('scikit-image'),backend_metrics='Brush additionally logs its own 8-bit PSNR/SSIM; filter/border implementation may differ'),visual_inspection='PENDING; metrics are not visual proof',memory=execution['peak_child_rss_bytes'])
    target=out/'artifact-verification.json';assert not target.exists();target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');shutil.copy2(Path(__file__),out/'evaluate_brush.py');print(result['status'],len(checks),'checks',len(data),'Gaussians','PSNR',result['mean_psnr_db'],'SSIM',result['mean_ssim_skimage']);assert result['status']=='PASS'


if __name__=='__main__':main()
