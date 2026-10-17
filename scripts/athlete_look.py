"""Static tailored wardrobe and equipment on the existing 22-bone skier.

Only changes the Athlete collection in a copy of the refined scene. Metres,
local +Z up / -Y forward. No cloth simulation, action, third-party model or logo.
"""
import math
import bpy
from mathutils import Vector
from build_scene import material

TAU=2*math.pi


class Tailor:
    def __init__(self,config):
        self.c=config;self.rig=bpy.data.objects['Athlete_Rig'];self.created=[]
        self.col=bpy.data.collections.new('LOOK_Tailored_Athlete')
        bpy.data.collections['P2_Athlete'].children.link(self.col)
        self.m={}

    def mesh(self,name,vertices,faces,mat,bone=None,weights=None):
        data=bpy.data.meshes.new('LOOK_'+name);data.from_pydata(vertices,[],faces);data.update()
        o=bpy.data.objects.new('LOOK_'+name,data);self.col.objects.link(o)
        data.materials.append(self.m[mat]);o.parent=self.rig
        for f in data.polygons:f.use_smooth=True
        if weights:
            groups={}
            for v in data.vertices:
                for key,value in weights(v.co).items():
                    if value>0:
                        if key not in groups:groups[key]=o.vertex_groups.new(name=key)
                        groups[key].add([v.index],value,'REPLACE')
        else:
            group=o.vertex_groups.new(name=bone);group.add(list(range(len(vertices))),1,'REPLACE')
        modifier=o.modifiers.new('LOOK_Skin','ARMATURE');modifier.object=self.rig
        self.created.append(o);return o

    def tube(self,name,points,radii,mat,bone,n=16):
        p=[Vector(v) for v in points];vx=[]
        for j,center in enumerate(p):
            direction=(p[min(j+1,len(p)-1)]-p[max(0,j-1)]).normalized()
            helper=Vector((0,1,0)) if abs(direction.y)<.9 else Vector((1,0,0))
            u=direction.cross(helper).normalized();v=direction.cross(u).normalized()
            rad=radii[j] if isinstance(radii,list) else radii
            rx,ry=rad if isinstance(rad,tuple) else (rad,rad)
            vx.extend(tuple(center+u*(rx*math.cos(TAU*i/n))+v*(ry*math.sin(TAU*i/n))) for i in range(n))
        faces=[tuple(reversed(range(n))),tuple(range((len(p)-1)*n,len(p)*n))]
        faces += [(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(p)-1) for i in range(n)]
        return self.mesh(name,vx,faces,mat,bone)

    def ellipsoid(self,name,center,radii,mat,bone,n=32,rows=18):
        # Ring construction avoids operator-dependent primitive face ordering.
        vx=[]
        for j in range(1,rows):
            phi=math.pi*j/rows
            vx.extend((center[0]+radii[0]*math.sin(phi)*math.cos(TAU*i/n),
                       center[1]+radii[1]*math.sin(phi)*math.sin(TAU*i/n),
                       center[2]+radii[2]*math.cos(phi)) for i in range(n))
        vx += [(center[0],center[1],center[2]+radii[2]),(center[0],center[1],center[2]-radii[2])]
        top,bottom=len(vx)-2,len(vx)-1;faces=[]
        for j in range(rows-2):
            for i in range(n):faces.append((j*n+i,(j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n))
        faces += [(top,i,(i+1)%n) for i in range(n)]
        base=(rows-2)*n;faces += [(bottom,base+(i+1)%n,base+i) for i in range(n)]
        return self.mesh(name,vx,faces,mat,bone)

    def box(self,name,center,half,mat,bone,bevel=.005):
        vx=[(center[0]+x*half[0],center[1]+y*half[1],center[2]+z*half[2])
            for z in [-1,1] for y in [-1,1] for x in [-1,1]]
        faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(1,3,7,5),(3,2,6,7),(2,0,4,6)]
        o=self.mesh(name,vx,faces,mat,bone)
        if bevel:
            m=o.modifiers.new('LOOK_Rounded_edges','BEVEL');m.width=bevel;m.segments=3
            for f in o.data.polygons:f.use_smooth=False
        return o

    def fabric(self,key,color,rough=.76):
        m=material('LOOK_'+key,color,roughness=rough);self.m[key]=m
        node=m.node_tree.nodes.get('Principled BSDF');node.inputs['Sheen Weight'].default_value=.22
        node.inputs['Specular IOR Level'].default_value=.3
        ns,links=m.node_tree.nodes,m.node_tree.links
        tc=ns.new('ShaderNodeTexCoord');noise=ns.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value=380;noise.inputs['Detail'].default_value=2
        links.new(tc.outputs['Object'],noise.inputs['Vector'])
        bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.2
        bump.inputs['Distance'].default_value=self.c['cloth_micro_bump_m']
        links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],node.inputs['Normal'])
        return m

    def materials(self):
        self.fabric('Pants',(.012,.014,.018),.83)
        self.fabric('Shirt',(.005,.0065,.009),.80)
        self.fabric('Base_layer',(.008,.010,.014),.58)
        self.fabric('Seam',(.019,.021,.026),.80)
        self.fabric('Glove',(.55,.53,.46),.52)
        for key,color,metal,rough in [('Rubber',(.006,.007,.009),0,.65),('Shell',(.009,.012,.016),.05,.29),
             ('Boot',(.022,.028,.033),.08,.33),('Sole',(.013,.015,.017),0,.68),
             ('Metal',(.20,.23,.25),.88,.23),('Accent',(.35,.095,.032),.25,.35),
             ('Skin',(.39,.225,.145),0,.53),('Lip',(.22,.095,.065),0,.55),
             ('Grip',(.018,.24,.25),.1,.45)]:self.m[key]=material('LOOK_'+key,color,metal,rough)
        p=self.m['Skin'].node_tree.nodes.get('Principled BSDF');p.inputs['Subsurface Weight'].default_value=.07
        m=material('LOOK_Amber_mirror',(.65,.25,.035),.95,.12);self.m['Lens']=m
        ns,links=m.node_tree.nodes,m.node_tree.links;p=ns.get('Principled BSDF');p.inputs['Coat Weight'].default_value=.55
        tc=ns.new('ShaderNodeTexCoord');sep=ns.new('ShaderNodeSeparateXYZ');ramp=ns.new('ShaderNodeValToRGB')
        links.new(tc.outputs['Generated'],sep.inputs[0]);links.new(sep.outputs['X'],ramp.inputs[0])
        cr=ramp.color_ramp;cr.elements.remove(cr.elements[1])
        for i,(pos,col) in enumerate([(0,(.17,.025,.055,1)),(.24,(.52,.11,.016,1)),(.55,(.72,.39,.035,1)),(.88,(.29,.19,.025,1)),(1,(.12,.07,.028,1))]):
            e=cr.elements[0] if i==0 else cr.elements.new(pos);e.position=pos;e.color=col
        links.new(ramp.outputs[0],p.inputs['Base Color'])

    def pants(self):
        n=64;vx=[];faces=[];tops=[];w=self.c;scale=w['fold_scale']
        rings=[(w['trouser_cuff_m'],.190,.087,.090),(.26,.190,.110,.112),(.30,.190,.145,.135),
               (.35,.188,.159,.150),(.42,.185,.158,.151),(.51,.180,.157,.145),
               (.60,.173,.151,.142),(.69,.165,.151,.145),(w['crotch_height_m'],.157,.151,.148)]
        for side,sign in [('L',1),('R',-1)]:
            start=len(vx)
            for j,(z,cx,rx,ry) in enumerate(rings):
                for i in range(n):
                    a=TAU*i/n
                    fold=scale*(.0045*math.sin(5*a+z*19+sign)+.004*math.sin(9*a-z*17))
                    fold+=scale*.010*math.exp(-((z-.33)/.10)**2)*math.sin(4*a+z*38+sign)
                    zz=z+.006*math.sin(3*a+sign)*math.exp(-((z-.32)/.11)**2)
                    vx.append((sign*cx+(rx+fold)*math.cos(a),-.008*math.sin(z*8)+(ry+fold)*math.sin(a),zz))
            faces.append(tuple(reversed(range(start,start+n))))
            for j in range(len(rings)-1):
                for i in range(n):faces.append((start+j*n+i,start+j*n+(i+1)%n,start+(j+1)*n+(i+1)%n,start+(j+1)*n+i))
            tops.append(start+(len(rings)-1)*n)
        left,right=tops
        # A true crotch bridge joins the two open leg tubes into one garment.
        for i in range(n//4,3*n//4):
            r0=(n//2-i)%n;r1=(n//2-i-1)%n
            faces.append((left+i,right+r0,right+r1,left+i+1))
        border=[left+(i%n) for i in range(3*n//4,5*n//4+1)]+[right+i for i in range(n//4,3*n//4+1)]
        angles=[math.atan2(vx[i][1]/.148,vx[i][0]/.308) for i in border]
        for z,rx,ry in [(.87,.275,.162),(.94,.246,.152),(1.0,.217,.142)]:
            current=[]
            for a in angles:
                current.append(len(vx));vx.append((rx*math.cos(a),ry*math.sin(a),z))
            for j in range(len(border)):
                k=(j+1)%len(border);faces.append((border[j],border[k],current[k],current[j]))
            border=current
        faces.append(tuple(border))
        def weights(v):
            side='L' if v.x>=0 else 'R'
            pelvis=max(0,min(1,(v.z-.72)/.18));thigh=max(0,min(1,(v.z-.43)/.21))
            return {'pelvis':pelvis,'thigh.'+side:(1-pelvis)*thigh,'shin.'+side:(1-pelvis)*(1-thigh)}
        o=self.mesh('Continuous_pants',vx,faces,'Pants',weights=weights)
        # Cuffs, pockets and seams are small separate skinned details.
        for side,sgn in [('L',1),('R',-1)]:
            points=[(sgn*.19+.089*math.cos(TAU*i/48),.091*math.sin(TAU*i/48),w['trouser_cuff_m']+.004) for i in range(49)]
            self.tube('Cuff_stitch_'+side,points,.0012,'Seam','shin.'+side,8)
            # Sewn lines follow actual leg-ring vertices; no floating pocket strokes.
            a=-math.pi/4 if sgn>0 else 5*math.pi/4;path=[]
            for z,cx,rx,ry in reversed(rings[5:8]):
                fold=scale*(.0045*math.sin(5*a+z*19+sgn)+.004*math.sin(9*a-z*17))
                fold+=scale*.010*math.exp(-((z-.33)/.10)**2)*math.sin(4*a+z*38+sgn)
                zz=z+.006*math.sin(3*a+sgn)*math.exp(-((z-.32)/.11)**2)
                path.append((sgn*cx+(rx+fold+.001)*math.cos(a),-.008*math.sin(z*8)+(ry+fold+.001)*math.sin(a),zz))
            self.tube('Pocket_piping_'+side,path,.0012,'Seam','thigh.'+side,8)
        return o

    def shirt(self):
        n=72;vx=[];faces=[];hem=self.c['shirt_hem_m']
        rings=[(hem,.295,.184),(hem+.015,.294,.184),(.94,.270,.171),(1.05,.245,.157),
               (1.17,.249,.155),(1.30,.256,.154),(1.38,.249,.145),(1.43,.221,.126),(1.478,.080,.078)]
        for z,rx,ry in rings:
            for i in range(n):
                a=TAU*i/n
                amplitude=(.003+.005*max(0,1-(z-hem)/.35))*self.c['fold_scale']
                fold=amplitude*(math.sin(7*a+12*z)+.4*math.sin(13*a-8*z))
                zz=z+.007*math.sin(a+.7)*max(0,1-(z-hem)/.14)
                vx.append(((rx+fold)*math.cos(a),(ry+fold)*math.sin(a),zz))
        for j in range(len(rings)-1):
            for i in range(n):faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
        # Thin fabric thickness, not a dense displacement surface.
        def weights(v):
            chest=max(0,min(1,(v.z-1.08)/.22));return {'spine':1-chest,'chest':chest}
        o=self.mesh('Long_T_shirt',vx,faces,'Shirt',weights=weights)
        solid=o.modifiers.new('LOOK_Fabric_thickness','SOLIDIFY');solid.thickness=.0015
        for z,rx,ry,label in [(hem+.012,.296,.187,'Hem'),(1.478,.081,.079,'Collar')]:
            p=[(rx*math.cos(TAU*i/72),ry*math.sin(TAU*i/72),z) for i in range(73)]
            self.tube(label,p,.0014,'Seam','spine' if label=='Hem' else 'chest',8)
        for side,sgn in [('L',1),('R',-1)]:
            shoulder=Vector((sgn*.20,0,1.38));elbow=Vector((sgn*.29,-.025,1.10));wrist=Vector((sgn*.36,-.14,.94))
            # Compression sleeves form one visually continuous elbow, under short T sleeves.
            pts=[shoulder,shoulder.lerp(elbow,.65),elbow,elbow.lerp(wrist,.45),wrist]
            under=self.tube('Compression_sleeve_'+side,pts,[.063,.055,.051,.046,.036],'Base_layer','upper_arm.'+side,32)
            under.vertex_groups.clear();a=under.vertex_groups.new(name='upper_arm.'+side);b=under.vertex_groups.new(name='forearm.'+side)
            for v in under.data.vertices:
                t=max(0,min(1,(1.14-v.co.z)/.08))
                if t<1:a.add([v.index],1-t,'REPLACE')
                if t:b.add([v.index],t,'REPLACE')
            end=shoulder.lerp(elbow,.64)
            self.tube('Short_sleeve_'+side,[shoulder,shoulder.lerp(elbow,.25),end],[.092,.090,.084],'Shirt','upper_arm.'+side,40)
            axis=(elbow-shoulder).normalized();u=axis.cross(Vector((0,1,0))).normalized();v=axis.cross(u)
            self.tube('Sleeve_hem_'+side,[tuple(end+u*(.085*math.cos(TAU*i/48))+v*(.085*math.sin(TAU*i/48))) for i in range(49)],.0015,'Seam','upper_arm.'+side,8)

    def head(self):
        n=64;vx=[];rings=[(1.492,.052,.064,0),(1.515,.071,.079,-.006),(1.55,.086,.091,-.004),
             (1.59,.101,.098,-.002),(1.64,.106,.105,0),(1.69,.105,.106,.002),(1.735,.097,.095,.006)]
        for z,rx,ry,cy in rings:
            for i in range(n):
                a=TAU*i/n;front=max(0,-math.sin(a))
                # Cheek/jaw contours are built into the mesh rather than a featureless sphere.
                yy=cy+ry*math.sin(a)-.004*front**4*math.exp(-((z-1.59)/.04)**2)
                vx.append((rx*math.cos(a),yy,z))
        faces=[tuple(reversed(range(n))),tuple(range((len(rings)-1)*n,len(rings)*n))]
        faces += [(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(rings)-1) for i in range(n)]
        self.mesh('Face_jaw',vx,faces,'Skin','head')
        self.ellipsoid('Neck',(0,.012,1.484),(.062,.065,.071),'Skin','neck')
        self.ellipsoid('Nose_bridge',(0,-.104,1.604),(.018,.030,.034),'Skin','head')
        self.ellipsoid('Nose_tip',(0,-.124,1.59),(.023,.018,.014),'Skin','head')
        self.tube('Mouth_line',[(-.030,-.091,1.552),(0,-.096,1.549),(.030,-.091,1.552)],.0013,'Lip','head',8)
        # Black helmet: shaped lower opening, shell thickness and rubber rim.
        def helmet(theta,f):
            bottom=1.624+.105*max(0,-math.sin(theta))**3
            phi=math.acos((bottom-1.63)/.205)*(1-f)
            return (.137*math.sin(phi)*math.cos(theta),.009+.153*math.sin(phi)*math.sin(theta),1.63+.205*math.cos(phi))
        vx=[helmet(TAU*i/n,j/20*.995) for j in range(21) for i in range(n)]
        faces=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(20) for i in range(n)]
        faces.append(tuple(range(20*n,21*n)))
        o=self.mesh('Helmet_shell',vx,faces,'Shell','head');m=o.modifiers.new('LOOK_Shell_wall','SOLIDIFY');m.thickness=.004
        self.tube('Helmet_rim',[helmet(TAU*i/96,0) for i in range(97)],.003,'Rubber','head',8)
        for x in [-.075,-.040,.040,.075]:
            points=[]
            for y in [-.037,-.015,.012,.04]:
                z=1.63+.205*math.sqrt(max(0,1-(x/.137)**2-((y-.009)/.153)**2))+.0015
                points.append((x,y,z))
            self.tube('Helmet_vent_'+str(x),points,(.0035,.0013),'Rubber','head',8)
        for side,sgn in [('L',1),('R',-1)]:
            self.tube('Chin_strap_'+side,[(sgn*.12,.035,1.655),(sgn*.093,-.003,1.555),(sgn*.047,-.042,1.491),(0,-.036,1.48)],.004,'Rubber','head',10)
        self.box('Chin_buckle',(.025,-.041,1.485),(.013,.006,.008),'Shell','head',.003)
        self.goggles()

    def goggles(self):
        w=self.c['visor_width_m']/2;h=self.c['visor_height_m']/2;cx,cz=0,1.672
        # Superelliptic, cylindrical visor with a real nose cutout and wrap around the face.
        def boundary(a,expand=0):
            co,si=math.cos(a),math.sin(a)
            x=(w+expand)*math.copysign(abs(co)**.56,co)
            z=cz+(h+expand)*math.copysign(abs(si)**.58,si)
            if si<0:z+=.031*math.exp(-(x/.033)**2)
            return x,z
        def ysurface(x,z):return -.169+.075*(x/w)**2+.012*((z-cz)/h)**2
        n=96;rows=10;vx=[(0,ysurface(0,cz)-.002,cz)]
        for j in range(1,rows+1):
            f=j/rows
            for i in range(n):
                x,z=boundary(TAU*i/n);x*=f;z=cz+(z-cz)*f
                vx.append((x,ysurface(x,z)-.002,z))
        faces=[(0,1+(i+1)%n,1+i) for i in range(n)]
        for j in range(rows-1):
            a=1+j*n;b=a+n
            faces += [(a+i,a+(i+1)%n,b+(i+1)%n,b+i) for i in range(n)]
        self.mesh('Panoramic_visor',vx,[tuple(reversed(f)) for f in faces],'Lens','head')
        for expand,radius,label,mat in [(0,.0045,'Visor_frame','Rubber'),(.003,.002,'Visor_outer_rim','Shell')]:
            points=[]
            for i in range(n+1):
                x,z=boundary(TAU*i/n,expand);points.append((x,ysurface(x,z),z))
            self.tube(label,points,radius,mat,'head',10)
        # Broad textile strap follows the back of the helmet, separate from the visor.
        vx=[];steps=72
        for z in [cz-.023,cz+.023]:
            for i in range(steps+1):
                a=math.pi*i/steps;vx.append((.140*math.cos(a),.014+.155*math.sin(a),z))
        faces=[(i,i+1,steps+2+i,steps+1+i) for i in range(steps)]
        self.mesh('Goggle_textile_strap',vx,faces,'Base_layer','head')

    def equipment(self):
        for side,sgn in [('L',1),('R',-1)]:
            bone='foot.'+side;x=sgn*.19
            # A rounded anatomical shell, defined by foot cross-sections along Y.
            sections=[(-.244,.042,.098,.030),(-.22,.060,.111,.046),(-.16,.071,.125,.062),
                      (-.07,.072,.148,.082),(.015,.068,.173,.096),(.095,.063,.159,.083),(.13,.048,.133,.061)]
            vx=[];n=40
            for y,rx,z,rz in sections:
                for i in range(n):
                    a=TAU*i/n;vx.append((x+rx*math.cos(a),y,max(.069,z+rz*math.sin(a))))
            faces=[tuple(range(n)),tuple(reversed(range((len(sections)-1)*n,len(sections)*n)))]
            faces += [(j*n+i,(j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n) for j in range(len(sections)-1) for i in range(n)]
            self.mesh('Boot_shell_'+side,vx,faces,'Boot',bone)
            self.tube('Boot_cuff_'+side,[(x,.035,.17),(x,.023,.23),(x,.005,.30)],[(.070,.078),(.071,.074),(.064,.066)],'Shell',bone,48)
            self.tube('Boot_liner_'+side,[(x,.005,.285),(x,.002,.314)],[(.058,.059),(.059,.060)],'Base_layer',bone,40)
            self.box('Boot_sole_'+side,(x,-.055,.061),(.072,.190,.012),'Sole',bone,.009)
            self.box('Toe_lug_'+side,(x,-.239,.069),(.060,.019,.010),'Boot',bone,.004)
            self.box('Heel_lug_'+side,(x,.135,.069),(.057,.014,.010),'Boot',bone,.004)
            for j,(y,z,width) in enumerate([(-.16,.178,.063),(-.066,.218,.064),(-.048,.267,.060)]):
                self.box('Buckle_band_'+side+str(j),(x,y,z),(width,.012,.0035),'Rubber',bone,.002)
                self.box('Buckle_lever_'+side+str(j),(x+sgn*.044,y-.003,z+.006),(.021,.009,.004),'Metal',bone,.003)
            self.box('Boot_power_strap_'+side,(x,-.045,.295),(.062,.010,.010),'Accent',bone,.004)
            # Bindings now have separate rail, toe wings, heel housing and brake arms.
            self.box('Binding_track_'+side,(x,-.048,.045),(.057,.245,.009),'Metal',bone,.004)
            self.box('Toe_binding_'+side,(x,-.275,.081),(.061,.035,.034),'Shell',bone,.012)
            self.box('Toe_binding_cap_'+side,(x,-.280,.117),(.044,.024,.005),'Metal',bone,.004)
            for sign in [-1,1]:
                self.box('Toe_wing_'+side+str(sign),(x+sign*.057,-.237,.086),(.012,.032,.015),'Metal',bone,.006)
                self.tube('Brake_arm_'+side+str(sign),[(x+sign*.047,.11,.11),(x+sign*.071,.12,.078),(x+sign*.073,.02,.043)],.0028,'Metal',bone,10)
            self.box('Heel_binding_'+side,(x,.178,.089),(.052,.040,.042),'Shell',bone,.010)
            self.box('Heel_release_'+side,(x,.183,.133),(.043,.034,.007),'Accent',bone,.004)
            hand='hand.'+side;center=(sgn*.374,-.153,.903)
            self.ellipsoid('Leather_glove_'+side,center,(.042,.034,.067),'Glove',hand)
            self.tube('Glove_cuff_'+side,[(sgn*.36,-.139,.950),(sgn*.365,-.145,.928)],[.038,.041],'Rubber',hand,24)
            self.ellipsoid('Glove_thumb_'+side,(sgn*.343,-.175,.904),(.021,.029,.039),'Glove',hand,24,14)
            for j in range(3):
                z=.881+j*.019
                self.tube('Glove_finger_seam_'+side+str(j),[(sgn*.346,-.181,z),(sgn*.373,-.187,z-.002),(sgn*.400,-.178,z+.001)],.0008,'Seam',hand,6)
            self.tube('Pole_grip_'+side,[(sgn*.375,-.16,.87),(sgn*.375,-.16,.968)],.011,'Rubber',hand,20)
            self.ellipsoid('Pole_grip_cap_'+side,(sgn*.375,-.16,.972),(.013,.013,.005),'Grip',hand,20,10)
            self.tube('Wrist_loop_'+side,[(sgn*.375,-.16,.953),(sgn*.39,-.12,.956),(sgn*.415,-.12,.921),(sgn*.40,-.15,.89)],.002,'Rubber',hand,8)

    def build(self):
        self.materials()
        keep={'ATH_Ski_L','ATH_Ski_R','ATH_Pole_L','ATH_Pole_R','ATH_Pole_basket_L','ATH_Pole_basket_R'}
        hidden=[]
        # Snapshot first: changing hide_viewport invalidates Blender's collection cache.
        for o in list(bpy.data.collections['P2_Athlete'].all_objects):
            if o.type=='MESH' and o.name not in keep:
                hidden.append(o.name);o.hide_render=True;o.hide_viewport=True
        self.pants();self.shirt();self.head();self.equipment()
        bpy.context.view_layer.update()
        return dict(created_objects=len(self.created),created_vertices=sum(len(o.data.vertices) for o in self.created),
                    hidden_legacy_objects=hidden,rig_reused=self.rig.name,bones=len(self.rig.data.bones),
                    model_type='Procedurally tailored standard skier; approximate anatomy, no identity reconstruction',
                    external_assets_added=[],cloth_simulation=False,animation_created=False)
