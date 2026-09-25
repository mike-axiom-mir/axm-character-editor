"""Fresh-import playback/weight checks for the machine's portable character files."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy


def positions(mesh):
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    points = [tuple(evaluated.matrix_world @ vertex.co) for vertex in data.vertices]
    evaluated.to_mesh_clear()
    if not points or not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("empty or nonfinite evaluated mesh")
    return points


def reset(arm):
    arm.animation_data_create()
    arm.animation_data.action = None
    for bone in arm.pose.bones:
        bone.location = (0,0,0)
        bone.rotation_quaternion = (1,0,0,0)
        bone.rotation_euler = (0,0,0)
        bone.scale = (1,1,1)
    bpy.context.view_layer.update()


def inspect(path, expected_bones=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30
    if path.suffix == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif path.suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise ValueError("only GLB and FBX are supported")
    arms = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    # glTF's importer adds an Icosphere used as a bone custom shape. It is a
    # viewport helper, not another character mesh; identify it by actual use.
    custom_shapes = {bone.custom_shape for arm in arms for bone in arm.pose.bones if bone.custom_shape}
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj not in custom_shapes]
    if len(arms) != 1 or len(meshes) != 1:
        raise ValueError(f"expected one armature and one mesh, received {len(arms)} / {len(meshes)}")
    arm,mesh = arms[0],meshes[0]
    reset(arm)
    rest = positions(mesh)
    bounds = {"min":[min(p[axis] for p in rest) for axis in range(3)],
              "max":[max(p[axis] for p in rest) for axis in range(3)]}
    bad_weights = sum(1 for vertex in mesh.data.vertices
                      if abs(sum(group.weight for group in vertex.groups)-1)>1e-4 or not vertex.groups)
    missing_groups = [group.name for group in mesh.vertex_groups if group.name not in arm.data.bones]
    results = []
    walk_contact = None
    for action in bpy.data.actions:
        if not action.slots:
            continue
        reset(arm)
        arm.animation_data.action = action
        arm.animation_data.action_slot = action.slots[0]
        first,last = action.frame_range
        samples = []
        for fraction in (0,.25,.5,.75,1):
            frame = first+(last-first)*fraction
            bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
            samples.append(positions(mesh))
        largest_motion = max(math.dist(a,b) for points in samples for a,b in zip(rest,points))
        loop_delta = max(math.dist(a,b) for a,b in zip(samples[0],samples[-1]))
        minimum_z = min(point[2] for points in samples for point in points)
        results.append({"name":action.name,"frame_range":[first,last],"largest_vertex_motion_m":largest_motion,
                        "endpoint_delta_m":loop_delta,"minimum_sampled_z_m":minimum_z,
                        "sampled_sole_heights_m":[min(point[2] for point in points) for points in samples],
                        "actually_deforms_mesh":largest_motion>.0001})
        if "Walk_InPlace" in action.name and "Finger1Tip.L" in arm.data.bones:
            soles={}
            for side in ("L","R"):
                group=mesh.vertex_groups.get(f"Foot.{side}")
                indices=[v.index for v in mesh.data.vertices if rest[v.index][2]<.015 and
                         any(g.group==group.index and g.weight>.5 for g in v.groups)] if group else []
                if not indices:
                    raise ValueError(f"no imported sole vertices for Foot.{side}")
                soles[side]=indices
            frame_rows=[]
            for frame in range(round(first),round(last)+1):
                bpy.context.scene.frame_set(frame)
                points=positions(mesh)
                row={"frame":frame,"feet":{}}
                for side,indices in soles.items():
                    row["feet"][side]={"min_z":min(points[i][2] for i in indices),
                                         "mean_y":sum(points[i][1] for i in indices)/len(indices)}
                frame_rows.append(row)
            max_height_error,max_velocity_error=0,0
            duration=last-first
            for i,row in enumerate(frame_rows):
                for side in soles:
                    phase=((row["frame"]-first)/duration+(0 if side=="L" else .5))%1
                    if phase<.5:
                        max_height_error=max(max_height_error,abs(row["feet"][side]["min_z"]-.0035))
                        if i+1<len(frame_rows) and phase+1/duration<.5:
                            dy=frame_rows[i+1]["feet"][side]["mean_y"]-row["feet"][side]["mean_y"]
                            max_velocity_error=max(max_velocity_error,abs(dy-.3/duration))
            walk_contact={"sampled_every_export_frame":True,"frames":frame_rows,
                          "maximum_stance_height_error_m":max_height_error,
                          "maximum_stance_step_error_m":max_velocity_error,
                          "note":"In-place backward stance motion matches 0.28125 m/s forward game travel; no controller tested."}
    required = {"Idle","Walk_InPlace","Wave","Oops_Recover"}
    found = {clip for clip in required if any(clip in row["name"] and row["actually_deforms_mesh"] for row in results)}
    gates = {"one-rig-one-mesh":True,"normalized-weights":bad_weights==0,"valid-bone-groups":not missing_groups,
             "all-clips-deform-imported-mesh":found==required,
             "meter-scale-height":1.1<bounds["max"][2]-bounds["min"][2]<1.7,
             "grounded-rest-pose":-.012<=bounds["min"][2]<=.015,
             "closed-clip-endpoints":all(row["endpoint_delta_m"]<.001 for row in results),
             "walk-sampled-ground-contact":all(abs(z-.0035)<.012 for row in results if "Walk_InPlace" in row["name"]
                                                for z in row["sampled_sole_heights_m"])}
    if expected_bones is not None:
        gates["skeleton-matches-manifest"]=set(arm.data.bones.keys())==set(expected_bones)
    if walk_contact:
        gates["walk-every-frame-stance-height"]=walk_contact["maximum_stance_height_error_m"]<.004
        gates["walk-every-frame-stance-speed"]=walk_contact["maximum_stance_step_error_m"]<.002
    return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"gates":gates,
            "status":"ROUNDTRIP_PLAYBACK_PASS" if all(gates.values()) else "ROUNDTRIP_REVIEW_REQUIRED",
            "bad_weight_vertices":bad_weights,"missing_bone_groups":missing_groups,"bounds_m":bounds,
            "vertices":len(mesh.data.vertices),"bones":len(arm.data.bones),"clips":results,
            "full_frame_walk_contact":walk_contact}


def inspect_animation_fbx(path, expected_clip, expected_bones):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps=30
    bpy.ops.import_scene.fbx(filepath=str(path))
    arms=[obj for obj in bpy.context.scene.objects if obj.type=="ARMATURE"]
    if len(arms)!=1:
        raise ValueError("animation FBX must contain exactly one armature")
    arm=arms[0]
    actions=list(bpy.data.actions)
    samples=[]
    for action in actions:
        reset(arm)
        arm.animation_data.action=action
        arm.animation_data.action_slot=action.slots[0]
        first,last=action.frame_range
        poses=[]
        for fraction in (0,.25,.5,.75,1):
            frame=first+(last-first)*fraction
            bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
            poses.append([tuple(bone.tail) for bone in arm.pose.bones])
        samples.append(max(math.dist(a,b) for pose in poses[1:] for a,b in zip(poses[0],pose)))
    gates={"one-take":len(actions)==1,"skeleton-matches-manifest":set(arm.data.bones.keys())==set(expected_bones),
           "root-and-grip-sockets":all(name in arm.data.bones for name in ("Root","Socket_Grip.L","Socket_Grip.R")),
           "take-actually-moves-bones":bool(samples) and max(samples)>.0001}
    return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "clip":expected_clip,"take_names":[action.name for action in actions],"gates":gates,
            "status":"PASS" if all(gates.values()) else "REVIEW_REQUIRED"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--directory",required=True)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    directory=Path(args.directory).resolve()
    manifest=json.loads((directory/"character-manifest.json").read_text(encoding="utf-8"))
    expected_bones=[bone["name"] for bone in manifest["bones"]]
    results=[inspect(directory/name,expected_bones) for name in ("AXM_OOPS_LOD0.glb","AXM_OOPS_LOD1.glb","AXM_OOPS_LOD2.glb","AXM_OOPS.fbx")]
    separate=[]
    for name in ("Idle","Walk_InPlace","Wave","Oops_Recover"):
        path=directory/"animations"/f"AXM_OOPS_{name}.fbx"
        if path.is_file():
            separate.append(inspect_animation_fbx(path,name,expected_bones))
    report={"schema":"axm.character-roundtrip/v0.1","artifacts":results,
            "separate_animation_fbx":separate,
            "status":"PASS" if all(row["status"]=="ROUNDTRIP_PLAYBACK_PASS" for row in results) and
                                    len(separate)==4 and all(row["status"]=="PASS" for row in separate) else "REVIEW_REQUIRED",
            "truth":"Fresh Blender imports and sampled playback; Unity/Unreal/Godot gameplay not tested."}
    (directory/"roundtrip-verification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)
    if report["status"]!="PASS":
        raise RuntimeError("character round-trip checks need review")


if __name__=="__main__":
    main()
