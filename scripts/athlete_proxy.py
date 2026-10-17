"""Procedural skier with a standard named FK bone hierarchy and rigid skin weights.

An articulated mannequin for scale/rig checks; no imported humanoid, action or trick.
"""
import math
import bpy
from mathutils import Vector


def collection(name,parent):
    c=bpy.data.collections.new(name);parent.children.link(c);return c


def move(obj,col):
    for old in list(obj.users_collection):old.objects.unlink(obj)
    col.objects.link(obj)


def material(name,color,metallic=0,roughness=.55):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=roughness
    return m


def build(scene,c):
    assert 'P2_Athlete' not in bpy.data.collections,'ATHLETE_ALREADY_PRESENT'
    parent=collection('P2_Athlete',scene.collection)
    cols={n:collection('ATH_'+n,parent) for n in ['Body','Rig','Skis','Boots','Bindings','Helmet','Goggles','Poles','Backpack']}
    mats={'jacket':material('ATH_Orange_jacket',(.88,.13,.025)),
          'pants':material('ATH_Navy_pants',(.022,.055,.10)),
          'skin':material('ATH_Face',(.60,.36,.23)),
          'black':material('ATH_Rubber_gloves',(.015,.021,.028)),
          'white':material('ATH_Helmet_shell',(.83,.88,.92),.15,.3),
          'lens':material('ATH_Goggle_lens',(.025,.23,.35),.7,.16),
          'ski':material('ATH_Ski_teal',(.015,.28,.31),.25,.3),
          'metal':material('ATH_Equipment_metal',(.24,.29,.32),.8,.3)}
    s=c['height_m']/1.82;half=c['stance_width_m']/2
    V=lambda xyz:tuple(x*s for x in xyz)
    bones={
        'root':((0,0,.04),(0,0,.30),None),
        'pelvis':((0,0,.88),(0,0,1.02),'root'),
        'spine':((0,0,1.02),(0,0,1.20),'pelvis'),
        'chest':((0,0,1.20),(0,0,1.40),'spine'),
        'neck':((0,0,1.40),(0,0,1.56),'chest'),
        'head':((0,0,1.56),(0,0,1.79),'neck')}
    for side,sign in [('L',1),('R',-1)]:
        bones.update({f'clavicle.{side}':((0,0,1.38),(sign*.20,0,1.38),'chest'),
          f'upper_arm.{side}':((sign*.20,0,1.38),(sign*.29,-.025,1.10),f'clavicle.{side}'),
          f'forearm.{side}':((sign*.29,-.025,1.10),(sign*.36,-.14,.94),f'upper_arm.{side}'),
          f'hand.{side}':((sign*.36,-.14,.94),(sign*.38,-.17,.86),f'forearm.{side}'),
          f'thigh.{side}':((sign*.14,0,.91),(sign*.18,-.025,.54),'pelvis'),
          f'shin.{side}':((sign*.18,-.025,.54),(sign*half/s,0,.16),f'thigh.{side}'),
          f'foot.{side}':((sign*half/s,0,.16),(sign*half/s,-.20,.10),f'shin.{side}'),
          f'toe.{side}':((sign*half/s,-.20,.10),(sign*half/s,-.31,.10),f'foot.{side}')})
    arm=bpy.data.armatures.new('ATH_Standard_FK_skeleton')
    rig=bpy.data.objects.new('Athlete_Rig',arm);cols['Rig'].objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name,(head,tail,par) in bones.items():
        b=arm.edit_bones.new(name);b.head=V(head);b.tail=V(tail)
        if par:b.parent=arm.edit_bones[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.show_in_front=True;arm.display_type='STICK'
    rig['rig_type']='FK articulated mannequin; no IK, biomechanical or trick validation'
    rig['forward_axis']='local -Y';rig['up_axis']='local +Z'

    def bind(obj,name,mat,col,bone):
        obj.name=name;move(obj,cols[col]);obj.data.materials.append(mats[mat])
        bpy.context.view_layer.objects.active=obj
        for o in bpy.context.selected_objects:o.select_set(False)
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        group=obj.vertex_groups.new(name=bone);group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
        mod=obj.modifiers.new('ATH_Skin','ARMATURE');mod.object=rig
        obj.parent=rig;obj['bound_bone']=bone
        return obj

    def ellipsoid(name,center,radii,mat,col,bone,scaled=True):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1,location=V(center) if scaled else center)
        o=bpy.context.object;o.scale=V(radii) if scaled else radii
        for p in o.data.polygons:p.use_smooth=True
        return bind(o,name,mat,col,bone)

    def segment(name,a,b,radius,mat,col,bone):
        a,b=Vector(V(a)),Vector(V(b));delta=b-a
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=1,location=(a+b)/2)
        o=bpy.context.object;o.scale=(radius*s,radius*s,delta.length/2+.025*s)
        o.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
        for p in o.data.polygons:p.use_smooth=True
        return bind(o,name,mat,col,bone)

    def box(name,center,halfsize,mat,col,bone):
        bpy.ops.mesh.primitive_cube_add(size=2,location=center)
        o=bpy.context.object;o.scale=halfsize
        o=bind(o,name,mat,col,bone)
        mod=o.modifiers.new('ATH_Soft_edges','BEVEL');mod.width=.015*s;mod.segments=3
        return o

    ellipsoid('ATH_Jacket',(0,0,1.21),(.245,.155,.285),'jacket','Body','chest')
    ellipsoid('ATH_Pelvis',(0,0,.91),(.215,.14,.145),'pants','Body','pelvis')
    ellipsoid('ATH_Collar',(0,0,1.465),(.105,.105,.065),'jacket','Body','neck')
    ellipsoid('ATH_Head',(0,-.012,1.63),(.115,.115,.135),'skin','Body','head')
    ellipsoid('ATH_Helmet',(0,.005,1.69),(.132,.142,.13),'white','Helmet','head')
    ellipsoid('ATH_Goggle_strap',(0,0,1.68),(.139,.15,.027),'black','Goggles','head')
    ellipsoid('ATH_Goggle_frame',(0,-.139,1.68),(.117,.033,.052),'jacket','Goggles','head')
    ellipsoid('ATH_Goggle_lens',(0,-.16,1.68),(.105,.017,.039),'lens','Goggles','head')
    ellipsoid('ATH_Backpack',(0,.18,1.23),(.17,.105,.22),'pants','Backpack','chest')
    for side,sign in [('L',1),('R',-1)]:
        for stem,radius,mat in [('upper_arm',.078,'jacket'),('forearm',.065,'jacket'),('thigh',.097,'pants'),('shin',.078,'pants')]:
            a,b,_=bones[f'{stem}.{side}'];segment('ATH_'+stem+'_'+side,a,b,radius,mat,'Body',f'{stem}.{side}')
        ellipsoid('ATH_Knee_'+side,(sign*.18,-.025,.54),(.09,.085,.09),'pants','Body',f'shin.{side}')
        ellipsoid('ATH_Glove_'+side,(sign*.375,-.16,.90),(.063,.07,.085),'black','Body',f'hand.{side}')
        x=sign*half
        box('ATH_Boot_'+side,(x,-.07*s,.135*s),(.075*s,.17*s,.095*s),'black','Boots',f'foot.{side}')
        box('ATH_Binding_'+side,(x,-.045*s,.062*s),(.073*s,.225*s,.025*s),'metal','Bindings',f'foot.{side}')
        # Closed ski mesh: narrow waist, wider rounded tips and raised shovel.
        length,width=c['ski_length_m'],c['ski_width_m'];verts=[]
        for i in range(17):
            t=i/16;y=(t-.5)*length
            w=width/2*(.85+.18*abs(2*t-1))
            if i in [0,16]:w*=.42
            rise=.11*max(0,(.20-t)/.20)**2+.045*max(0,(t-.88)/.12)**2
            verts.extend([(x-w,y,rise),(x+w,y,rise),(x+w,y,rise+.035),(x-w,y,rise+.035)])
        faces=[(3,2,1,0),(64,65,66,67)]
        for i in range(16):
            for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
        data=bpy.data.meshes.new('ATH_Ski_mesh_'+side);data.from_pydata(verts,[],faces);data.update()
        o=bpy.data.objects.new('ATH_Ski_'+side,data);cols['Skis'].objects.link(o)
        bind(o,'ATH_Ski_'+side,'ski','Skis',f'foot.{side}')
        hand=(sign*.375,-.16,.91);tip=(sign*.55,-.28,.065)
        segment('ATH_Pole_'+side,hand,tip,.008,'metal','Poles',f'hand.{side}')
        ellipsoid('ATH_Pole_basket_'+side,tip,(.045,.045,.008),'black','Poles',f'hand.{side}')
    # Fit rigid equipment above the existing terrain using actual mesh intersections.
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    x0,y0=c['position_xy_m'];slope=.025
    ground=[]
    for sign in [-1,1]:
        for y in [-.6,0,.6]:
            hit,point,_,_,obj,_=scene.ray_cast(deps,Vector((x0+sign*half,y0+y,10)),Vector((0,0,-1)),distance=30)
            assert hit and obj.name=='Snow_terrain',(obj.name if obj else None)
            ground.append(point.z-slope*y)
    rig.location=(x0,y0,max(ground)+c['ground_clearance_m'])
    rig.rotation_euler.x=math.atan(slope)
    rig['height_parameter_m']=c['height_m']
    rig['placement']='Standing beside the rail, skis fitted to terrain; no simulated contacts'
    for o in scene.objects:o.select_set(False)
    rig.select_set(True);bpy.context.view_layer.objects.active=rig
    scene['milestone']='P2_STATIC_RIGGED_PROXY'
    bpy.context.view_layer.update()
    return rig,dict(bones=len(arm.bones),collections=list(cols),objects=len(parent.all_objects),rig_location=list(rig.location),
                    rig_type='FK with one-bone skin weights per segmented part',motion_actions_created=0,
                    dimensions_source='Configured artistic adult proportions, not anthropometric validation')
