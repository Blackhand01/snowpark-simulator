"""Staged refinement: actual piste geometry, paired shaders, static rig and evidence."""
import argparse,json
from pathlib import Path
import sys,tomllib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from p2_support import ROOT,sha,write,render,render_contract
from refine_geometry import build,fingerprint,stable_fingerprint
from refine_athlete import build as athlete
from compare_snow import pbr_material


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['compare','finish','reproduce'],required=True)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--config',required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs')
    c=tomllib.loads(a.config.read_text())
    assert sha(ROOT/c['source']['p1_blend'])==c['source']['p1_sha256'],'P1_SOURCE_CHANGED'
    if a.stage in ['compare','reproduce']:
        s,profile=build(c)
    else:
        s=bpy.context.scene;profile=json.loads(s['profile_json'])
    if a.stage=='compare':
        assert not (out/'environment-baseline.blend').exists()
        write(out/'environment-fingerprint.json',fingerprint(s))
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'environment-baseline.blend'))
        # Comparison uses the close rail view so snow detail can actually be inspected.
        s.camera=s.objects['Preview_rail'];contract=render_contract(s)
        result=dict(baseline=render(s,out/'snow-baseline.png'))
        write(out/'snow-comparison.json',result)
        for slot in s.objects['Snow_terrain'].material_slots:slot.material=pbr_material(slot.material,c['snow'])
        assert fingerprint(s)==json.loads((out/'environment-fingerprint.json').read_text())
        assert render_contract(s)==contract
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'environment-pbr-candidate.blend'))
        result['pbr']=render(s,out/'snow-pbr.png')
        result.update(identical_geometry=True,identical_render_contract=result['baseline']['contract']==result['pbr']['contract'],
                      time_ratio=result['pbr']['seconds']/result['baseline']['seconds'],displacement_used=False)
        write(out/'snow-comparison.json',result)
    else:
        chosen=json.loads((out/'snow-decision.json').read_text())
        if a.stage=='reproduce' and chosen['selected']=='pbr':
            for slot in s.objects['Snow_terrain'].material_slots:slot.material=pbr_material(slot.material,c['snow'])
        assert fingerprint(s)==json.loads((out/'environment-fingerprint.json').read_text())
        rig,meta=athlete(s,c,profile)
        if a.stage=='reproduce':
            expected=json.loads((out/'stable-final-fingerprint.json').read_text())
            actual=stable_fingerprint(s)
            if actual!=expected:
                write(out/'reproduction-difference.json',{n:dict(expected=expected.get(n),actual=actual.get(n))
                      for n in expected.keys()|actual.keys() if expected.get(n)!=actual.get(n)})
            # Primitive operators can emit equivalent faces in a different storage order.
            # Preserve oriented connectivity; polygon ordering is not part of the geometry.
            rebuilt={n:s.objects[n] for n in actual};names=list(expected)
            with bpy.data.libraries.load(str(out/'snowpark-refined.blend'),link=False) as (src,dst):
                dst.objects=names.copy()
            numeric={};ok=actual.keys()==expected.keys()
            for n,saved in zip(names,dst.objects):
                lhs,rhs=actual[n].copy(),expected[n].copy();lhs.pop('geometry');rhs.pop('geometry')
                ok=ok and lhs==rhs
                if actual[n]['geometry']==expected[n]['geometry']:continue
                live=rebuilt[n]
                if live.type!='MESH':ok=False;continue
                def faces(data):
                    oriented=[]
                    for p in data.polygons:
                        v=tuple(p.vertices);i=v.index(min(v))
                        oriented.append(v[i:]+v[:i])
                    return sorted(oriented)
                same_topology=(len(live.data.vertices)==len(saved.data.vertices) and faces(live.data)==faces(saved.data))
                delta=max((v.co-w.co).length for v,w in zip(live.data.vertices,saved.data.vertices))
                numeric[n]=dict(same_topology=same_topology,max_vertex_error_m=delta,polygon_storage_order_ignored=True)
                ok=ok and same_topology and delta<=1e-6
            write(out/'reproduction-numeric.json',dict(tolerance_m=1e-6,objects=numeric))
            assert ok,'NONREPRODUCIBLE_GEOMETRY_OR_RIG'
            write(out/'reproducibility.json',dict(status='PASS',method='Independent rebuild from original P1 and frozen config; exact topology, rig and hierarchy transforms; mesh coordinates within 1 micrometre',objects_checked=len(actual),
                  objects_exact_geometry=sum(actual[n]['geometry']==expected[n]['geometry'] for n in expected),
                  max_vertex_error_m=max((v['max_vertex_error_m'] for v in numeric.values()),default=0)))
            return
        assert not (out/'snowpark-refined.blend').exists()
        s.camera=s.objects['Preview_main']
        for o in s.objects:o.select_set(False)
        rig.select_set(True);bpy.context.view_layer.objects.active=rig
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'snowpark-refined.blend'))
        write(out/'final-fingerprint.json',fingerprint(s))
        report=dict(athlete=meta,snow_decision=chosen,renders=[],blender=bpy.app.version_string,build=bpy.app.build_hash.decode())
        write(out/'build-report.json',report)
        for name,filename in [('Preview_main','main.png'),('Preview_slope','slope-side.png'),('Preview_rail','rail-close.png'),('Preview_overview','overview.png')]:
            s.camera=s.objects[name];report['renders'].append(render(s,out/filename));write(out/'build-report.json',report)
    print('REFINEMENT_STAGE_COMPLETE',a.stage)


if __name__=='__main__':main()
