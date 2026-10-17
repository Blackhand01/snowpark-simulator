"""Controlled two-render snow material comparison on the loaded P1 baseline."""
import argparse
import json
from pathlib import Path
import sys
import tomllib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p2_support import ROOT,sha,write,environment_signature,render,render_contract
import bpy


def pbr_material(original,c):
    m=original.copy()
    m.name=original.name+'_Snow01_1K'
    nodes,links=m.node_tree.nodes,m.node_tree.links
    p=nodes.get('Principled BSDF')
    coord=nodes.new('ShaderNodeTexCoord')
    scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE'
    scale.inputs['Scale'].default_value=1/c['tile_m']
    links.new(coord.outputs['Object'],scale.inputs[0])
    maps={}
    for kind in ['diff','bump','rough']:
        path=ROOT/c['asset']/f'snow_01_{kind}_1k.png'
        img=bpy.data.images.load(str(path),check_existing=True)
        img.colorspace_settings.name='sRGB' if kind=='diff' else 'Non-Color'
        assert tuple(img.size)==(1024,1024)
        img.pack()
        node=nodes.new('ShaderNodeTexImage');node.image=img
        node.projection='BOX';node.projection_blend=.2
        links.new(scale.outputs['Vector'],node.inputs['Vector'])
        maps[kind]=node
    mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX'
    mix.inputs[0].default_value=c['color_mix']
    mix.inputs[1].default_value=p.inputs['Base Color'].default_value
    links.new(maps['diff'].outputs['Color'],mix.inputs[2])
    links.new(mix.outputs[0],p.inputs['Base Color'])
    links.new(maps['rough'].outputs['Color'],p.inputs['Roughness'])
    bump=nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value=c['bump_strength']
    bump.inputs['Distance'].default_value=c['bump_distance_m']
    # Preserve the procedural corduroy and grain, then add image-space height detail.
    old=p.inputs['Normal'].links[0].from_socket
    links.new(old,bump.inputs['Normal'])
    links.new(maps['bump'].outputs['Color'],bump.inputs['Height'])
    links.new(bump.outputs['Normal'],p.inputs['Normal'])
    assert not nodes.get('Material Output').inputs['Displacement'].is_linked
    return m


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--config',type=Path,required=True)
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs')
    c=tomllib.loads(a.config.read_text())
    assert sha(ROOT/c['source']['p1_blend'])==c['source']['p1_sha256']
    s=bpy.context.scene;s.camera=s.objects['Preview_main']
    before=environment_signature();contract=render_contract(s)
    write(out/'environment-before.json',before)
    report=dict(blender=bpy.app.version_string,build=bpy.app.build_hash.decode(),config=c,baseline=render(s,out/'snow-baseline.png'))
    write(out/'snow-comparison.json',report)
    terrain=s.objects['Snow_terrain']
    for slot in terrain.material_slots:slot.material=pbr_material(slot.material,c['snow'])
    assert environment_signature()==before,'GEOMETRY_CHANGED'
    assert render_contract(s)==contract,'RENDER_CONDITIONS_CHANGED'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'snow-pbr-candidate.blend'))
    report['pbr']=render(s,out/'snow-pbr.png')
    report['identical_render_contract']=report['baseline']['contract']==report['pbr']['contract']
    report['identical_environment_geometry']=environment_signature()==before
    report['time_ratio']=report['pbr']['seconds']/report['baseline']['seconds']
    report['external_texture_bytes']=sum(p.stat().st_size for p in (ROOT/c['snow']['asset']).glob('*.png'))
    report['displacement_used']=False
    report['status']='COMPARISON_RENDERED_AWAITING_VISUAL_DECISION'
    write(out/'snow-comparison.json',report)
    print('SNOW_COMPARISON_COMPLETE',json.dumps(report['time_ratio']))


if __name__=='__main__':main()
