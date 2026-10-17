"""Scientific comparison panels and optional projected-rail rectangle metrics."""
import argparse
import json
import os
from pathlib import Path
import numpy as np
from PIL import Image
from evaluate_brush import metrics,relocated

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--rois',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1];run=a.run.resolve();assert run.is_relative_to(root/'outputs');os.environ['MPLCONFIGDIR']=str(run/'mpl-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
v=json.loads((run/'artifact-verification.json').read_text());rois=json.loads(a.rois.read_text()) if a.rois else None;rows=[]
for view in v['views']:
    gt=np.asarray(Image.open(relocated(view['reference'],root)).convert('RGB'));pred=np.asarray(Image.open(relocated(view['prediction'],root)).convert('RGB'));fig,axes=plt.subplots(1,3,figsize=(12,4));error=np.mean(np.abs(gt.astype(float)-pred),axis=2)/255
    for ax,data,title in zip(axes,[gt,pred,error],['Blender: held-out reference','Brush: final reconstruction','Mean absolute RGB error [0,1]']):
        if data.ndim==2:im=ax.imshow(data,cmap='magma',vmin=0,vmax=1);fig.colorbar(im,ax=ax,fraction=.046)
        else:ax.imshow(data)
        ax.set_title(title);ax.axis('off')
    fig.suptitle(f"{view['camera']} — PSNR {view['psnr_db']:.2f} dB / SSIM {view['ssim_skimage']:.3f}");fig.tight_layout();target=run/(view['camera']+'-comparison.png');assert not target.exists();fig.savefig(target,dpi=120);plt.close(fig)
    if rois:
        x0,y0,x1,y1=rois['views'][view['camera']];rows.append(dict(camera=view['camera'],bbox_xyxy=[x0,y0,x1,y1],**metrics(gt[y0:y1,x0:x1],pred[y0:y1,x0:x1])))
if rois:
    (run/'rail-roi-metrics.json').write_text(json.dumps(dict(purpose=rois['purpose'],views=rows),indent=2)+'\n')
print('Comparison panels:',len(v['views']),'rail rectangles:',len(rows))
