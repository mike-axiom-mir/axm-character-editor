from __future__ import annotations

"""Independent standard-library verifier for Character Editor rigged GLB candidates.

This module intentionally does not import the human builder. It reopens the binary
GLB, decodes accessors, evaluates node/skin transforms and animation channels, and
samples actual deformed vertices. This is software deformation evidence, not a
Blender/engine visual acceptance claim.
"""

import bisect
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

SCHEMA = "axm.character.independent-deformation-verification/v0.1"


class GameAssetVerificationError(ValueError):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise GameAssetVerificationError(message)


def _finite(rows):
    return all(math.isfinite(float(v)) for row in rows for v in row)


def _identity():
    return [
        1.0,0.0,0.0,0.0,
        0.0,1.0,0.0,0.0,
        0.0,0.0,1.0,0.0,
        0.0,0.0,0.0,1.0,
    ]


def _mul(a, b):
    return [sum(a[r*4+k]*b[k*4+c] for k in range(4)) for r in range(4) for c in range(4)]


def _transform(m, p):
    x,y,z=p
    q=[
        m[0]*x+m[1]*y+m[2]*z+m[3],
        m[4]*x+m[5]*y+m[6]*z+m[7],
        m[8]*x+m[9]*y+m[10]*z+m[11],
    ]
    w=m[12]*x+m[13]*y+m[14]*z+m[15]
    if abs(w-1.0) > 1e-7 and abs(w) > 1e-12:
        q=[v/w for v in q]
    return q


def _translation(v):
    x,y,z=v
    return [1,0,0,x, 0,1,0,y, 0,0,1,z, 0,0,0,1]


def _scale(v):
    x,y,z=v
    return [x,0,0,0, 0,y,0,0, 0,0,z,0, 0,0,0,1]


def _rotation(q):
    x,y,z,w=q
    n=math.sqrt(x*x+y*y+z*z+w*w)
    _require(n>1e-12,"zero quaternion")
    x,y,z,w=(v/n for v in (x,y,z,w))
    xx,yy,zz=x*x,y*y,z*z
    xy,xz,yz=x*y,x*z,y*z
    wx,wy,wz=w*x,w*y,w*z
    return [
        1-2*(yy+zz),2*(xy-wz),2*(xz+wy),0,
        2*(xy+wz),1-2*(xx+zz),2*(yz-wx),0,
        2*(xz-wy),2*(yz+wx),1-2*(xx+yy),0,
        0,0,0,1,
    ]


def _trs(node):
    return _mul(
        _mul(_translation(node.get("translation",[0,0,0])), _rotation(node.get("rotation",[0,0,0,1]))),
        _scale(node.get("scale",[1,1,1])),
    )


def _from_gltf_matrix(values):
    _require(isinstance(values,list) and len(values)==16,"invalid MAT4")
    return [float(values[c*4+r]) for r in range(4) for c in range(4)]


def _parse_glb(body: bytes):
    _require(len(body)>=28,"GLB too small")
    magic,version,length=struct.unpack_from("<4sII",body,0)
    _require(magic==b"glTF" and version==2 and length==len(body),"invalid GLB header")
    jlen,jtype=struct.unpack_from("<I4s",body,12)
    _require(jtype==b"JSON","missing JSON chunk")
    jstart=20
    jend=jstart+jlen
    _require(jend+8<=len(body),"truncated JSON chunk")
    doc=json.loads(body[jstart:jend].decode("utf-8").rstrip(" \0"))
    blen,btype=struct.unpack_from("<I4s",body,jend)
    _require(btype==b"BIN\0","missing BIN chunk")
    binary=body[jend+8:jend+8+blen]
    _require(len(binary)==blen,"truncated BIN chunk")
    return doc,binary


_COMPONENT={5126:("f",4),5125:("I",4),5123:("H",2),5121:("B",1)}
_WIDTH={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}


class Asset:
    def __init__(self, body: bytes):
        self.sha256=hashlib.sha256(body).hexdigest()
        self.doc,self.binary=_parse_glb(body)
        self.nodes=self.doc.get("nodes",[])
        self.views=self.doc.get("bufferViews",[])
        self.accessors=self.doc.get("accessors",[])
        _require(isinstance(self.nodes,list) and self.nodes,"nodes required")
        self.parents=[None]*len(self.nodes)
        for i,node in enumerate(self.nodes):
            _require(isinstance(node,dict),"node must be object")
            _require("matrix" not in node,"matrix-authored nodes are not supported by this bounded verifier")
            for child in node.get("children",[]):
                _require(type(child) is int and 0<=child<len(self.nodes),"invalid child")
                _require(self.parents[child] is None,"node has multiple parents")
                self.parents[child]=i
        self.order=[]
        roots=[i for i,p in enumerate(self.parents) if p is None]
        stack=list(reversed(roots))
        while stack:
            i=stack.pop()
            self.order.append(i)
            for child in reversed(self.nodes[i].get("children",[])):
                stack.append(child)
        _require(len(self.order)==len(self.nodes),"cyclic node hierarchy")
        self.node_names={node.get("name",f"node-{i}"):i for i,node in enumerate(self.nodes)}

    def accessor(self, ref: int):
        _require(type(ref) is int and 0<=ref<len(self.accessors),"invalid accessor")
        a=self.accessors[ref]
        _require(not a.get("sparse") and not a.get("extensions"),"sparse/extended accessor unsupported")
        kind=a.get("type")
        component=a.get("componentType")
        _require(kind in _WIDTH and component in _COMPONENT,"unsupported accessor format")
        count=a.get("count")
        _require(type(count) is int and 0<count<=5_000_000,"invalid accessor count")
        view_ref=a.get("bufferView")
        _require(type(view_ref) is int and 0<=view_ref<len(self.views),"invalid bufferView")
        view=self.views[view_ref]
        _require(view.get("buffer",0)==0 and not view.get("extensions"),"only embedded buffer zero supported")
        width=_WIDTH[kind]
        fmt,size=_COMPONENT[component]
        start=int(view.get("byteOffset",0))+int(a.get("byteOffset",0))
        stride=int(view.get("byteStride",width*size))
        _require(stride>=width*size and stride%size==0,"invalid accessor stride")
        end=start+(count-1)*stride+width*size
        _require(0<=start<end<=len(self.binary),"accessor exceeds binary")
        rows=[list(struct.unpack_from("<"+fmt*width,self.binary,start+i*stride)) for i in range(count)]
        _require(_finite(rows),"nonfinite accessor")
        if a.get("normalized"):
            _require(component in (5121,5123),"unsupported normalized component")
            divisor=255 if component==5121 else 65535
            rows=[[v/divisor for v in row] for row in rows]
        return rows

    def local_nodes(self):
        return [{
            "translation":[float(v) for v in n.get("translation",[0,0,0])],
            "rotation":[float(v) for v in n.get("rotation",[0,0,0,1])],
            "scale":[float(v) for v in n.get("scale",[1,1,1])],
        } for n in self.nodes]

    def _sample_track(self,times,values,time_s,mode,path):
        if time_s<=times[0]:
            return list(values[0])
        if time_s>=times[-1]:
            return list(values[-1])
        upper=bisect.bisect_right(times,time_s)
        lo=upper-1
        if mode=="STEP":
            return list(values[lo])
        alpha=(time_s-times[lo])/(times[upper]-times[lo])
        if path=="rotation":
            a=list(values[lo])
            b=list(values[upper])
            dot=sum(x*y for x,y in zip(a,b))
            if dot<0:
                b=[-x for x in b]
                dot=-dot
            dot=max(-1,min(1,dot))
            if dot>.9995:
                q=[x+(y-x)*alpha for x,y in zip(a,b)]
                n=math.sqrt(sum(v*v for v in q))
                return [v/n for v in q]
            theta=math.acos(dot)
            s=math.sin(theta)
            return [
                (math.sin((1-alpha)*theta)/s)*x+(math.sin(alpha*theta)/s)*y
                for x,y in zip(a,b)
            ]
        return [x+(y-x)*alpha for x,y in zip(values[lo],values[upper])]

    def clip(self,name):
        for animation in self.doc.get("animations",[]):
            if animation.get("name")==name:
                return animation
        raise GameAssetVerificationError(f"missing clip {name!r}")

    def clip_times(self,name):
        animation=self.clip(name)
        times=set()
        for sampler in animation.get("samplers",[]):
            times.update(row[0] for row in self.accessor(sampler["input"]))
        return sorted(times)

    def pose(self,clip_name=None,time_s=0.0):
        local=self.local_nodes()
        if clip_name is not None:
            animation=self.clip(clip_name)
            samplers=animation.get("samplers",[])
            for channel in animation.get("channels",[]):
                target=channel.get("target",{})
                node=target.get("node")
                path=target.get("path")
                _require(type(node) is int and 0<=node<len(local),"animation target node invalid")
                _require(path in ("translation","rotation","scale"),"animation path unsupported")
                sampler_ref=channel.get("sampler")
                _require(type(sampler_ref) is int and 0<=sampler_ref<len(samplers),"animation sampler invalid")
                sampler=samplers[sampler_ref]
                times=[row[0] for row in self.accessor(sampler["input"])]
                values=self.accessor(sampler["output"])
                _require(len(times)==len(values),"animation sample count mismatch")
                mode=sampler.get("interpolation","LINEAR")
                _require(mode in ("LINEAR","STEP"),"animation interpolation unsupported")
                local[node][path]=self._sample_track(times,values,time_s,mode,path)
        world=[None]*len(self.nodes)
        for i in self.order:
            m=_trs(local[i])
            p=self.parents[i]
            world[i]=m if p is None else _mul(world[p],m)
            _require(all(math.isfinite(v) for v in world[i]),"nonfinite node transform")
        return world

    def skin(self,index=0):
        skins=self.doc.get("skins",[])
        _require(type(index) is int and 0<=index<len(skins),"skin missing")
        skin=skins[index]
        joints=skin.get("joints",[])
        _require(isinstance(joints,list) and joints,"skin joints required")
        inv=[_from_gltf_matrix(row) for row in self.accessor(skin["inverseBindMatrices"])]
        _require(len(inv)==len(joints),"inverse bind count mismatch")
        return joints,inv

    def mesh_records(self):
        meshes=self.doc.get("meshes",[])
        records=[]
        for node_index,node in enumerate(self.nodes):
            if "mesh" not in node:
                continue
            _require(node.get("skin")==0,"all current candidate mesh nodes must use skin 0")
            mesh_ref=node["mesh"]
            _require(type(mesh_ref) is int and 0<=mesh_ref<len(meshes),"mesh reference invalid")
            for prim in meshes[mesh_ref].get("primitives",[]):
                attrs=prim.get("attributes",{})
                for key in ("POSITION","JOINTS_0","WEIGHTS_0"):
                    _require(key in attrs,f"missing {key}")
                positions=self.accessor(attrs["POSITION"])
                joints=self.accessor(attrs["JOINTS_0"])
                weights=self.accessor(attrs["WEIGHTS_0"])
                _require(len(positions)==len(joints)==len(weights),"skin attribute counts differ")
                indices=[r[0] for r in self.accessor(prim["indices"])]
                _require(all(type(i) is int and 0<=i<len(positions) for i in indices),"index out of bounds")
                _require(len(indices)%3==0,"triangle index count invalid")
                records.append({
                    "node":node_index,
                    "positions":positions,
                    "joints":joints,
                    "weights":weights,
                    "indices":indices,
                })
        _require(records,"no skinned mesh records")
        return records

    def deformed_vertices(self,clip_name=None,time_s=0.0):
        world=self.pose(clip_name,time_s)
        skin_joints,inverses=self.skin(0)
        palette=[_mul(world[j],ibm) for j,ibm in zip(skin_joints,inverses)]
        out=[]
        for record in self.mesh_records():
            mesh_world=world[record["node"]]
            _require(
                max(abs(a-b) for a,b in zip(mesh_world,_identity()))<1e-7,
                "non-identity mesh transform unsupported",
            )
            points=[]
            for p,jrow,wrow in zip(record["positions"],record["joints"],record["weights"]):
                _require(
                    all(type(j) is int and 0<=j<len(palette) for j in jrow),
                    "joint index out of skin range",
                )
                _require(
                    all(w>=-1e-7 for w in wrow) and abs(sum(wrow)-1)<=2e-5,
                    "invalid normalized skin weights",
                )
                influences=[_transform(palette[j],p) for j in jrow]
                q=[
                    sum(influences[k][axis]*wrow[k] for k in range(4))
                    for axis in range(3)
                ]
                _require(all(math.isfinite(v) for v in q),"nonfinite deformed vertex")
                points.append(q)
            out.append(points)
        return out


def _bounds(meshes):
    pts=[p for mesh in meshes for p in mesh]
    return {
        "min":[min(p[i] for p in pts) for i in range(3)],
        "max":[max(p[i] for p in pts) for i in range(3)],
    }


def _max_delta(a,b):
    _require(len(a)==len(b),"mesh count changed during animation")
    result=0.0
    for ma,mb in zip(a,b):
        _require(len(ma)==len(mb),"vertex count changed during animation")
        for pa,pb in zip(ma,mb):
            result=max(result,math.dist(pa,pb))
    return result


def verify_bytes(body: bytes) -> dict[str, Any]:
    asset=Asset(body)
    doc=asset.doc
    _require(doc.get("asset",{}).get("version")=="2.0","glTF 2.0 required")
    rest=asset.deformed_vertices()
    rest_bounds=_bounds(rest)
    height=rest_bounds["max"][1]-rest_bounds["min"][1]
    ground=rest_bounds["min"][1]
    clips=[a.get("name") for a in doc.get("animations",[])]
    _require(set(clips)=={"Idle","Walk","Wave"},"starter clip set changed")
    observations=[]
    for name in clips:
        times=asset.clip_times(name)
        _require(len(times)>=2,"clip needs multiple key times")
        samples=[(t,asset.deformed_vertices(name,t)) for t in times]
        max_motion=max(_max_delta(rest,posed) for _,posed in samples)
        endpoint=_max_delta(samples[0][1],samples[-1][1])
        observations.append({
            "clip":name,
            "sample_times_s":times,
            "max_vertex_motion_m":max_motion,
            "endpoint_delta_m":endpoint,
            "actually_deforms_mesh":max_motion>.001,
            "closed_endpoint":endpoint<1e-5,
        })
    records=asset.mesh_records()
    checks={
        "metre_scale_height":1.35<=height<=2.20,
        "grounded_rest_pose":-.002<=ground<=.03,
        "one_skin":len(doc.get("skins",[]))==1,
        "humanoid_joint_count":len(doc["skins"][0].get("joints",[]))==18,
        "all_clips_deform":all(r["actually_deforms_mesh"] for r in observations),
        "all_clip_endpoints_close":all(r["closed_endpoint"] for r in observations),
        "finite_rest_bounds":all(math.isfinite(v) for v in rest_bounds["min"]+rest_bounds["max"]),
    }
    return {
        "schema":SCHEMA,
        "source_sha256":asset.sha256,
        "status":"SOFTWARE_DEFORMATION_PASS" if all(checks.values()) else "SOFTWARE_DEFORMATION_REVIEW_REQUIRED",
        "checks":checks,
        "rest_bounds_m":rest_bounds,
        "height_m":height,
        "ground_min_y_m":ground,
        "mesh_primitives":len(records),
        "vertices":sum(len(r["positions"]) for r in records),
        "clips":observations,
        "truth":(
            "Independent standard-library GLB decode and linear-skin playback over actual exported bytes. "
            "This does not substitute for Blender/target-engine import, visual deformation judgment, "
            "collision or runtime performance."
        ),
    }


def verify_path(path: str|Path) -> dict[str, Any]:
    path=Path(path)
    result=verify_bytes(path.read_bytes())
    result["path"]=str(path)
    return result
