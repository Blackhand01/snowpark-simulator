"""Rebuild only the copied P1 environment into an actual downhill installation."""
import hashlib,json,math,random
import bpy
from mathutils import Vector
from refine_profile import solve,height,elevation,grade
from build_scene import mesh_object,camera


def mesh(name,vertices,faces,col,mat,smooth=False):
    o=mesh_object(name,vertices,faces,col,mat)
    if smooth:
        for p in o.data.polygons:p.use_smooth=True
    return o


def closed_box(name,x0,x1,y0,y1,zbottom,ztop,col,mat):
    corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    verts=[(x,y,fun(x,y)) for fun in [zbottom,ztop] for x,y in corners]
    faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    return mesh(name,verts,faces,col,mat)


def build(c):
    s=bpy.context.scene;s.name='Refined_Static_Snowpark'
    col=bpy.data.collections['P1_Snowpark']
    # This process opened a frozen P1 copy. No user file is reset or saved here.
    for obj in list(col.all_objects):bpy.data.objects.remove(obj,do_unlink=True)
    col.name='REF_Environment'
    snow,groom,steel=[bpy.data.materials[n] for n in ['Snow_loose','Snow_groomed','Worn_galvanized_steel']]
    dark=bpy.data.materials['Dark_steel_endcaps'];rock=bpy.data.materials['Alpine_rock']
    t=c['terrain'];p=solve(t);length=p['horizontal_length_m'];half=length/2;w=t['width_m']/2
    nx,ny=2*math.ceil(w/t['grid_step_m']),math.ceil(length/t['grid_step_m'])
    verts=[(x,y,height(x,y,t,p)) for j in range(ny+1) for i in range(nx+1)
           for x,y in [(-w+2*w*i/nx,-half+length*j/ny)]]
    faces=[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)]
    ground=mesh('Snow_terrain',verts,faces,col,groom,True);ground.data.materials.append(snow)
    for poly in ground.data.polygons:
        poly.material_index=int(abs(poly.center.x)>w-3 or (abs(poly.center.x)<.8 and abs(poly.center.y)<4))
    m=ground.modifiers.new('Terrain_volume','SOLIDIFY');m.thickness=t['thickness_m']
    # One continuous perimeter apron: exact core boundary, no gaps at the run ends.
    perimeter=[(-w+2*w*i/nx,-half) for i in range(nx+1)]
    perimeter += [(w,-half+length*j/ny) for j in range(1,ny+1)]
    perimeter += [(-w+2*w*i/nx,half) for i in range(nx-1,-1,-1)]
    perimeter += [(-w,-half+length*j/ny) for j in range(ny-1,0,-1)]
    def surrounding_height(x,y):
        yy=max(-half,min(half,y))
        base=elevation(yy,p)+grade(yy,p)*(y-yy)
        base+=t['cross_grade']*x+t['ripple_m']*math.sin(2*math.pi*x/12)*math.sin(2*math.pi*y/length)
        side=.007*max(0,abs(x)-w)**1.35
        radius=math.hypot(x,.9*y);u=max(0,min(1,(radius-100)/100));envelope=u*u*(3-2*u)
        a=math.atan2(y,x)
        peaks=19+6*math.sin(3*a)+5*math.cos(7*a)+3*math.sin(.08*x)*math.cos(.07*y)
        return base+side+envelope*peaks
    rings=18;count=len(perimeter);vx=[]
    for ring in range(rings+1):
        offset=240*(ring/rings)**1.8
        for x,y in perimeter:
            xx,yy=x*(1+offset/w),y*(1+offset/half)
            vx.append((xx,yy,surrounding_height(xx,yy)))
    fs=[(j*count+i,(j+1)*count+i,(j+1)*count+(i+1)%count,j*count+(i+1)%count)
        for j in range(rings) for i in range(count)]
    mesh('Alpine_background_360',vx,fs,col,snow,True)
    # Round rail is a straight fabricated tube, pitched independently of the terrain.
    r=c['rail'];radius=r['diameter_m']/2;angle=math.atan(r['longitudinal_grade'])
    axis=Vector((0,math.cos(angle),math.sin(angle)));up=Vector((0,-math.sin(angle),math.cos(angle)))
    rail_origin=Vector((0,0,r['center_height_m']));n=r['radial_segments'];vx=[]
    for distance in [-r['length_m']/2,r['length_m']/2]:
        for rad in [radius,radius-r['wall_m']]:
            for i in range(n):
                theta=2*math.pi*i/n
                vx.append(tuple(rail_origin+axis*distance+Vector((rad*math.cos(theta),0,0))+up*(rad*math.sin(theta))))
    fs=[]
    for i in range(n):
        k=(i+1)%n;fs.extend([(i,2*n+i,2*n+k,k),(n+i,n+k,3*n+k,3*n+i),(i,k,n+k,n+i),(2*n+i,3*n+i,3*n+k,2*n+k)])
    tube=mesh('Rail_tube',vx,fs,col,steel)
    for f in tube.data.polygons:f.use_smooth=f.index%4<2
    for label,distance in [('front',-r['length_m']/2+.012),('back',r['length_m']/2-.012)]:
        vx=[]
        for delta in [-.006,.006]:
            for i in range(n):
                a=2*math.pi*i/n
                vx.append(tuple(rail_origin+axis*(distance+delta)+Vector(((radius-r['wall_m'])*math.cos(a),0,0))+up*((radius-r['wall_m'])*math.sin(a))))
        fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        mesh('Rail_end_'+label,vx,fs,col,dark)
    supports=[]
    for index,y in enumerate(r['support_y_m']):
        # Saddle plate is tangent to the underside of the tube and shares its pitch.
        center_z=r['center_height_m']+r['longitudinal_grade']*y-radius/math.cos(angle)
        top=lambda x,yy,z=center_z,y0=y:z+r['longitudinal_grade']*(yy-y0)
        saddle=closed_box(f'Saddle_{index}',-.18,.18,y-.11,y+.11,
                         lambda x,yy:top(x,yy)-.035,top,col,steel)
        fw,fl=r['foot_half_width_m'],r['foot_half_length_m']
        footing=closed_box(f'Footing_{index}',-fw,fw,y-fl,y+fl,
                          lambda x,yy:height(x,yy,t,p),lambda x,yy:height(x,yy,t,p)+.045,col,dark)
        # Two vertical legs meet the terrain-fitted footing and tilted saddle exactly.
        for side,x in [('L',-.13),('R',.13)]:
            bottom=lambda xx,yy:height(xx,yy,t,p)+.045
            end=lambda xx,yy:top(xx,yy)-.035
            post=closed_box(f'Support_{index}_{side}',x-.035,x+.035,y-.035,y+.035,bottom,end,col,steel)
            supports.append(post.name)
    for i,(x,y) in enumerate([(-10,20),(11,-25),(-11,55),(12,-62)]):
        z=height(x,y,t,p)
        o=closed_box(f'Marker_{i}',x-.018,x+.018,y-.018,y+.018,lambda a,b:z,lambda a,b:z+1.3,col,dark)
    sun=bpy.data.lights.new('Winter_sun','SUN');sun.energy=4;sun.angle=math.radians(5)
    o=bpy.data.objects.new('Winter_sun',sun);col.objects.link(o);o.rotation_euler=tuple(math.radians(v) for v in [27,-22,-35])
    def cam(name,pos,target,lens=38,ortho=None):
        o=camera(name,pos,target,lens,col)
        if ortho:o.data.type='ORTHO';o.data.ortho_scale=ortho
        return o
    main=cam('Preview_main',(-6.3,-10.5,height(-6.3,-10.5,t,p)+3.7),(0,1,height(0,1,t,p)+.8),34)
    cam('Preview_slope',(145,0,25),(0,0,0),ortho=185)
    cam('Preview_rail',(4.5,-3.8,2.0),(0,0,.35),44)
    cam('Preview_overview',(-80,-100,135),(0,0,0),ortho=190)
    s.camera=main;s['milestone']='REFINED_STATIC_ENVIRONMENT';s['downhill_axis']='-Y';s['vertical_axis']='+Z'
    s['config_json']=json.dumps(c,sort_keys=True);s['profile_json']=json.dumps(p)
    s.render.resolution_x=c['render']['width'];s.render.resolution_y=c['render']['height']
    s.cycles.samples=c['render']['samples'];s.cycles.seed=c['render']['seed'];s.render.threads=c['render']['threads']
    for obj in s.objects:obj.select_set(False)
    tube.select_set(True);bpy.context.view_layer.objects.active=tube
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                v=area.spaces.active;v.region_3d.view_location=(0,0,.4);v.region_3d.view_distance=12
                v.region_3d.view_rotation=main.rotation_euler.to_quaternion();v.region_3d.view_perspective='PERSP'
                v.clip_end=1000;v.overlay.show_extras=False
    bpy.context.view_layer.update()
    return s,p


def fingerprint(scene):
    import array,struct
    result={}
    for o in sorted(scene.objects,key=lambda o:o.name):
        if o.type not in ['MESH','ARMATURE']:continue
        h=hashlib.sha256()
        if o.type=='MESH':
            data=array.array('f',[0])*(3*len(o.data.vertices));o.data.vertices.foreach_get('co',data);h.update(data.tobytes())
            for f in o.data.polygons:h.update(struct.pack('<'+'I'*len(f.vertices),*f.vertices))
        else:
            for b in o.data.bones:h.update(json.dumps((b.name,list(b.head_local),list(b.tail_local),b.parent.name if b.parent else None)).encode())
        result[o.name]=dict(type=o.type,geometry=h.hexdigest(),matrix=[list(r) for r in o.matrix_world])
    return result


def stable_fingerprint(scene):
    """Persisted hierarchy transforms, independent of hidden-object evaluation caches."""
    result=fingerprint(scene)
    for name,entry in result.items():
        o=scene.objects[name]
        del entry['matrix']
        entry.update(matrix_basis=[list(r) for r in o.matrix_basis],
                     matrix_parent_inverse=[list(r) for r in o.matrix_parent_inverse],
                     parent=o.parent.name if o.parent else None,parent_type=o.parent_type,parent_bone=o.parent_bone,
                     hidden_viewport=o.hide_viewport,hidden_render=o.hide_render)
    return result
