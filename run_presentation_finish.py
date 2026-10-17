"""Restore readable corduroy and material viewport, preserving the tailored scene.

Host mode starts installed Blender in the verified offline background mode.
The paired 'before' is an existing real render with an identical render contract.
"""
import argparse,datetime,hashlib,json,shutil,subprocess,sys,time,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')


def shader_state(terrain):
    result={}
    for mat in terrain.data.materials:
        p=mat.node_tree.nodes.get('Principled BSDF')
        result[mat.name]=dict(final_normal=[l.from_node.name for l in p.inputs['Normal'].links],bumps={n.name:
            dict(strength=n.inputs['Strength'].default_value,distance=n.inputs['Distance'].default_value,
                 normal_from=[l.from_node.name for l in n.inputs['Normal'].links],
                 height_from=[l.from_node.name for l in n.inputs['Height'].links]) for n in mat.node_tree.nodes if n.type=='BUMP'})
    return result


def inside(stage,out,c):
    sys.path.insert(0,str(ROOT/'scripts'))
    import bpy
    from refine_geometry import stable_fingerprint
    from p2_support import render,render_contract
    s=bpy.context.scene;terrain=s.objects['Snow_terrain']
    if stage=='verify':
        checks=dict(all_meshes_bones_and_transforms_preserved=stable_fingerprint(s)==json.loads((out/'geometry-before.json').read_text()),
                    saved_shader_recipe_matches=shader_state(terrain)==json.loads((out/'shader-after.json').read_text()),
                    material_preview_saved=all(a.spaces.active.shading.type=='MATERIAL' for sc in bpy.data.screens for a in sc.areas if a.type=='VIEW_3D'),
                    static_existing_rig=len(s.objects['Athlete_Rig'].data.bones)==22 and not bpy.data.actions,
                    final_flag=s.get('presentation_finish')=='CORDUROY_VISIBLE')
        old=json.loads((out/'preserved-files.json').read_text());changed=[p for p,h in old.items() if sha(ROOT/p)!=h]
        checks['old_outputs_unchanged']=not changed
        write(out/'verification.json',dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
              preserved_files=len(old),changed=changed,blend_sha256=sha(bpy.data.filepath),scene_saved_by_verifier=False))
        assert all(checks.values()),checks
        print('PRESENTATION_VERIFY_PASS');return
    assert sha(ROOT/c['source']['blend'])==c['source']['sha256']
    old_record=next(r for r in json.loads((ROOT/c['source']['render_records']).read_text()) if r['file']=='context.png')
    rc=old_record['contract'];s.camera=s.objects[rc['camera']]
    s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage=rc['resolution']
    s.cycles.samples=rc['samples'];s.cycles.seed=rc['seed'];s.render.threads=rc['threads']
    assert render_contract(s)==rc,'BEFORE_RENDER_SETTINGS_DO_NOT_MATCH'
    before_image=ROOT/c['source']['render_directory']/old_record['file'];assert sha(before_image)==old_record['sha256']
    shutil.copy2(before_image,out/'snow-before.png')
    write(out/'geometry-before.json',stable_fingerprint(s));write(out/'shader-before.json',shader_state(terrain))
    count=0
    for slot in terrain.material_slots:
        mat=slot.material.copy();mat.name=slot.material.name+'_Readable';slot.material=mat
        nodes,links=mat.node_tree.nodes,mat.node_tree.links;p=nodes.get('Principled BSDF')
        image_bump=next(n for n in nodes if n.type=='BUMP' and n.inputs['Height'].is_linked and n.inputs['Height'].links[0].from_node.type=='TEX_IMAGE')
        image_bump.inputs['Strength'].default_value=c['snow']['pbr_bump_strength']
        image_bump.inputs['Distance'].default_value=c['snow']['pbr_bump_distance_m']
        cord=[n for n in nodes if n.type=='BUMP' and n.inputs['Height'].is_linked and
              n.inputs['Height'].links[0].from_node.type=='MATH' and n.inputs['Height'].links[0].from_node.operation=='SINE']
        if cord:
            assert len(cord)==1;g=cord[0];fine=g.inputs['Normal'].links[0].from_socket
            links.new(fine,image_bump.inputs['Normal']);links.new(image_bump.outputs['Normal'],g.inputs['Normal'])
            links.new(g.outputs['Normal'],p.inputs['Normal']);g.inputs['Strength'].default_value=c['snow']['corduroy_strength']
            g.inputs['Distance'].default_value=c['snow']['corduroy_distance_m'];count+=1
    assert count==1
    assert stable_fingerprint(s)==json.loads((out/'geometry-before.json').read_text())
    write(out/'shader-after.json',shader_state(terrain))
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                v=area.spaces.active;v.shading.type='MATERIAL';v.shading.use_scene_world=True;v.shading.use_scene_lights=True
                v.overlay.show_overlays=c['viewport']['overlays'];v.region_3d.view_distance=c['viewport']['distance_m']
                v.region_3d.view_location=(-.3,0,.6);v.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion()
                v.region_3d.view_perspective='PERSP'
    s['presentation_finish']='CORDUROY_VISIBLE';s['snow_presentation_config']=json.dumps(c)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'snowpark-presentation.blend'))
    result=render(s,out/'snow-after.png')
    write(out/'snow-visibility-comparison.json',dict(before=old_record,before_image='snow-before.png',before_reused_from=str(before_image),
          after=result,identical_render_contract=result['contract']==rc,geometry_unchanged=True,viewport_shading='MATERIAL',
          note='Before is a previously executed render copied byte-for-byte; its recorded render time is not measured again'))
    print('PRESENTATION_BUILD_COMPLETE')


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['build','verify']);p.add_argument('--output',type=Path)
    p.add_argument('--inside-blender',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    if a.inside_blender:
        out=a.output.resolve();inside(a.stage,out,tomllib.loads((out/'config.toml').read_text()));return
    if a.stage=='build':
        assert a.output is None
        out=ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime('presentation-%Y%m%dT%H%M%S-%fZ');out.mkdir()
        shutil.copy2(ROOT/'snow_visibility.toml',out/'config.toml')
        old={str(f.relative_to(ROOT)):sha(f) for d in (ROOT/'outputs').iterdir() if d.is_dir() and d!=out for f in d.rglob('*') if f.is_file()}
        write(out/'preserved-files.json',old)
    else:
        assert a.output;out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs')
    c=tomllib.loads((out/'config.toml').read_text());source=out/'source'/a.stage;source.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),out/'config.toml']+[ROOT/'scripts'/n for n in ['p2_support.py','refine_geometry.py','refine_profile.py','build_scene.py']]
    for f in files:shutil.copy2(f,source/f.name)
    write(source/'manifest.json',{str(f):sha(f) for f in files})
    blend=ROOT/c['source']['blend'] if a.stage=='build' else out/'snowpark-presentation.blend'
    command=['/Applications/Blender.app/Contents/MacOS/Blender','--background','--offline-mode','--disable-autoexec','--python-exit-code','1',str(blend),
             '--python',str(Path(__file__).resolve()),'--',a.stage,'--inside-blender','--output',str(out)]
    tick=time.monotonic()
    with (out/(a.stage+'.log')).open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800,cwd=ROOT)
    with (out/'execution.jsonl').open('a') as log:log.write(json.dumps(dict(stage=a.stage,command=command,exit_code=result.returncode,seconds=time.monotonic()-tick))+'\n')
    print('PRESENTATION',a.stage,'EXIT',result.returncode,'OUTPUT',out)
    if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
