"""Verify per-point Axis Lock (Lock X/Y/Z): copies ignore curve points moved along a locked axis.
Run: ./run_blender.sh tests/verify_lock.py -- <array_plus.blend>
"""
import bpy, sys, json, bmesh
from mathutils import Vector

blend = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(blend) as (s, d):
    d.node_groups = ["Array Plus"]
ng = bpy.data.node_groups["Array Plus"]
ids = {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}

me = bpy.data.meshes.new("bar"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=0.1); bm.to_mesh(me); bm.free()
bar = bpy.data.objects.new("Bar", me); bpy.context.scene.collection.objects.link(bar)
bpy.ops.curve.primitive_bezier_circle_add(radius=1.0); circ = bpy.context.object
bp = circ.data.splines[0].bezier_points[1]
bp.co.z += 0.4; bp.handle_left.z += 0.4; bp.handle_right.z += 0.4  # lift one point (like your front point)

mod = bar.modifiers.new("A", "NODES"); mod.node_group = ng
P = mod.properties.inputs
getattr(P, ids["Curve Object"]).value = circ
def setin(**kw):
    for k, v in kw.items(): getattr(P, ids[k.replace("_", " ")]).value = v

def copies():
    bpy.context.view_layer.update()
    ev = bar.evaluated_get(bpy.context.evaluated_depsgraph_get()); m = ev.to_mesh()
    vs = [v.co.copy() for v in m.vertices]; ev.to_mesh_clear()
    return [vs[i:i + 8] for i in range(0, len(vs), 8)]

def stats(cs):
    zc = [round((sum(c, Vector()) / 8).z, 4) for c in cs]
    tilt = max(round(max(v.z for v in c) - min(v.z for v in c), 4) for c in cs)  # 0.1 = perfectly level cube
    return {"copies": len(cs), "center_z": sorted(set(zc)), "max_z_span": tilt}

base = dict(Shape="Curve", Count_Method="Count & Spacing", Count=12, Gap=0.3, Realize_Instances=True,
            Relative_Space=True, Lock_X=False, Lock_Y=False, Lock_Z=False)
R = {}
circ.location = (0, 0, 0.5)
setin(**base); R["no_lock"] = stats(copies())
setin(**{**base, "Lock_Z": True}); R["lock_z"] = stats(copies())
setin(**{**base, "Count_Method": "Count", "Lock_Z": True}); R["count_mode_lock_z"] = stats(copies())
setin(**{**base, "Count_Method": "Distance", "Distance": 0.5, "Lock_Z": True}); R["distance_mode_lock_z"] = stats(copies())
setin(**{**base, "Lock_Z": True, "Relative_Space": False}); R["relative_off_lock_z"] = stats(copies())
circ.location = (0, 0, 0.8); setin(**{**base, "Lock_Z": True}); R["curve_moved_to_0.8_lock_z"] = stats(copies())
circ.location = (0.25, 0, 0); setin(**{**base, "Lock_X": True})
R["lock_x_center_x"] = sorted({round((sum(c, Vector()) / 8).x, 4) for c in copies()})
print("JSON>>" + json.dumps(R))
