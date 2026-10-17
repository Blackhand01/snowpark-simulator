"""Retime the approved saved scene without rebuilding its poses or geometry."""
import csv
import json
import math
import tomllib

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

from animate_scene import environment, points
from p2_support import ROOT, render, sha, write
from rail_slide_scene import articulated_pose, linear_keys, preview_setup, verify as verify_slide
from reference_clock import approved_time, validate
from motion_profile import smooth
from refine_profile import grade, solve

OBJECTS = ['ANIM_Translation', 'ANIM_Orientation', 'Athlete_Rig', 'ANIM_Review']


def timing_for(out):
    return json.loads((out/'reference-timing.json').read_text())


def frame_at(scene, t, fps):
    frame = 1+t*fps
    scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
    bpy.context.view_layer.update()


def signature(scene):
    return dict(objects={name: [list(row) for row in scene.objects[name].matrix_world] for name in OBJECTS},
                bones={b.name: [list(row) for row in b.matrix] for b in scene.objects['Athlete_Rig'].pose.bones},
                camera_lens_mm=scene.camera.data.lens)


def celebrate(scene, t, c, timing, terrain, profile, camera_anchor):
    k = c.get('celebration')
    if not k or t <= k['start_s']:
        return
    turn = smooth((t-k['start_s'])/(k['turn_end_s']-k['start_s']))
    raised = smooth((t-k['arms_start_s'])/(k['arms_up_s']-k['arms_start_s']))
    rig = scene.objects['Athlete_Rig']; trans = scene.objects['ANIM_Translation']
    reference_end = timing['reference_duration_ticks']/timing['time_base_den']
    if t > reference_end:
        trans.location.y = c['motion']['end_y_m']-k['runout_speed_m_s']*(t-reference_end)
    camera_mix = smooth((t-k['start_s'])/k['camera_settle_s'])
    camera_position = camera_anchor.lerp(Vector(k['camera_position_m']), camera_mix)
    camera_delta = camera_position-trans.location
    camera_yaw = math.atan2(-camera_delta.x, camera_delta.y)
    state = dict(crouch=.09, torso_pitch=.12, torso_yaw=camera_yaw*turn,
                 arm_spread=.10, arm_swing=.05, ski_pitch=0., accessory_pitch=-.85)
    articulated_pose(rig, state)
    head = rig.pose.bones['head']; head.rotation_mode = 'XYZ'; head.rotation_euler.x = -.12*turn
    bpy.context.view_layer.update()
    torso = Quaternion((0, 0, 1), state['torso_yaw']) @ Quaternion((1, 0, 0), state['torso_pitch'])
    for side, sign in [('L', 1), ('R', -1)]:
        for stem, target in [('upper_arm', (sign*.15, -.02, .30)),
                             ('forearm', (sign*.06, -.015, .28)),
                             ('hand', (sign*.025, -.01, .10))]:
            bone = rig.pose.bones[stem+'.'+side]
            rest = bone.bone
            target_q = (rest.tail_local-rest.head_local).rotation_difference(torso @ Vector(target).normalized()) @ rest.matrix_local.to_quaternion()
            q = bone.matrix.to_quaternion().slerp(target_q, raised)
            bone.matrix = Matrix.LocRotScale(bone.head.copy(), q, Vector((1, 1, 1)))
            bpy.context.view_layer.update()
    orient = scene.objects['ANIM_Orientation']
    orient.rotation_quaternion = Euler((math.atan(grade(trans.location.y, profile)), 0, 0)).to_quaternion() @ Quaternion((0, 0, 1), math.radians(k['target_yaw_degrees'])*turn)
    trans.location.z = 0.
    bpy.context.view_layer.update(); gaps = []
    for name in ['ATH_Ski_L', 'ATH_Ski_R']:
        for point in points(scene.objects[name], bpy.context.evaluated_depsgraph_get()):
            hit, *_ = terrain.ray_cast(Vector((point.x, point.y, 30)), Vector((0, 0, -1)), 100)
            assert hit is not None
            gaps.append(point.z-hit.z)
    trans.location.z = c['motion']['clearance_m']-min(gaps)
    cam = scene.objects['ANIM_Review']
    center = trans.location+Vector((0, 0, .8+.30*raised))
    cam.location = camera_position
    cam.rotation_euler = (center-cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = c['render']['camera_lens_mm']+(k['camera_lens_mm']-c['render']['camera_lens_mm'])*camera_mix
    bpy.context.view_layer.update()


def build(out, c):
    timing = timing_for(out); validate(timing, c)
    assert sha(ROOT/c['source']['blend']) == c['source']['sha256']
    assert sha(ROOT/c['source']['reference_video']) == c['source']['reference_sha256']
    scene = bpy.context.scene; old_fps = scene.render.fps/scene.render.fps_base
    old_end = (scene.frame_end-1)/old_fps
    assert abs(old_end-timing['events'][-1]['approved_time_s']) < 1e-6
    write(out/'environment-before.json', environment())
    fps = c['motion']['fps']; duration = c['motion']['duration_s']; den = timing['time_base_den']
    # Original PTS and event instants are explicit keys, even between bake frames.
    times = {i/fps for i in range(math.floor(duration*fps)+1)}
    times.update(p/den for p in timing['frame_pts'])
    times.update(e['pts']/den for e in timing['events'])
    times.add(duration)
    reference_ticks = set(timing['frame_pts']); samples = []; reference = {}
    terrain = BVHTree.FromObject(scene.objects['Snow_terrain'], bpy.context.evaluated_depsgraph_get())
    profile = solve(tomllib.loads((ROOT/'refine_config.toml').read_text())['terrain'])
    camera_anchor = scene.camera.location.copy()
    if 'celebration' in c:
        frame_at(scene, approved_time(c['celebration']['start_s'], timing), old_fps)
        camera_anchor = scene.camera.location.copy()
    for t in sorted(times):
        source_t = approved_time(t, timing)
        frame_at(scene, source_t, old_fps)
        celebrate(scene, t, c, timing, terrain, profile, camera_anchor)
        row = dict(t=t, approved_time_s=source_t,
                   objects={n: [list(r) for r in scene.objects[n].matrix_basis] for n in OBJECTS},
                   bones={b.name: [list(r) for r in b.matrix_basis] for b in scene.objects['Athlete_Rig'].pose.bones},
                   camera_lens_mm=scene.camera.data.lens)
        samples.append(row)
        ticks = round(t*den)
        if abs(t*den-ticks) < 1e-6 and ticks in reference_ticks:
            reference[str(ticks)] = signature(scene)
    # Capture first, then replace actions; no source key is changed while sampling.
    for name in OBJECTS:
        scene.objects[name].animation_data_clear()
    scene.camera.data.animation_data_clear()
    scene.render.fps = fps; scene.render.fps_base = 1
    scene.frame_start = 1; scene.frame_end = 1+math.ceil(duration*fps)
    rig = scene.objects['Athlete_Rig']
    previous_quaternions = {}
    def continuous(key, quat):
        # q and -q encode the same orientation. Component interpolation needs
        # consistent signs, especially as the camera crosses its Euler wrap.
        if key in previous_quaternions and quat.dot(previous_quaternions[key]) < 0:
            quat.negate()
        previous_quaternions[key] = quat.copy()
        return quat
    for row in samples:
        f = 1+row['t']*fps
        for name, matrix in row['objects'].items():
            obj = scene.objects[name]; loc, quat, scale = Matrix(matrix).decompose()
            quat = continuous('object/'+name, quat)
            obj.location = loc; obj.rotation_mode = 'QUATERNION'; obj.rotation_quaternion = quat; obj.scale = scale
            for channel in ['location', 'rotation_quaternion', 'scale']:
                obj.keyframe_insert(channel, frame=f)
        for name, matrix in row['bones'].items():
            b = rig.pose.bones[name]; loc, quat, scale = Matrix(matrix).decompose()
            quat = continuous('bone/'+name, quat)
            b.location = loc; b.rotation_mode = 'QUATERNION'; b.rotation_quaternion = quat; b.scale = scale
            for channel in ['location', 'rotation_quaternion', 'scale']:
                b.keyframe_insert(channel, frame=f)
        scene.camera.data.lens = row['camera_lens_mm']
        scene.camera.data.keyframe_insert('lens', frame=f)
    linear_keys()
    scene.timeline_markers.clear()
    for e in timing['events']:
        scene.timeline_markers.new(e['name'], frame=1+round(e['pts']/den*fps))
    scene['animation_config'] = json.dumps(c)
    scene['reference_timing'] = json.dumps(timing)
    scene['animation_interpretation'] = c['motion']['interpretation']
    frame_at(scene, c['motion']['freeze_time_s'], fps)
    assert not (out/'snowpark-motion.blend').exists()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'snowpark-motion.blend'))
    with (out/'timeline.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['t', 'approved_time_s'])
        writer.writeheader(); writer.writerows({k: row[k] for k in writer.fieldnames} for row in samples)
    write(out/'reference-pose-samples.json', reference)
    write(out/'build-report.json', dict(status='BUILT', bake_samples=len(samples),
          reference_frames=len(timing['frame_pts']), duration_s=duration,
          source_blend_sha256=c['source']['sha256'], blend_sha256=sha(out/'snowpark-motion.blend'),
          environment_unchanged=environment() == json.loads((out/'environment-before.json').read_text()),
          interpretation=c['motion']['interpretation']))


def verify(out, c):
    verify_slide(out, c)
    scene = bpy.context.scene; timing = timing_for(out); den = timing['time_base_den']
    expected = json.loads((out/'reference-pose-samples.json').read_text()); error = 0.
    for ticks, target in expected.items():
        frame_at(scene, int(ticks)/den, c['motion']['fps'])
        actual = signature(scene)
        error = max(error, max(abs(actual[group][name][i][j]-matrix[i][j])
                    for group in ['objects', 'bones'] for name, matrix in target[group].items()
                    for i in range(4) for j in range(4)))
        error = max(error, abs(actual['camera_lens_mm']-target['camera_lens_mm']))
    event_poses = []
    for event in timing['events']:
        if 'expected_heading_deg' not in event: continue
        frame_at(scene, event['pts']/den, c['motion']['fps'])
        for name in ['ATH_Ski_L', 'ATH_Ski_R']:
            p = points(scene.objects[name], bpy.context.evaluated_depsgraph_get())
            axis = (p[48]+p[49]-p[16]-p[17])*.5
            yaw = math.degrees(math.atan2(-axis.x, axis.y))
            event_poses.append(dict(event=event['name'], t=event['pts']/den, ski=name,
                                    heading_deg=yaw, target_deg=event['expected_heading_deg']))
    result = json.loads((out/'verification.json').read_text())
    result['checks']['retimed_and_extended_poses_survive_reopening'] = error < 2e-5
    result['checks']['heading_targets_match_at_annotated_event_timestamps'] = all(abs(v['heading_deg']-v['target_deg']) < .1 for v in event_poses)
    result['details'].update(max_retimed_matrix_error=error, event_poses=event_poses,
                             reference_timing_uncertainty=timing['uncertainty'])
    if 'celebration' in c:
        frame_at(scene, c['celebration']['arms_up_s'], c['motion']['fps'])
        rig = scene.objects['Athlete_Rig']
        head = rig.matrix_world @ rig.pose.bones['head'].tail
        hands = [rig.matrix_world @ rig.pose.bones['hand.'+side].tail for side in ['L', 'R']]
        chest = rig.pose.bones['chest']
        local_front = chest.bone.matrix_local.to_quaternion().conjugated() @ Vector((0, -1, 0))
        front = rig.matrix_world.to_quaternion() @ (chest.matrix.to_quaternion() @ local_front)
        to_camera = (scene.camera.location-(rig.matrix_world @ chest.head)).normalized()
        result['checks']['celebration_both_hands_above_head'] = all(hand.z > head.z+.025 for hand in hands)
        result['checks']['celebration_faces_rail_and_camera'] = front.dot(to_camera) > .8 and front.y > .8
        before = scene.objects['ANIM_Translation'].location.y
        frame_at(scene, c['motion']['duration_s'], c['motion']['fps'])
        result['checks']['celebration_continues_sliding_downhill'] = scene.objects['ANIM_Translation'].location.y < before-.5
        result['details']['celebration'] = dict(hand_height_above_head_m=[hand.z-head.z for hand in hands],
            facing_camera_dot=front.dot(to_camera), facing_uphill_y=front.y)
    result['status'] = 'PASS' if all(result['checks'].values()) else 'FAIL'
    write(out/'verification.json', result)
    assert result['status'] == 'PASS', result['checks']


def preview(out, c):
    scene = bpy.context.scene; timing = timing_for(out); den = timing['time_base_den']
    preview_setup(scene)
    folder = out/'preview'; folder.mkdir(exist_ok=False); records = []
    for i, pts in enumerate(timing['frame_pts']):
        frame_at(scene, pts/den, c['motion']['fps'])
        path = folder/f'{i:04d}.png'; scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records.append(dict(frame=i, pts=pts, file=str(path.relative_to(out))))
    write(out/'preview.json', dict(engine='BLENDER_WORKBENCH', diagnostic_only=True,
          complete_sequence=True, time_base_den=den, pts_ticks=timing['frame_pts'],
          duration_ticks=timing['duration_ticks'], fps=30, frames=records))


def render_frames(out, c):
    scene = bpy.context.scene; timing = timing_for(out); records = []
    for e in timing['events']:
        if e['name'] not in ['rail_contact_s', 'switch_end_s', 'rail_release_s', 'snow_contact_s']: continue
        frame_at(scene, e['pts']/timing['time_base_den'], c['motion']['fps'])
        records.append(render(scene, out/(e['name']+'.png')))
        write(out/'renders.json', records)
