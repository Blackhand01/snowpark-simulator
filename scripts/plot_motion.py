"""Plot an existing timeline CSV without rerunning Blender."""
import argparse
import csv
import os
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    out=a.output.resolve()
    assert out.is_relative_to(Path(__file__).resolve().parents[1]/'outputs')
    os.environ['MPLCONFIGDIR']=str(out/'mpl-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=list(csv.DictReader((out/'timeline.csv').open()))
    t=[float(r['t']) for r in rows]
    fig,axs=plt.subplots(3,1,figsize=(9,7),sharex=True)
    for ax,keys,label in [(axs[0],['altitude','crouch'],'Metri'),(axs[1],['y','root_z'],'Metri'),(axs[2],['torso_pitch','ski_pitch','arm_swing','accessory_pitch'],'Radianti')]:
        for k in keys:ax.plot(t,[float(r[k]) for r in rows],label=k)
        ax.set_ylabel(label);ax.legend(loc='upper right',ncol=2);ax.grid(alpha=.2)
    axs[2].set_xlabel('Tempo [s]');fig.suptitle('Salto cinematico — non simulazione fisica');fig.tight_layout()
    for ext in ['png','svg']:
        target=out/('timeline.'+ext);assert not target.exists();fig.savefig(target,dpi=150)


if __name__=='__main__':main()
