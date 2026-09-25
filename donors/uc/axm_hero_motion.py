"""Reusable mechanical/soft-cloth skin, authored action clips and roundtrip view.

Animation is baked to ordinary skeleton transforms. No live Blender constraints,
simulation, particle hair or driver expressions are needed by the exported GLB.
"""
import hashlib
import json
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Quaternion
import axm_blender_forge as geo
from axm_oops_character import reset_pose, aim_limb, orient_world, solve_leg, triangulate_game_mesh

TAU=math.tau
CLIPS=[
    ('Idle_Relaxed',3.0,True),('Idle_Ready',2.0,True),('Crouch_Idle',2.0,True),
    ('Walk_Forward',1.2,True),('Walk_Backward',1.4,True),('Run_Forward',.8,True),
    ('Strafe_Left',1.2,True),('Strafe_Right',1.2,True),('Crouch_Walk',1.6,True),
    ('Jump',1.2,False),('Land',.6,False),('Wrench_Attack',1.1,False),
    ('Repair_Loop',1.2,True),('Interact',1.4,False),('Wave',2.2,False),
    ('Celebrate',2.4,False),('Hit_React',.7,False),('Knockdown',1.2,False),
    ('Get_Up',1.6,False),('Hero_Pose',2.0,True),
]


def clean_triangles(mesh):
    """Remove zero-area cap/pole triangles without welding distinct skin parts."""
    triangulate_game_mesh(mesh)
    bm=bmesh.new();bm.from_mesh(mesh.data)
    # Leave margin for float32 GLB position quantization: faces that are barely
    # nonzero in the authoring mesh can collapse when exported and re-imported.
    if any(len(face.verts)!=3 for face in bm.faces):
        bm.free();raise ValueError('Triangle cleanup requires a triangulated skin')
    # Cross local edges instead of the polygon area accumulator, whose
    # cancellation error kept five collinear extruded-letter triangles alive.
    bad=[face for face in bm.faces
         if (face.verts[1].co-face.verts[0].co).cross(face.verts[2].co-face.verts[0].co).length<2e-10]
    if bad:bmesh.ops.delete(bm,geom=bad,context='FACES_ONLY')
    isolated=[v for v in bm.verts if not v.link_faces]
    if isolated:bmesh.ops.delete(bm,geom=isolated,context='VERTS')
    bm.to_mesh(mesh.data);bm.free();mesh.data.update()
    print('REMOVED_DEGENERATE_TRIANGLES',len(bad),flush=True)


def rig(hero):
    data=bpy.data.armatures.new('AXM_Hero_Skeleton');arm=bpy.data.objects.new('AXM_Hero_Rig',data)
    bpy.context.collection.objects.link(arm);geo.select_only([arm]);bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name,(h,t,p) in hero.bones.items():
        b=data.edit_bones.new(name);b.head=h;b.tail=t
        if p:b.parent=data.edit_bones[p]
    bpy.ops.object.mode_set(mode='OBJECT');arm.show_in_front=True;data.display_type='STICK'
    originals=bpy.data.collections.new('SOURCE_editable_parts');bpy.context.scene.collection.children.link(originals)
    # Freeze all modifiers together. Re-evaluating the entire scene for each
    # small rivet made dense authoring unnecessarily expensive.
    geo.select_only(hero.parts);bpy.context.view_layer.objects.active=hero.parts[0]
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    copies=[]
    for i,ob in enumerate(hero.parts):
        if not ob.data.uv_layers:
            uv=ob.data.uv_layers.new(name='UVMap')
            for loop in ob.data.loops:
                v=ob.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x,v.z)
        if ob.get('axm_cape'):
            groups=[ob.vertex_groups.new(name='Cape.0'+str(j)) for j in [1,2,3]]
            for v in ob.data.vertices:
                t=max(0,min(2,(1.41-v.co.z)/.30))
                a=min(1,int(t));f=t-a
                groups[a].add([v.index],1-f,'REPLACE')
                if f>0:groups[a+1].add([v.index],f,'REPLACE')
        elif ob.get('axm_mouth'):
            upper=ob.vertex_groups.new(name='Head');lower=ob.vertex_groups.new(name='Jaw')
            for v in ob.data.vertices:
                f=max(0,min(1,(1.56-v.co.z)/.18))
                if f<1:upper.add([v.index],1-f,'REPLACE')
                if f>0:lower.add([v.index],f,'REPLACE')
        else:
            vg=ob.vertex_groups.new(name=ob['axm_bone']);vg.add(list(range(len(ob.data.vertices))),1,'REPLACE')
        cp=ob.copy();cp.data=ob.data.copy();bpy.context.collection.objects.link(cp);copies.append(cp)
        for col in list(ob.users_collection):col.objects.unlink(ob)
        originals.objects.link(ob)
        if i%150==0:print('RIG_PARTS',i,len(hero.parts),flush=True)
    originals.hide_render=True;originals.hide_viewport=True
    geo.select_only(copies);bpy.context.view_layer.objects.active=copies[0];bpy.ops.object.join()
    mesh=bpy.context.object;mesh.name='AXM_Chaos_Hero';mesh.data.name='AXM_Chaos_Hero_Surface';mesh.parent=arm
    clean_triangles(mesh)
    skin=mesh.modifiers.new('Armour rigid / cape blended skin','ARMATURE');skin.object=arm
    arm['forward_axis']='-Y in Blender, +Z in glTF';arm['meters_per_unit']=1.0
    arm['binding']='Rigid mechanical shells; blended cape and mouth; articulated face and fingers.'
    return arm,mesh


def translate(arm,name,xyz):
    bone=arm.pose.bones[name]
    # Root/pelvis translations are expressed in armature space, not local-Y guesses.
    bone.location=bone.bone.matrix_local.to_quaternion().inverted() @ Vector(xyz)


def base_pose(arm,t=0):
    reset_pose(arm)
    b=arm.pose.bones
    # Upper/lower hemispheres tuck behind the eye when open.
    b['LidUpper'].rotation_euler.x=-1.48
    b['LidLower'].rotation_euler.x=1.48
    b['Head'].rotation_euler.z=.02*math.sin(TAU*t)
    b['Jaw'].rotation_euler.x=.02*math.sin(TAU*t)
    b['Antenna'].rotation_euler.x=.05*math.sin(TAU*t)
    b['Cape.01'].rotation_euler.x=.045*math.sin(TAU*t)
    b['Cape.02'].rotation_euler.x=.06*math.sin(TAU*t-.35)
    b['Cape.03'].rotation_euler.x=.08*math.sin(TAU*t-.7)
    b['ScarfTail'].rotation_euler.y=.055*math.sin(TAU*t+.4)
    b['Charm'].rotation_euler.x=.09*math.sin(TAU*t)
    blink=max(0,1-abs(t-.80)/.035)
    b['LidUpper'].rotation_euler.x=-1.48*(1-blink)
    b['LidLower'].rotation_euler.x=1.48*(1-blink)


def arm_pose(arm,side,upper,lower,amount=1,level_hand=True):
    aim_limb(arm,'UpperArm.'+side,upper,amount)
    aim_limb(arm,'Forearm.'+side,lower,amount)
    if level_hand:
        orient_world(arm,'Hand.'+side,arm.data.bones['Hand.'+side].matrix_local.to_quaternion())


def envelope(t):return math.sin(math.pi*max(0,min(1,t)))**2


def stance(arm,lower=.055,width=.28):
    translate(arm,'Pelvis',(0,0,-lower))
    for s,side in [(-1,'R'),(1,'L')]:solve_leg(arm,side,(s*width,0,.20))


def pose(arm,name,t):
    base_pose(arm,t);b=arm.pose.bones;p=TAU*t;e=envelope(t)
    locomotion={'Walk_Forward','Walk_Backward','Run_Forward','Strafe_Left','Strafe_Right','Crouch_Walk'}
    if name in locomotion:
        running=name=='Run_Forward';crouch=name=='Crouch_Walk';sideways=name.startswith('Strafe')
        step=.34 if running else .22 if crouch else .28
        if sideways:step=.20
        translate(arm,'Pelvis',(.018*math.sin(p),0,-(.16 if crouch else .075)+(.018 if running else .009)*(1-math.cos(p*2))))
        b['Chest'].rotation_euler.x=.14 if running else .15 if crouch else .03
        b['Chest'].rotation_euler.z=.045*math.sin(p)
        b['Head'].rotation_euler.x=-.07 if running else -.04
        for s,side in [(-1,'R'),(1,'L')]:
            cycle=(t+(0 if side=='L' else .5))%1
            if cycle<.5:
                travel=-step/2+step*cycle*2;lift=0
            else:
                u=(cycle-.5)*2;travel=step/2-step*(u*u*(3-2*u));lift=(.12 if running else .075)*math.sin(math.pi*u)**2
            if name=='Walk_Backward':travel=-travel
            x=s*.28;y=travel
            if sideways:x+=(1 if name=='Strafe_Right' else -1)*travel;y=0
            solve_leg(arm,side,(x,y,.20+lift))
            swing=math.sin(p+(0 if side=='L' else math.pi))
            arm_pose(arm,side,(s*.30,-.45*swing,-1),(s*.12,-.25-.35*swing,-1),1)
        b['Cape.01'].rotation_euler.x=-.12 if running else -.03
        b['Cape.02'].rotation_euler.x=-.13+.10*math.sin(p)
        b['Cape.03'].rotation_euler.x=.14*math.sin(p-.5)
        b['Charm'].rotation_euler.x=.22*math.sin(p)
    elif name in {'Idle_Ready','Crouch_Idle','Repair_Loop'}:
        stance(arm,.18 if name=='Crouch_Idle' else .08,width=.30)
        b['Chest'].rotation_euler.x=.12
        for s,side in [(-1,'R'),(1,'L')]:
            arm_pose(arm,side,(s*.7,-.3,-.9),(s*.08,-.9,.25 if name!='Repair_Loop' else -.25))
        if name=='Repair_Loop':
            arm_pose(arm,'R',(-.42,-.4,-.8),(-.1,-.8,-.1+.45*math.sin(p*2)))
            b['Tool'].rotation_euler.x=.18*math.sin(p*2)
            b['Head'].rotation_euler.x=.15
            b['Jaw'].rotation_euler.x=-.06
    elif name in {'Jump','Land'}:
        if name=='Jump':
            if t<.2:
                a=t/.2;stance(arm,.16*math.sin(a*math.pi/2),.29)
            elif t<.85:
                a=(t-.2)/.65;z=.44*math.sin(math.pi*a)
                translate(arm,'Root',(0,0,z));translate(arm,'Pelvis',(0,0,-.03))
                for s,side in [(-1,'R'),(1,'L')]:solve_leg(arm,side,(s*.28,.035,.23+z+.10*math.sin(math.pi*a)))
            else:stance(arm,.11*math.sin(math.pi*(1-t)/.15),.29)
            for s,side in [(-1,'R'),(1,'L')]:arm_pose(arm,side,(s*.9,-.1,-.2), (s*.3,-.7,.6),e)
            b['Cape.02'].rotation_euler.x=-.3*e
        else:
            stance(arm,.15*e,.30);b['Chest'].rotation_euler.x=.20*e
    elif name in {'Wrench_Attack','Interact'}:
        stance(arm,.075*e,.29)
        if name=='Wrench_Attack':
            # Anticipation, quick strike, recoil and a bounded return to idle.
            wind=math.sin(math.pi*min(t/.44,1)/2) if t<.44 else max(0,1-(t-.44)/.20)
            strike=envelope((t-.40)/.35)
            arm_pose(arm,'R',(-.6,.2*wind-.7*strike,-.8+.9*wind),(-.15,-.4,.9*wind-.9*strike),e)
            b['Chest'].rotation_euler.z=-.20*wind+.18*strike
            b['Tool'].rotation_euler.x=.30*wind-1.15*strike
            b['Head'].rotation_euler.x=.06*strike
        else:
            arm_pose(arm,'L',(.35,-.55,-.7),(.1,-1,.2),e)
            for i in range(4):b[f'Finger{i}.02.L'].rotation_euler.x=.8*e
    elif name in {'Wave','Celebrate','Hero_Pose'}:
        a=1 if name=='Hero_Pose' else e
        stance(arm,.02*a,.29)
        if name in {'Hero_Pose','Celebrate'}:
            arm_pose(arm,'R',(-.8,0,.6),(-.22,-.55,1),a)
            arm_pose(arm,'L',(.9,-.18,-.10),(.30,-.7,.72),a)
            b['Thumb.L'].rotation_euler.y=-.12*a
            b['Jaw'].rotation_euler.x=.10*a
            b['Head'].rotation_euler.z=-.07*a
            b['Brow.R'].rotation_euler.y=.13*a
            if name=='Celebrate':
                translate(arm,'Chest',(0,0,.013*math.sin(p*3)*e))
                b['Tool'].rotation_euler.y=.08*math.sin(p*3)*e
            else:
                translate(arm,'Pelvis',(0,0,-.07))
                solve_leg(arm,'R',(-.32,-.15,.20));solve_leg(arm,'L',(.30,.07,.20))
                b['Head'].rotation_euler.z=-.12
        else:
            arm_pose(arm,'L',(.9,0,.25),(.12,-.3,1),a)
            desired=Quaternion(Vector((0,1,0)),math.pi*a)@arm.data.bones['Hand.L'].matrix_local.to_quaternion()
            orient_world(arm,'Hand.L',desired)
            b['Hand.L'].rotation_euler.z+=.28*math.sin(p*3)*e
            for i in range(4):
                b[f'Finger{i}.01.L'].rotation_euler.z=(i-1.5)*.12*e
                b[f'Finger{i}.02.L'].rotation_euler.x=1.15*e
    elif name=='Hit_React':
        hit=math.sin(math.pi*t)**2*math.exp(-2*t)
        b['Chest'].rotation_euler.x=-.7*hit;b['Head'].rotation_euler.x=.40*hit
        stance(arm,.15*hit,.29)
        b['LidUpper'].rotation_euler.x=-1.48*(1-min(1,hit*3))
    elif name in {'Knockdown','Get_Up'}:
        a=t if name=='Knockdown' else 1-t
        a=a*a*(3-2*a)
        translate(arm,'Root',(0,.18*a,.18*a))
        b['Pelvis'].rotation_euler.x=-1.30*a
        translate(arm,'Pelvis',(0,0,-.65*a))
        b['Head'].rotation_euler.x=.20*a
        for s,side in [(-1,'R'),(1,'L')]:arm_pose(arm,side,(s,0,-.3),(s*.25,-.2,-1),a)
        b['Cape.01'].rotation_euler.x=.5*a
    elif name=='Idle_Relaxed':
        b['Chest'].rotation_euler.z=.012*math.sin(p)
        translate(arm,'Chest',(0,0,.004*math.sin(p)))


def animate(arm,mesh):
    arm.animation_data_create();clips=[]
    skins=[m for ob in bpy.context.scene.objects if ob.type=='MESH' for m in ob.modifiers if m.type=='ARMATURE']
    for m in skins:m.show_viewport=False
    for name,seconds,loop in CLIPS:
        end=round(seconds*30)+1;action=bpy.data.actions.new(name);action.use_fake_user=True
        arm.animation_data.action=action
        for frame in range(1,end+1):
            pose(arm,name,(frame-1)/(end-1))
            if name in {'Knockdown','Get_Up'}:
                for m in skins:m.show_viewport=True
                bpy.context.view_layer.update()
                evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=evaluated.to_mesh()
                lowest=min((evaluated.matrix_world@v.co).z for v in data.vertices);evaluated.to_mesh_clear()
                if lowest<.003:
                    arm.pose.bones['Root'].location+=arm.data.bones['Root'].matrix_local.to_quaternion().inverted()@Vector((0,0,.003-lowest))
                for m in skins:m.show_viewport=False
            for b in arm.pose.bones:
                b.keyframe_insert('rotation_euler',frame=frame,group=b.name)
                b.keyframe_insert('location',frame=frame,group=b.name)
        for fc in action.fcurves:
            for key in fc.keyframe_points:key.interpolation='LINEAR'
        row={'name':name,'seconds':seconds,'fps':30,'frames':end,'loop':loop,
             'root_motion':name in {'Jump','Knockdown','Get_Up'},
             'root_motion_policy':'Baked local jump/fall displacement; do not add a second jump arc.' if name in {'Jump','Knockdown','Get_Up'} else 'In place; drive actor translation in the game controller.'}
        if name in {'Walk_Forward','Walk_Backward','Run_Forward','Strafe_Left','Strafe_Right','Crouch_Walk'}:
            step=.34 if name=='Run_Forward' else .22 if name=='Crouch_Walk' else .20 if name.startswith('Strafe') else .28
            row['matching_controller_speed_m_s']=step*2/seconds
            row['contact']='Analytic level-foot two-link solve, 50 percent stance; engine motion must match clip speed.'
        if name=='Wrench_Attack':row['events']=[{'time':.52,'name':'tool_impact'}]
        if name=='Repair_Loop':row['events']=[{'time':.30,'name':'repair_tap'},{'time':.90,'name':'repair_tap'}]
        clips.append(row);print('AUTHORED_CLIP',name,end,flush=True)
    arm.animation_data.action=None;reset_pose(arm)
    for m in skins:m.show_viewport=True
    return clips


def export(hero,arm,mesh,clips,out):
    # Retain the expensive authored scene before attempting target conversion.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'rig-checkpoint.blend'),compress=True)
    outputs={}
    for name,ratio in [('AXM_Chaos_Hero',1),('AXM_Chaos_Hero_LOD1',.40)]:
        target=mesh
        if ratio<1:
            target=mesh.copy();target.data=mesh.data.copy();bpy.context.collection.objects.link(target)
            target.name=name;target.modifiers.clear();geo.select_only([target]);bpy.context.view_layer.objects.active=target
            mod=target.modifiers.new('Weighted game LOD','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name);clean_triangles(target)
            skin=target.modifiers.new('Skin','ARMATURE');skin.object=arm
        geo.select_only([arm,target]);bpy.context.view_layer.objects.active=arm
        path=out/(name+'.glb')
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
            export_apply=False,export_skins=True,export_def_bones=False,export_animations=True,
            export_animation_mode='ACTIONS',export_anim_slide_to_zero=True,
            export_force_sampling=True,export_yup=True,export_extras=True,export_tangents=True,
            export_cameras=False,export_lights=False,export_materials='EXPORT')
        target.data.calc_loop_triangles()
        outputs[name]={'path':path.name,'bytes':path.stat().st_size,'triangles':len(target.data.loop_triangles),
                       'vertices':len(target.data.vertices),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        if ratio<1:bpy.data.objects.remove(target,do_unlink=True)
    base_pose(arm);arm.animation_data.action=bpy.data.actions['Idle_Relaxed'];bpy.context.scene.frame_set(1)
    studio(1000)
    geo.select_only([arm]);bpy.context.view_layer.objects.active=arm
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'AXM_Chaos_Hero.blend'),compress=True)
    source_files=['axm_chaos_hero.py','axm_hero_motion.py','axm_hero_detail.py','axm_hero_closeup.py','axm_hero_surfaces.py','axm_oops_character.py','axm_blender_forge.py','axm_salvage_construction.py','axm_salvage_surfaces.py']
    report={'schema':'axm.hero-character/v1','asset_id':'axm-chaos-hero','height_m':2.25,'meters_per_unit':1,
            'exports':outputs,'animations':clips,'bones':[{'name':n,'parent':v[2]} for n,v in hero.bones.items()],
            'materials':len(mesh.data.materials),'editable_source':'AXM_Chaos_Hero.blend',
            'source_hashes':{n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in source_files},
            'reference':'1000000471.png; supplied character illustration',
            'reference_fidelity':'Authored 3D interpretation, not exact reconstruction. Rear surfaces inferred.',
            'binding':'Rigid armour and finger/face parts; blended head/jaw mouth and three-segment cape. Not muscle simulation.',
            'collision_recommendation':{'type':'capsule','radius_m':.35,'height_m':1.95,'center_y_m':.975},
            'engine_status':'Portable skeleton and clips; target engine/controller integration untested.'}
    (out/'character-manifest.json').write_text(json.dumps(report,indent=2)+'\n')


def studio(resolution):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8
    scene.render.resolution_x=resolution;scene.render.resolution_y=round(resolution*1.16)
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    if not scene.world:scene.world=bpy.data.worlds.new('Indigo workshop atmosphere')
    scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.13,.17,.27,1);bg.inputs['Strength'].default_value=.35
    from axm_salvage_surfaces import solid
    ground=solid('Preview ground','#242b3c',rough=.68)
    geo.box('PREVIEW_floor',(0,0,-.05),(200,200,.09),ground,bevel=0)
    from axm_salvage_construction import mesh as studio_mesh
    rows=[(-20,-.005)]+[(1+3*math.sin(i/32*math.pi/2),3*(1-math.cos(i/32*math.pi/2))-.005) for i in range(33)]+[(4,15)]
    vertices=[(x,y,z) for y,z in rows for x in [-20,20]]
    faces=[(i*2,i*2+1,i*2+3,i*2+2) for i in range(len(rows)-1)]
    studio_mesh('PREVIEW_cyclorama',vertices,faces,ground,smooth=True)
    for n,c,power,size,col in [('Warm key',(-3,-4,5),520,3,(1,.79,.58)),('Cool fill',(3,-2,3),350,2.8,(.65,.82,1)),('Edge light',(1.5,3,4),680,2,(.64,.73,1))]:
        d=bpy.data.lights.new(n,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=col
        o=bpy.data.objects.new(n,d);bpy.context.collection.objects.link(o);o.location=c
        o.rotation_euler=(Vector((0,0,1.1))-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='PREVIEW_camera';cam.data.type='ORTHO';cam.data.ortho_scale=2.85
    cam.location=(3,-7,3.0);cam.rotation_euler=(Vector((0,0,1.12))-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
    return cam


def preview(out,resolution,clip='Hero_Pose',frame=31,angle=12,filename='preview.png'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps=30
    bpy.ops.import_scene.gltf(filepath=str(out/'AXM_Chaos_Hero.glb'))
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    arm.animation_data.action=next(a for a in bpy.data.actions if a.name==clip or a.name.startswith(clip))
    if hasattr(arm.animation_data.action,'slots') and arm.animation_data.action.slots:
        arm.animation_data.action_slot=arm.animation_data.action.slots[0]
    bpy.context.scene.render.fps=30;bpy.context.scene.frame_set(frame)
    cam=studio(resolution);a=math.radians(angle);cam.location=(math.sin(a)*7,-math.cos(a)*7,2.9)
    cam.rotation_euler=(Vector((0,0,1.12))-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.scene.render.filepath=str(out/filename);bpy.ops.render.render(write_still=True)
