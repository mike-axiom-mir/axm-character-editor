#!/usr/bin/env python3
"""Compile an AXM Doll Blueprint v1 scene plan into editable Blender/GLB outputs.

This is a new generic bounded doll builder. It does not replace or modify the
recovered Odd Shift Duo builder, which remains the regression baseline.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(tail)


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.armatures, bpy.data.materials, bpy.data.meshes, bpy.data.curves,
                       bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def rgba(hex_color):
    raw = hex_color.lstrip("#")
    return tuple(int(raw[i:i+2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


def _socket(node, name, *aliases):
    for candidate in (name, *aliases):
        value = node.inputs.get(candidate)
        if value is not None:
            return value
    raise RuntimeError(f"required Blender 4.x material socket is missing: {name}")


def _rgb4(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("expected RGB triplet")
    return tuple(float(v) for v in value) + (1.0,)


def _bind_breakup(material, bsdf, plan, base_color, base_roughness):
    node_plan = next((item for item in plan.get("node_plans", []) if item.get("kind") == "object-space-noise-breakup"), None)
    if node_plan is None:
        return []
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    tex.name = "AXM Response Object Coordinates"
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "AXM Response Breakup"
    noise.noise_dimensions = node_plan.get("noise_dimensions", "4D")
    _socket(noise, "Scale").default_value = float(node_plan["scale"])
    _socket(noise, "Detail").default_value = float(node_plan["detail"])
    if noise.inputs.get("W") is not None:
        noise.inputs["W"].default_value = float(node_plan["seed_w"])
    object_output = tex.outputs.get("Object")
    if object_output is None:
        raise RuntimeError("ShaderNodeTexCoord Object output is missing")
    links.new(object_output, _socket(noise, "Vector"))

    created = [tex.name, noise.name]
    rough_var = float(node_plan.get("roughness_variation", 0))
    if rough_var > 0:
        centered = nodes.new("ShaderNodeMath")
        centered.name = "AXM Breakup Roughness Center"
        centered.operation = "SUBTRACT"
        centered.inputs[1].default_value = 0.5
        links.new(noise.outputs["Fac"], centered.inputs[0])

        scale = nodes.new("ShaderNodeMath")
        scale.name = "AXM Breakup Roughness Amount"
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = 2.0 * rough_var
        links.new(centered.outputs[0], scale.inputs[0])

        add = nodes.new("ShaderNodeMath")
        add.name = "AXM Breakup Roughness Result"
        add.operation = "ADD"
        add.inputs[1].default_value = float(base_roughness)
        add.use_clamp = True
        links.new(scale.outputs[0], add.inputs[0])
        links.new(add.outputs[0], _socket(bsdf, "Roughness"))
        created.extend([centered.name, scale.name, add.name])

    color_var = float(node_plan.get("color_variation", 0))
    if color_var > 0:
        centered = nodes.new("ShaderNodeMath")
        centered.name = "AXM Breakup Color Center"
        centered.operation = "SUBTRACT"
        centered.inputs[1].default_value = 0.5
        links.new(noise.outputs["Fac"], centered.inputs[0])

        scale = nodes.new("ShaderNodeMath")
        scale.name = "AXM Breakup Color Amount"
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = 2.0 * color_var
        links.new(centered.outputs[0], scale.inputs[0])

        add = nodes.new("ShaderNodeMath")
        add.name = "AXM Breakup Color Multiplier"
        add.operation = "ADD"
        add.inputs[1].default_value = 1.0
        links.new(scale.outputs[0], add.inputs[0])

        mix = nodes.new("ShaderNodeMixRGB")
        mix.name = "AXM Breakup Base Color"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value = base_color
        links.new(add.outputs[0], mix.inputs[2])
        links.new(mix.outputs["Color"], _socket(bsdf, "Base Color"))
        created.extend([centered.name, scale.name, add.name, mix.name])
    return created



def _bind_directional_roughness_fallback(material, bsdf, node_plan, base_roughness):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    tex = nodes.new("ShaderNodeTexCoord")
    tex.name = "AXM Anisotropy Fallback Coordinates"
    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = "AXM Anisotropy Fallback Mapping"
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "AXM Anisotropy Fallback Noise"
    noise.noise_dimensions = "3D"
    _socket(noise, "Scale").default_value = float(node_plan.get("scale", 7.0))
    _socket(noise, "Detail").default_value = 2.0

    direction = node_plan.get("direction", "tangent_u")
    stretch = float(node_plan.get("stretch", 8.0))
    if direction == "tangent_v":
        mapping.inputs["Scale"].default_value = (stretch, 1.0, stretch)
    else:
        mapping.inputs["Scale"].default_value = (1.0, stretch, stretch)
    mapping.inputs["Rotation"].default_value[2] = float(node_plan.get("rotation", 0.0)) * 2.0 * math.pi

    links.new(tex.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])

    centered = nodes.new("ShaderNodeMath")
    centered.name = "AXM Anisotropy Fallback Center"
    centered.operation = "SUBTRACT"
    centered.inputs[1].default_value = 0.5
    links.new(noise.outputs["Fac"], centered.inputs[0])

    amount = nodes.new("ShaderNodeMath")
    amount.name = "AXM Anisotropy Fallback Amount"
    amount.operation = "MULTIPLY"
    amount.inputs[1].default_value = 2.0 * float(node_plan.get("roughness_variation", 0.16))
    links.new(centered.outputs[0], amount.inputs[0])

    roughness = _socket(bsdf, "Roughness")
    add = nodes.new("ShaderNodeMath")
    add.name = "AXM Anisotropy Fallback Roughness"
    add.operation = "ADD"
    add.use_clamp = True
    if roughness.is_linked:
        previous = roughness.links[0].from_socket
        links.new(previous, add.inputs[0])
    else:
        add.inputs[0].default_value = float(base_roughness)
    links.new(amount.outputs[0], add.inputs[1])
    links.new(add.outputs[0], roughness)

    return [tex.name, mapping.name, noise.name, centered.name, amount.name, add.name]

def apply_response_binding(material, bsdf, spec):
    plan = spec.get("blender_response_binding")
    if not plan:
        return None
    applied = []
    for name, value in plan.get("principled_sockets", {}).items():
        aliases = ("Anisotropic",) if name == "Anisotropic IOR Level" else ()
        _socket(bsdf, name, *aliases).default_value = float(value)
        applied.append(name)
    for name, value in plan.get("principled_colors", {}).items():
        _socket(bsdf, name).default_value = _rgb4(value)
        applied.append(name)
    for name, value in plan.get("principled_vectors", {}).items():
        _socket(bsdf, name).default_value = tuple(float(v) for v in value)
        applied.append(name)
    for name, value in plan.get("shader_properties", {}).items():
        if name == "subsurface_method":
            bsdf.subsurface_method = value
            applied.append("subsurface_method")
        else:
            raise RuntimeError(f"unsupported response shader property {name!r}")

    node_names = []
    tangent_plan = next((item for item in plan.get("node_plans", []) if item.get("kind") == "radial-object-tangent"), None)
    if tangent_plan is not None:
        tangent_socket = bsdf.inputs.get("Tangent")
        if tangent_socket is None:
            raise RuntimeError("surface.anisotropy planned but Principled BSDF Tangent socket is missing")
        tangent = material.node_tree.nodes.new("ShaderNodeTangent")
        tangent.name = "AXM Response Tangent"
        tangent.direction_type = tangent_plan["direction_type"]
        tangent.axis = tangent_plan["axis"]
        material.node_tree.links.new(tangent.outputs["Tangent"], tangent_socket)
        node_names.append(tangent.name)

    node_names.extend(_bind_breakup(
        material,
        bsdf,
        plan,
        rgba(spec["color"]),
        float(spec["roughness"]),
    ))
    for fallback_plan in (
        item for item in plan.get("node_plans", [])
        if item.get("kind") == "directional-roughness-fallback"
    ):
        node_names.extend(_bind_directional_roughness_fallback(
            material, bsdf, fallback_plan, float(spec["roughness"])
        ))
    material["axm_response_binding_plan"] = json.dumps(plan, sort_keys=True)
    return {
        "material": spec["id"],
        "family": spec.get("response_family"),
        "requested_organs": plan.get("requested_organs", []),
        "bound_organs": plan.get("bound_organs", []),
        "held_organs": plan.get("held_organs", []),
        "partial_bindings": plan.get("partial_bindings", []),
        "fallbacks": plan.get("fallbacks", []),
        "applied_sockets": sorted(applied),
        "created_nodes": node_names,
        "evidence": "declared_contract_match_not_tested",
        "render_verified_organs": [],
    }


def make_material(spec):
    material = bpy.data.materials.new(spec["id"])
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    base_color = rgba(spec["color"])
    _socket(bsdf, "Base Color").default_value = base_color
    _socket(bsdf, "Metallic").default_value = float(spec["metallic"])
    _socket(bsdf, "Roughness").default_value = float(spec["roughness"])
    if "specular" in spec and bsdf.inputs.get("Specular IOR Level") is not None:
        bsdf.inputs["Specular IOR Level"].default_value = float(spec["specular"])
    if spec.get("response_family"):
        material["axm_response_family"] = spec["response_family"]
        material["axm_response_renderer_binding"] = spec.get(
            "response_renderer_binding", "HOLD_RENDER_VERIFICATION_REQUIRED"
        )
        material["axm_active_organs"] = json.dumps(spec.get("active_organs", []), sort_keys=True)
    return material, apply_response_binding(material, bsdf, spec)


def make_rig(bones):
    data = bpy.data.armatures.new("AXM_Doll_Blueprint_RigData")
    rig = bpy.data.objects.new("AXM_Doll_Blueprint_Rig", data)
    bpy.context.collection.objects.link(rig)
    rig["axm_deformation"] = "RIGID_BONE_PARENTING"
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for spec in bones:
        bone = data.edit_bones.new(spec["name"])
        bone.head = spec["head"]
        bone.tail = spec["tail"]
        if spec.get("parent"):
            bone.parent = data.edit_bones.get(spec["parent"])
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    return rig


def assign(obj, material):
    if material and hasattr(obj.data, "materials"):
        obj.data.materials.append(material)


def bone_parent(obj, rig, bone_name):
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world


def smooth(obj):
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def cylinder_between(start, end, radius):
    start_v, end_v = Vector(start), Vector(end)
    direction = end_v - start_v
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=direction.length,
                                       location=(start_v + end_v) * 0.5)
    obj = bpy.context.object
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj


def create_object(spec, materials, rig):
    primitive = spec["primitive"]
    if primitive == "ellipsoid":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=16, location=spec["location"])
        obj = bpy.context.object
        obj.scale = spec["scale"]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        smooth(obj)
    elif primitive == "box":
        bpy.ops.mesh.primitive_cube_add(location=spec["location"], rotation=spec.get("rotation", [0,0,0]))
        obj = bpy.context.object
        obj.dimensions = spec["dimensions"]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = obj.modifiers.new("crafted edge", "BEVEL")
        bevel.width = min(spec["dimensions"]) * 0.08
        bevel.segments = 2
    elif primitive == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=spec["radius"], depth=spec["depth"],
                                           location=spec["location"], rotation=spec.get("rotation", [0,0,0]))
        obj = bpy.context.object
        smooth(obj)
    elif primitive == "cylinder_between":
        obj = cylinder_between(spec["start"], spec["end"], spec["radius"])
        smooth(obj)
    elif primitive == "torus":
        bpy.ops.mesh.primitive_torus_add(major_radius=spec["major_radius"], minor_radius=spec["minor_radius"],
                                        major_segments=32, minor_segments=12, location=spec["location"],
                                        rotation=spec.get("rotation", [0,0,0]))
        obj = bpy.context.object
        obj.scale = spec.get("scale", [1,1,1])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        smooth(obj)
    else:
        raise ValueError(f"unsupported primitive {primitive!r}")
    obj.name = spec["id"]
    obj["axm_blueprint_part"] = True
    obj["axm_part_id"] = spec["id"]
    assign(obj, materials[spec["material"]])
    bone_parent(obj, rig, spec["bone"])
    return obj


def animate(rig, keys):
    if not keys:
        return
    action = bpy.data.actions.new("AXM_Blueprint_Action")
    rig.animation_data_create()
    rig.animation_data.action = action
    for spec in keys:
        pose_bone = rig.pose.bones.get(spec["bone"])
        if pose_bone is None:
            raise ValueError(f"missing animation bone {spec['bone']}")
        pose_bone.rotation_mode = "XYZ"
        pose_bone.rotation_euler = spec["rotation_euler"]
        pose_bone.keyframe_insert(data_path="rotation_euler", frame=spec["frame"], group=spec["bone"])


def stage(scene, plan):
    world = bpy.data.worlds.new("AXM Blueprint World") if bpy.data.worlds.get("AXM Blueprint World") is None else bpy.data.worlds["AXM Blueprint World"]
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = rgba(plan["scene"]["background"])
    bg.inputs["Strength"].default_value = 0.42

    bpy.ops.object.camera_add(location=plan["scene"]["camera"]["location"])
    camera = bpy.context.object
    camera.name = "AXM_Blueprint_Camera"
    camera.data.lens = plan["scene"]["camera"]["lens"]
    target = Vector((0, 0, 1.55))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    for loc, energy, size in [((-4,-4,7), 1100, 4.0), ((4,-2,5), 800, 3.0), ((0,4,4), 600, 3.0)]:
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (Vector((0,0,1.5)) - light.location).to_track_quat("-Z", "Y").to_euler()

    bpy.ops.mesh.primitive_plane_add(size=20, location=(0,0,0))
    floor = bpy.context.object
    floor.name = "AXM_Blueprint_Floor"
    mat = bpy.data.materials.new("AXM_Floor")
    mat.diffuse_color = (0.12,0.13,0.15,1)
    floor.data.materials.append(mat)


def main():
    cfg = parse_args()
    plan = json.loads(Path(cfg.plan).read_text(encoding="utf-8"))
    if plan.get("schema") != "axm.avatar.scene-plan/v1":
        raise ValueError("unsupported scene plan schema")
    out = Path(cfg.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    reset_scene()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out / "Blueprint-Avatar-Poster.png")
    scene.render.fps = plan["scene"]["fps"]
    scene.frame_start = plan["scene"]["frame_start"]
    scene.frame_end = plan["scene"]["frame_end"]
    scene["axm_blueprint_plan_sha256"] = plan["plan_sha256"]
    scene["axm_deformation"] = "RIGID_BONE_PARENTING"

    materials = {}
    response_binding_receipts = []
    for spec in plan["materials"]:
        material, response_receipt = make_material(spec)
        materials[spec["id"]] = material
        if response_receipt is not None:
            response_binding_receipts.append(response_receipt)
    rig = make_rig(plan["bones"])
    for spec in plan["objects"]:
        create_object(spec, materials, rig)
    animate(rig, plan["animation"])
    stage(scene, plan)

    scene.frame_set(scene.frame_start)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "Blueprint-Avatar.blend"))
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for obj in bpy.data.objects:
        if obj.get("axm_blueprint_part"):
            obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(out / "Blueprint-Avatar.glb"),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
    )
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.render.render(write_still=True)

    from verify_material_response_v1 import run_verification
    material_verification = run_verification(out / "material-response-proof")

    response_materials = [spec for spec in plan["materials"] if spec.get("response_family")]
    active_response_organs = sorted({
        organ for spec in response_materials for organ in spec.get("active_organs", [])
    })
    bound_response_organs = sorted({
        organ for receipt in response_binding_receipts for organ in receipt.get("bound_organs", [])
    })
    held_response_organs = []
    seen_holds = set()
    for receipt in response_binding_receipts:
        for item in receipt.get("held_organs", []):
            key = (item.get("organ"), item.get("reason"))
            if key not in seen_holds:
                held_response_organs.append(item)
                seen_holds.add(key)

    fallback_response_organs = []
    seen_fallbacks = set()
    for receipt in response_binding_receipts:
        for item in receipt.get("fallbacks", []):
            key = (item.get("organ"), item.get("fallback"), item.get("evidence"))
            if key not in seen_fallbacks:
                fallback_response_organs.append(item)
                seen_fallbacks.add(key)

    partial_response_organs = []
    seen_partial = set()
    for receipt in response_binding_receipts:
        for item in receipt.get("partial_bindings", []):
            key = (
                item.get("organ"),
                tuple(item.get("bound_fields", [])),
                tuple(item.get("held_fields", [])),
                item.get("renderer_method"),
            )
            if key not in seen_partial:
                partial_response_organs.append(item)
                seen_partial.add(key)
    verified_response_organs = sorted(material_verification.get("verified_organs", []))
    verified_partial_response_organs = material_verification.get("verified_partial_organs", [])
    verified_response_fallbacks = material_verification.get("verified_fallbacks", [])
    material_response_status = "PASS_NO_ACTIVE_ORGANS"
    if bound_response_organs:
        material_response_status = (
            "PASS_BOUND_ORGANS_HOST_VERIFIED"
            if set(bound_response_organs).issubset(set(verified_response_organs))
            else "HOLD_RENDER_VERIFICATION_INCOMPLETE"
        )
    if held_response_organs:
        material_response_status = (
            "HOLD_PARTIAL_BINDING_AFTER_HOST_VERIFICATION"
            if set(bound_response_organs).issubset(set(verified_response_organs))
            else "HOLD_PARTIAL_BINDING_AND_RENDER_VERIFICATION_REQUIRED"
        )
    receipt = {
        "schema": "axm.avatar.blueprint-build-receipt/v1",
        "plan_sha256": plan["plan_sha256"],
        "deformation": "RIGID_BONE_PARENTING",
        "objects": len(plan["objects"]),
        "bones": len(plan["bones"]),
        "materials": len(plan["materials"]),
        "animation_keys": len(plan["animation"]),
        "outputs": ["Blueprint-Avatar.blend", "Blueprint-Avatar.glb", "Blueprint-Avatar-Poster.png"],
        "material_response": {
            "selected_materials": len(response_materials),
            "active_organs": active_response_organs,
            "bound_not_render_verified_organs": bound_response_organs,
            "held_organs": held_response_organs,
            "partial_bindings": partial_response_organs,
            "fallbacks": fallback_response_organs,
            "render_verified_organs": verified_response_organs,
            "render_verified_partial_organs": verified_partial_response_organs,
            "render_verified_fallbacks": verified_response_fallbacks,
            "host_verification": material_verification,
            "base_scalar_projection": True,
            "binding_constructed": bool(bound_response_organs or fallback_response_organs),
            "binding_receipts": response_binding_receipts,
            "status": material_response_status,
        },
        "status": (
            "BUILT_WITH_MATERIAL_RESPONSE_HOLD_NOT_AESTHETICALLY_ACCEPTED"
            if active_response_organs else "BUILT_NOT_AESTHETICALLY_ACCEPTED"
        ),
    }
    (out / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
