"""Verify Copy Transform (Accumulate / Copy Offset / Copy Rotation / Copy Scale) in Count & Spacing.
Run: ./run_blender.sh tests/verify_copy_transform.py -- <array_plus.blend>
"""
import bpy, sys, json, math, bmesh
from mathutils import Vector

blend = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(blend) as (s, d):
    d.node_groups = ["Array Plus"]
ng = bpy.data.node_groups["Array Plus"]
ids = {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}

me = bpy.data.meshes.new("bar"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts: v.co.x *= 0.1; v.co.y *= 0.02; v.co.z *= 0.02
bm.to_mesh(me); bm.free()
bar = bpy.data.objects.new("Bar", me); bpy.context.scene.collection.objects.link(bar)
orig = [v.co.copy() for v in me.vertices]

cu = bpy.data.curves.new("ln", "CURVE"); cu.dimensions = "3D"
sp = cu.splines.new("POLY"); sp.points.add(1)
sp.points[0].co = (0, 0, 0, 1); sp.points[1].co = (5, 0, 0, 1)
line = bpy.data.objects.new("Line", cu); bpy.context.scene.collection.objects.link(line)

mod = bar.modifiers.new("A", "NODES"); mod.node_group = ng
P = mod.properties.inputs
DEFAULTS = dict(Shape="Curve", Count_Method="Count & Spacing", Count=5, Gap=0.01, Edge_to_Edge=True, Start_Offset=0.5,
                Realize_Instances=True, Align_Rotation=False, Accumulate=True,
                Copy_Offset=(0, 0, 0), Copy_Rotation=(0, 0, 0), Copy_Scale=(1, 1, 1))

def setup(**kw):
    getattr(P, ids["Curve Object"]).value = line
    for k, v in {**DEFAULTS, **kw}.items():
        getattr(P, ids[k.replace("_", " ")]).value = v
    bpy.context.view_layer.update()
    ev = bar.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh(); vs = [v.co.copy() for v in m.vertices]; ev.to_mesh_clear()
    return [vs[i:i + 8] for i in range(0, len(vs), 8)]

def ctr(c): return sum(c, Vector()) / 8
def r(x, n=4): return round(x, n)
R = {}

# 1. fixed offset, accumulate off -> every copy shifted by the same Z
cs = setup(Accumulate=False, Copy_Offset=(0, 0, 0.05))
R["fixed_offset_z"] = [r(ctr(c).z) for c in cs]
# 2. accumulated offset -> z = 0.05 * i
cs = setup(Accumulate=True, Copy_Offset=(0, 0, 0.05))
R["accum_offset_z"] = [r(ctr(c).z) for c in cs]
# 3. accumulated rotation Z 10deg -> yaw = 10*i
def yaw(c): d = c[4] - c[0] if (c[4] - c[0]).length > 1e-6 else c[1] - c[0]; return d
o_dir = (orig[4] - orig[0]) if (orig[4] - orig[0]).length > 1e-6 else (orig[1] - orig[0])
def ang(c):
    d = yaw(c); return r(math.degrees(math.atan2(d.y, d.x) - math.atan2(o_dir.y, o_dir.x)) % 360, 2)
cs = setup(Accumulate=True, Copy_Rotation=(0, 0, math.radians(10)))
R["accum_rot_z_deg"] = [ang(c) for c in cs]
cs = setup(Accumulate=False, Copy_Rotation=(0, 0, math.radians(10)))
R["fixed_rot_z_deg"] = [ang(c) for c in cs]
# 4. accumulated scale X 1.5 with edge-to-edge gap 0.01 -> lengths 0.1*1.5^i, edge gaps all 0.01
def spans(cs):
    sp = [(min(v.x for v in c), max(v.x for v in c)) for c in cs]
    return [r(b - a) for a, b in sp], [r(sp[i + 1][0] - sp[i][1]) for i in range(len(sp) - 1)]
cs = setup(Accumulate=True, Copy_Scale=(1.5, 1, 1))
R["accum_scale_len"], R["accum_scale_gaps"] = spans(cs)
cs = setup(Accumulate=False, Copy_Scale=(2, 1, 1))
R["fixed_scale_len"], R["fixed_scale_gaps"] = spans(cs)
# 5. baseline unchanged (no copy transform): lengths 0.1, gaps 0.01
cs = setup()
R["baseline_len"], R["baseline_gaps"] = spans(cs)
# 6. aligned: offset Y is sideways relative to curve (curve along +X -> Y offset stays perpendicular)
cs = setup(Align_Rotation=True, Accumulate=False, Copy_Offset=(0, 0.05, 0))
R["aligned_offset_y_ctr"] = [[r(ctr(c).y), r(ctr(c).z)] for c in cs][:2]
# 7. visibility: copy-transform inputs used only in Count & Spacing
vis = {}
for m in ("Count", "Count & Spacing"):
    getattr(P, ids["Count Method"]).value = m; bpy.context.view_layer.update()
    vis[m] = {k: bool(mod.is_input_used(ids[k])) for k in ("Accumulate", "Copy Offset", "Copy Rotation", "Copy Scale")}
R["input_used"] = vis
print("JSON>>" + json.dumps(R))
