"""Bake and inspect the complete reference rail slide in a new Blender scene.

This is articulated kinematics with geometric support fitting, not a rigid-body
or biomechanical simulation. The historical cork profiles remain reproducible.
"""
import csv
import json
import math
import tomllib

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

from animate_scene import controls, environment, points, pose
from build_scene import camera
from p2_support import ROOT, render, sha, write
from motion_profile import smooth
from rail_slide_profile import ballistic, sample, validate
from refine_profile import grade, solve


def articulated_pose(rig, s):
    pose(rig, s)  # Two-link leg solve keeps each ankle fixed without stretching.
    chest = rig.pose.bones['chest']
    rest = chest.bone.matrix_local.to_quaternion()
    torso = Quaternion((0, 0, 1), s['torso_yaw']) @ Quaternion((1, 0, 0), s['torso_pitch'])
    chest.rotation_mode = 'QUATERNION'
    chest.rotation_quaternion = rest.conjugated() @ torso @ rest
    bpy.context.view_layer.update()
    for side, sign in [('L', 1), ('R', -1)]:
        for stem, direction in [
            ('upper_arm', (sign*s['arm_spread'], -.09, -.23)),
            ('forearm', (sign*.065, -.18, -.15)),
        ]:
            b = rig.pose.bones[stem+'.'+side]
            head = b.head.copy()
            target = torso @ Vector(direction).normalized()
            q = (b.bone.tail_local-b.bone.head_local).rotation_difference(target) @ b.bone.matrix_local.to_quaternion()
            b.matrix = Matrix.LocRotScale(head, q, Vector((1, 1, 1)))
            bpy.context.view_layer.update()
        hand = rig.pose.bones['hand.'+side]
        hand.rotation_mode = 'XYZ'
        hand.rotation_euler.x = s['accessory_pitch']
    bpy.context.view_layer.update()


def set_camera(scene, trans, ground_z, c):
    cam = scene.objects['ANIM_Review']
    center = Vector((trans.location.x, trans.location.y,
                     .65*trans.location.z+.35*ground_z+.80))
    if 'air_trick' in c:
        center.z = trans.location.z+c['air_trick']['pivot_height_m']
    cam.location = center + Vector(c['render']['camera_offset_m'])
    cam.rotation_euler = (center-cam.location).to_track_quat('-Z', 'Y').to_euler()


def orientation(s, slope, c):
    ground = Euler((math.atan(slope), 0, 0)).to_quaternion()
    yaw = Quaternion((0, 0, 1), s['yaw'])
    if 'air_trick' not in c:
        return ground @ yaw
    k = c['air_trick']
    azimuth = math.radians(k['axis_azimuth_degrees'])
    tilt = Quaternion(Vector((math.cos(azimuth), math.sin(azimuth), 0)), math.radians(k['axis_tilt_degrees']))
    rotation = tilt @ Quaternion((0, 0, 1), s['air_spin']) @ tilt.conjugated()
    return ground @ rotation @ yaw


def left_marker(scene, col, tree, c):
    """A visible screen-left reference, outside the skier's rail corridor."""
    if 'left_marker_xy_m' not in c['render']:
        return
    x, y = c['render']['left_marker_xy_m']
    hit, *_ = tree.ray_cast(Vector((x, y, 30)), Vector((0, 0, -1)), 100)
    assert hit is not None
    vertices = [(x+.016*math.cos(i*math.pi/4), y+.016*math.sin(i*math.pi/4), hit.z+h)
                for h in [0, 1.55] for i in range(8)]
    faces = [tuple(reversed(range(8))), tuple(range(8, 16))]
    faces += [(i, (i+1)%8, (i+1)%8+8, i+8) for i in range(8)]
    mesh = bpy.data.meshes.new('ANIM_LeftMarker_mesh'); mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new('ANIM_LeftMarker', mesh); col.objects.link(obj)
    mat = bpy.data.materials.new('ANIM_MarkerOrange'); mat.diffuse_color = (1., .12, .01, 1.)
    mesh.materials.append(mat)


def linear_keys():
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    bag = strip.channelbag(slot)
                    if bag:
                        for curve in bag.fcurves:
                            for key in curve.keyframe_points:
                                key.interpolation = 'LINEAR'


def build(out, c):
    validate(c)
    m, r = c['motion'], c['rail_slide']
    assert sha(ROOT/c['source']['blend']) == c['source']['sha256']
    assert sha(ROOT/c['source']['reference_video']) == c['source']['reference_sha256']
    scene = bpy.context.scene
    write(out/'environment-before.json', environment())
    trans, orient = controls(scene)
    orient.rotation_mode = 'QUATERNION'
    rig = scene.objects['Athlete_Rig']
    if 'air_trick' in c:
        # Offset both sides of the orientation node to rotate about the pelvis.
        # This is an artistic pivot, not an inferred center of mass.
        pivot = c['air_trick']['pivot_height_m']
        orient.location.z = pivot
        rig.location.z = -pivot
    rig['rig_type'] = 'Articulated rail reference; two-link leg IK and torso counterrotation; no dynamics'
    profile = solve(tomllib.loads((ROOT/'refine_config.toml').read_text())['terrain'])
    rail_config = tomllib.loads((ROOT/'refine_config.toml').read_text())['rail']
    rail_grade = rail_config['longitudinal_grade']
    rail_top = rail_config['center_height_m'] + rail_config['diameter_m']/2*math.sqrt(1+rail_grade**2)
    tree = BVHTree.FromObject(scene.objects['Snow_terrain'], bpy.context.evaluated_depsgraph_get())
    scene.render.fps = m['fps']
    scene.frame_start = 1
    scene.frame_end = 1+round(m['duration_s']*m['fps'])
    rows = []
    # Fit both skis to the actual terrain and rail tangent before solving flights.
    for f in range(scene.frame_start, scene.frame_end+1):
        scene.frame_set(f)
        s = sample((f-1)/m['fps'], c)
        articulated_pose(rig, s)
        trans.location = (s['x'], s['y'], 0)
        slope = grade(s['y'], profile)*(1-s['pitch_mix'])+rail_grade*s['pitch_mix']
        orient.rotation_quaternion = Euler((math.atan(slope), 0, 0)).to_quaternion() @ Quaternion((0, 0, 1), s['yaw'])
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ground_fit, rail_fit = [], []
        for n in ['ATH_Ski_L', 'ATH_Ski_R']:
            for p in points(scene.objects[n], deps):
                hit, *_ = tree.ray_cast(Vector((p.x, p.y, 30)), Vector((0, 0, -1)), 100)
                assert hit is not None
                ground_fit.append(hit.z-p.z)
                rail_fit.append(rail_top+rail_grade*p.y-p.z)
        rows.append(dict(frame=f, **s,
                         ground_z=max(ground_fit)+m['clearance_m'],
                         rail_z=max(rail_fit)+m['clearance_m']))
    def at(t):
        return rows[round(t*m['fps'])]
    a, b, d, e = [r[k] for k in ('entry_takeoff_s', 'rail_contact_s', 'rail_release_s', 'snow_contact_s')]
    col = bpy.data.collections['ANIM_Controls']
    left_marker(scene, col, tree, c)
    cam = camera('ANIM_Review', (6, 10, 5), (0, 0, 1), c['render']['camera_lens_mm'], col)
    scene.camera = cam
    previous_orientation = None
    for row in rows:
        f, t = row['frame'], row['t']
        scene.frame_set(f)
        articulated_pose(rig, row)
        slope = grade(row['y'], profile)*(1-row['pitch_mix'])+rail_grade*row['pitch_mix']
        q = orientation(row, slope, c)
        if previous_orientation is not None and q.dot(previous_orientation) < 0:
            q.negate()
        previous_orientation = q.copy()
        orient.rotation_quaternion = q
        if t <= a or t >= e:
            z = row['ground_z']
        elif t < b:
            z = ballistic(t, a, b, at(a)['ground_z'], at(b)['rail_z'], r['gravity_m_s2'])
        elif t <= d:
            z = row['rail_z']+row.get('rail_lift', 0.)
        else:
            z = ballistic(t, d, e, at(d)['rail_z'], at(e)['ground_z'], r['gravity_m_s2'])
        trans.location = (row['x'], row['y'], z)
        row['root_z'] = z
        trans.keyframe_insert('location', frame=f)
        orient.keyframe_insert('rotation_quaternion', frame=f)
        for bone in rig.pose.bones:
            loc, quat, scale = bone.matrix_basis.decompose()
            bone.rotation_mode = 'QUATERNION'
            bone.location, bone.rotation_quaternion, bone.scale = loc, quat, scale
            for channel in ['location', 'rotation_quaternion', 'scale']:
                bone.keyframe_insert(channel, frame=f)
        set_camera(scene, trans, row['ground_z'], c)
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
    linear_keys()
    with (out/'timeline.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    for key in ['width', 'height']:
        setattr(scene.render, 'resolution_'+('x' if key == 'width' else 'y'), c['render'][key])
    scene.render.resolution_percentage = 100
    scene.cycles.samples = c['render']['samples']
    scene.cycles.seed = c['render']['seed']
    scene.render.threads = c['render']['threads']
    scene['animation_interpretation'] = m['interpretation']
    scene['animation_config'] = json.dumps(c)
    scene['animation_origin'] = 'Ski support origin; not measured center of mass'
    for label, t in [('approach', 0), ('entry_takeoff', a), ('rail_contact', b),
                     ('rail_release', d), ('snow_contact', e),
                     ('compression_peak', r['compression_peak_s']), ('runout', r['recovered_s'])]:
        scene.timeline_markers.new(label, frame=1+round(t*m['fps']))
    if 'switch_start_s' in r:
        for label, t in [('knees_left', r['switch_start_s']-.1),
                         ('reorientation', (r['switch_start_s']+r['switch_end_s'])/2),
                         ('knees_right', r['switch_end_s']+.1)]:
            scene.timeline_markers.new(label, frame=1+round(t*m['fps']))
    if 'air_trick' in c:
        k = c['air_trick']
        spin_start = d+k['start_delay_s']; spin_end = e-k['landing_prepare_s']
        for i in range(1, 2*k['rotations'], 2):
            target = i/(2*k['rotations'])
            low, high = 0., 1.
            for _ in range(40):
                mid = (low+high)/2
                if smooth(mid) < target: low = mid
                else: high = mid
            t = spin_start+(spin_end-spin_start)*(low+high)/2
            scene.timeline_markers.new('inversion_'+str((i+1)//2), frame=1+round(t*m['fps']))
    scene.frame_set(1+round(m['freeze_time_s']*m['fps']))
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_location = (0, 0, 1)
                area.spaces.active.region_3d.view_distance = 13
    assert not (out/'snowpark-motion.blend').exists()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'snowpark-motion.blend'))
    write(out/'build-report.json', dict(status='BUILT', frames=len(rows),
          blender=bpy.app.version_string, blend_sha256=sha(out/'snowpark-motion.blend'),
          reference_sha256=c['source']['reference_sha256'],
          environment_unchanged=environment() == json.loads((out/'environment-before.json').read_text()),
          interpretation=m['interpretation']))


def obstacle_trees(scene):
    result = []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.collections['REF_Environment'].all_objects:
        if o.type != 'MESH' or not o.name.startswith(('Rail_', 'Support_', 'Saddle_', 'Footing_')):
            continue
        ev = o.evaluated_get(deps); mesh = ev.to_mesh()
        vv = [ev.matrix_world@v.co for v in mesh.vertices]
        bounds = [(min(v[k] for v in vv), max(v[k] for v in vv)) for k in range(3)]
        result.append((o.name, BVHTree.FromPolygons(vv, [list(p.vertices) for p in mesh.polygons]), bounds))
        ev.to_mesh_clear()
    return result


def verify(out, c):
    scene = bpy.context.scene; m = c['motion']; r = c['rail_slide']
    terrain = BVHTree.FromObject(scene.objects['Snow_terrain'], bpy.context.evaluated_depsgraph_get())
    obstacles = obstacle_trees(scene)
    rail = next(tree for name, tree, _ in obstacles if name == 'Rail_tube')
    names = [o.name for o in bpy.data.collections['P2_Athlete'].all_objects if o.type == 'MESH' and not o.hide_render]
    collisions = []; contacts = []; snow_contacts = []; ground_min = math.inf; max_step = 0.; stretch = 0.
    ski_alignment = True; inversion_intervals = []; active_inversion = False
    headings = {n: [] for n in ['ATH_Ski_L', 'ATH_Ski_R']}
    knee_sides = dict(left=[], right=[])
    marker_offsets = []; rail_lifts = []
    exit_heights = []
    finite = True; upright_min = 1.; prior = None; all_in_frame = True
    for half in range(2*(scene.frame_end-1)+1):
        f = 1+half*.5; t = (f-1)/m['fps']
        switching = 'switch_start_s' in r and r['switch_start_s'] < t < r['switch_end_s']
        scene.frame_set(int(f), subframe=f-int(f)); deps = bpy.context.evaluated_depsgraph_get()
        positions = {}
        for name in names:
            pts = points(scene.objects[name], deps); positions[name] = pts
            finite &= all(math.isfinite(x) for p in pts for x in p)
            bounds = [(min(p[k] for p in pts), max(p[k] for p in pts)) for k in range(3)]
            candidates = [(label, tree) for label, tree, bb in obstacles
                          if all(bounds[k][0] <= bb[k][1] and bounds[k][1] >= bb[k][0] for k in range(3))]
            if candidates:
                ev = scene.objects[name].evaluated_get(deps); mesh = ev.to_mesh()
                body = BVHTree.FromPolygons(pts, [list(p.vertices) for p in mesh.polygons]); ev.to_mesh_clear()
                for label, tree in candidates:
                    if body.overlap(tree):
                        collisions.append(dict(frame=f, athlete=name, obstacle=label))
            # Every vertex against the actual terrain; no assumed flat floor.
            ski_gaps = []
            for p in pts:
                hit, *_ = terrain.ray_cast(Vector((p.x, p.y, 30)), Vector((0, 0, -1)), 100)
                assert hit is not None
                ground_min = min(ground_min, p.z-hit.z)
                if name in ['ATH_Ski_L', 'ATH_Ski_R']:
                    ski_gaps.append(p.z-hit.z)
            if name in ['ATH_Ski_L', 'ATH_Ski_R']:
                direction = (pts[64]+pts[65]-pts[0]-pts[1])*.5
                # Use two flat waist sections: unequal raised tips would bias
                # the projected heading. Station 4 is forward of station 12.
                waist = (pts[48]+pts[49]-pts[16]-pts[17])*.5
                headings[name].append((t, math.atan2(-waist.x, waist.y)))
                if r['rail_contact_s'] <= t <= r['rail_release_s'] and not switching:
                    ski_alignment &= abs(direction.y)/math.hypot(direction.x, direction.y) < .02
                if t <= r['entry_takeoff_s'] or t >= r['snow_contact_s']:
                    snow_contacts.append(min(ski_gaps))
                    if 'celebration' not in c or t <= c['celebration']['start_s']:
                        ski_alignment &= abs(direction.x)/math.hypot(direction.x, direction.y) < .02
            if name in ['ATH_Ski_L', 'ATH_Ski_R'] and r['rail_contact_s'] <= t <= r['rail_release_s'] and not switching:
                gaps = []
                for i in range(0, len(pts)-3, 4):
                    p = (pts[i]+pts[i+1])*.5
                    hit, *_ = rail.ray_cast(Vector((p.x, p.y, 30)), Vector((0, 0, -1)), 100)
                    if hit is not None:
                        gaps.append(p.z-hit.z)
                contacts.append(dict(frame=f, ski=name, min_gap_m=min(gaps) if gaps else None))
            # Bounds corners suffice for screen containment in front of the camera.
            for x in bounds[0]:
                for y in bounds[1]:
                    for z in bounds[2]:
                        uv = world_to_camera_view(scene, scene.camera, Vector((x, y, z)))
                        all_in_frame &= .025 <= uv.x <= .975 and .025 <= uv.y <= .975 and uv.z > 0
        if prior:
            max_step = max(max_step, max((p-q).length for n in names for p, q in zip(positions[n], prior[n])))
        prior = positions
        rig = scene.objects['Athlete_Rig']
        if 'switch_start_s' in r and r['rail_contact_s'] <= t <= r['rail_release_s']:
            root = scene.objects['ANIM_Translation'].location
            hit, *_ = rail.ray_cast(Vector((root.x, root.y, 30)), Vector((0, 0, -1)), 100)
            assert hit is not None
            rail_lifts.append(root.z-hit.z-m['clearance_m'])
        for side in ['L', 'R']:
            for stem in ['thigh', 'shin']:
                bone = rig.pose.bones[stem+'.'+side]
                stretch = max(stretch, abs((bone.tail-bone.head).length-bone.bone.length))
            if 'switch_start_s' in r:
                stage = ('left' if r['rail_contact_s'] <= t <= r['switch_start_s'] else
                         'right' if r['switch_end_s'] <= t <= r['rail_release_s'] else None)
                if stage:
                    thigh = rig.pose.bones['thigh.'+side]; shin = rig.pose.bones['shin.'+side]
                    knee = rig.matrix_world @ thigh.tail
                    straight = rig.matrix_world @ ((thigh.head+shin.tail)*.5)
                    offset = world_to_camera_view(scene, scene.camera, knee).x-world_to_camera_view(scene, scene.camera, straight).x
                    knee_sides[stage].append(offset)
                    if side == 'L' and 'ANIM_LeftMarker' in scene.objects:
                        marker = scene.objects['ANIM_LeftMarker']
                        center = marker.matrix_world @ (sum((Vector(v) for v in marker.bound_box), Vector())/8)
                        athlete = scene.objects['ANIM_Translation'].location+Vector((0, 0, .8))
                        marker_offsets.append(world_to_camera_view(scene, scene.camera, center).x-world_to_camera_view(scene, scene.camera, athlete).x)
        up = scene.objects['ANIM_Orientation'].rotation_quaternion @ Vector((0, 0, 1))
        if r['rail_release_s'] <= t <= r['snow_contact_s']:
            exit_heights.append(scene.objects['ANIM_Translation'].location.z)
        airborne_trick = 'air_trick' in c and r['rail_release_s'] < t < r['snow_contact_s']
        if not airborne_trick:
            upright_min = min(upright_min, up.z)
        if airborne_trick and up.z < -.15:
            if not active_inversion:
                inversion_intervals.append(dict(start_s=t, end_s=t, min_up_z=up.z))
            else:
                inversion_intervals[-1]['end_s'] = t
                inversion_intervals[-1]['min_up_z'] = min(inversion_intervals[-1]['min_up_z'], up.z)
            active_inversion = True
        else:
            active_inversion = False
    checks = dict(
        environment_geometry_and_hierarchy_preserved=environment() == json.loads((out/'environment-before.json').read_text()),
        finite_evaluated_geometry=bool(finite),
        no_visible_mesh_ground_penetration=ground_min >= -.001,
        no_rail_or_support_intersections=not collisions,
        both_skis_contact_rail_in_supported_slide_poses=bool(contacts) and all(v['min_gap_m'] is not None and .003 <= v['min_gap_m'] <= .025 for v in contacts),
        both_skis_contact_snow_before_and_after=bool(snow_contacts) and all(.003 <= v <= .025 for v in snow_contacts),
        skis_transverse_on_rail_and_forward_on_snow=bool(ski_alignment),
        leg_lengths_preserved=stretch < 1e-5,
        no_large_mesh_position_jump=max_step < .20,
        complete_athlete_visible_every_sample=bool(all_in_frame),
    )
    checks['upright_on_snow_and_rail' if 'air_trick' in c else 'no_backflip'] = upright_min > .97
    if 'air_trick' in c:
        checks['two_distinct_inversions_in_exit_flight'] = (len(inversion_intervals) == 2 and
            all(v['end_s']-v['start_s'] > .08 and v['min_up_z'] < -.4 for v in inversion_intervals))
        # Inspect the baked rotation path itself, independently of profile samples.
        accumulated = 0.; previous = None
        for f in range(1+round(r['rail_release_s']*m['fps']), 2+round(r['snow_contact_s']*m['fps'])):
            scene.frame_set(f)
            q = scene.objects['ANIM_Orientation'].rotation_quaternion.copy()
            if previous is not None:
                accumulated += 2*math.acos(min(1., abs(q.dot(previous))))
            previous = q
        # Net path length differs from the off-axis 720 degrees because the
        # skier also realigns the original transverse heading by 90 degrees.
        checks['baked_aerial_rotation_between_650_and_810_degrees'] = 650 <= math.degrees(accumulated) <= 810
        details_rotation = dict(inversion_intervals=inversion_intervals, accumulated_rotation_degrees=math.degrees(accumulated))
    details = dict(min_ground_gap_m=ground_min, collisions=collisions[:30], rail_contacts=contacts,
                   snow_contact_gap_range_m=[min(snow_contacts), max(snow_contacts)],
                   max_half_frame_mesh_step_m=max_step, max_leg_length_error_m=stretch,
                   min_body_up_z=upright_min)
    if 'air_trick' in c:
        details.update(details_rotation)
    if r.get('style') == 'boardslide':
        yaw_paths = {}
        for name, path in headings.items():
            if 'celebration' in c:
                path = [(t, yaw) for t, yaw in path if t <= c['celebration']['start_s']]
            increments = [math.atan2(math.sin(b-a), math.cos(b-a)) for (_, a), (_, b) in zip(path, path[1:])]
            yaw_paths[name] = dict(
                min_degrees=math.degrees(min(a for _, a in path)),
                max_degrees=math.degrees(max(a for _, a in path)),
                positive_degrees=math.degrees(sum(max(0, v) for v in increments)),
                negative_degrees=math.degrees(sum(min(0, v) for v in increments)),
                landing_degrees=math.degrees(next(a for t, a in path if t >= r['snow_contact_s'])))
        if 'switch_start_s' in r:
            checks['opposite_transverse_poses_with_180_reorientation'] = all(
                abs(v['min_degrees']+90) < .1 and abs(v['max_degrees']-90) < .1 and
                abs(v['positive_degrees']-180) < .3 and abs(v['negative_degrees']+180) < .3
                for v in yaw_paths.values())
            checks['knees_screen_left_on_entry_screen_right_before_exit'] = (
                bool(knee_sides['left']) and bool(knee_sides['right']) and
                max(knee_sides['left']) < -.003 and min(knee_sides['right']) > .003)
            checks['reorientation_stays_within_five_cm_of_rail_support_plane'] = max(rail_lifts) <= .05
            if 'left_marker_xy_m' in c['render']:
                checks['orange_marker_screen_left_in_both_slide_poses'] = bool(marker_offsets) and max(marker_offsets) < -.01
            details['knee_screen_offset_ranges'] = {k: [min(v), max(v)] for k, v in knee_sides.items()}
            details['max_reorientation_lift_m'] = max(rail_lifts)
        else:
            checks['spin_on_plus_90_spin_off_minus_90'] = all(
                -.1 <= v['min_degrees'] <= .1 and 89.9 <= v['max_degrees'] <= 90.1 and
                abs(v['positive_degrees']-90) < .2 and abs(v['negative_degrees']+90) < .2
                for v in yaw_paths.values())
        checks['landing_forward_in_direction_of_travel'] = all(abs(v['landing_degrees']) < .1 for v in yaw_paths.values())
        rise = max(exit_heights)-exit_heights[0]
        flight = r['snow_contact_s']-r['rail_release_s']
        checks['exit_rise_at_most_three_centimeters'] = rise <= r['max_exit_rise_m']+1e-5
        checks['brief_exit_drop'] = flight <= r['max_exit_flight_s']
        details.update(yaw_paths=yaw_paths, exit_rise_m=rise, exit_flight_s=flight)
    write(out/'verification.json', dict(status='PASS' if all(checks.values()) else 'FAIL',
          checks=checks, details=details, sampled_times=2*(scene.frame_end-1)+1,
          blend_sha256=sha(bpy.data.filepath),
          limits='Geometric checks at half frames after reopening; no contact forces, measured biomechanics or continuous collision proof.'))
    assert all(checks.values()), checks


def preview_setup(scene):
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.studiolight_rotate_z = .5
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.65, .76, .86)
    scene.view_settings.view_transform = 'Standard'


def preview(out, c):
    scene = bpy.context.scene; m = c['motion']; stride = c['render']['preview_stride']
    preview_setup(scene)
    folder = out/'preview'; folder.mkdir(exist_ok=False)
    records = []
    for f in range(scene.frame_start, scene.frame_end+1, stride):
        scene.frame_set(f)
        scene.render.filepath = str(folder/f'{f:04d}.png')
        bpy.ops.render.render(write_still=True)
        records.append(dict(frame=f, file=str((folder/f'{f:04d}.png').relative_to(out))))
    write(out/'preview.json', dict(engine='BLENDER_WORKBENCH', diagnostic_only=True,
          frame_stride=stride, fps=m['fps']/stride, width=scene.render.resolution_x,
          height=scene.render.resolution_y, frames=records, complete_sequence=True))


def render_frames(out, c):
    scene = bpy.context.scene; m = c['motion']; r = c['rail_slide']
    records = []
    for label, t in [('approach', .4), ('entry', 1.1), ('slide', 1.9),
                     ('release', r['rail_release_s']), ('landing', r['compression_peak_s']), ('runout', 4.6)]:
        scene.frame_set(1+round(t*m['fps']))
        assert not (out/(label+'.png')).exists()
        records.append(render(scene, out/(label+'.png')))
        write(out/'renders.json', records)
