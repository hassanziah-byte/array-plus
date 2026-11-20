"""Verify the "Count & Spacing" mode of Array Plus.
Run: ./run_blender.sh tests/verify_spacing.py -- <array_plus.blend>
"""
import bpy, sys, json, math, bmesh
from mathutils import Vector

_a = sys.argv[sys.argv.index("--") + 1:]
blend = _a[0]
GROUP = _a[1] if len(_a) > 1 else "Array Plus"
STOCK_ONLY = GROUP != "Array Plus"
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(blend) as (s, d):
    d.node_groups = [GROUP]
ng = bpy.data.node_groups[GROUP]
ids = {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}

BAR = 0.1  # bar length along X
def make_bar():
    me = bpy.data.meshes.new("bar"); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co.x *= BAR; v.co.y *= 0.02; v.co.z *= 0.02
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Bar", me); bpy.context.scene.collection.objects.link(o); return o

def make_circle(r=1.0):
    bpy.ops.curve.primitive_bezier_circle_add(radius=r, location=(0, 0, 0)); return bpy.context.object

def make_line(length=1.0):
    cu = bpy.data.curves.new("ln", "CURVE"); cu.dimensions = "3D"
    sp = cu.splines.new("POLY"); sp.points.add(1)
    sp.points[0].co = (0, 0, 0, 1); sp.points[1].co = (length, 0, 0, 1)
    o = bpy.data.objects.new("Line", cu); bpy.context.scene.collection.objects.link(o); return o

bar = make_bar(); circ = make_circle(); line = make_line(1.0)
mod = bar.modifiers.new("Array", "NODES"); mod.node_group = ng
P = mod.properties.inputs
def setin(**kw):
    for k, v in kw.items():
        getattr(P, ids[k.replace("_", " ")]).value = v

def copies():
    dg = bpy.context.evaluated_depsgraph_get()
    ev = bar.evaluated_get(dg).to_mesh()
    n = 8; cs = []
    for c in range(len(ev.vertices) // n):
        cs.append(sum((ev.vertices[c*n+i].co for i in range(n)), Vector()) / n)
    bar.evaluated_get(dg).to_mesh_clear()
    return cs

def warnings():
    return [w.message for w in mod.node_warnings] if hasattr(mod, "node_warnings") else []

def run(label, **kw):
    setin(**kw); bpy.context.view_layer.update()
    cs = copies()
    out = {"copies": len(cs), "warnings": warnings()}
    if kw.get("Curve_Object") is circ and cs:
        ang = sorted((math.atan2(c.y, c.x)) % (2*math.pi) for c in cs)
        ang_raw = [math.atan2(c.y, c.x) % (2*math.pi) for c in cs]
        d = [((ang_raw[i+1]-ang_raw[i]) % (2*math.pi)) for i in range(len(ang_raw)-1)]
        out["center_arc_step"] = sorted(set(round(x, 5) for x in d))
        out["arc_covered_deg"] = round(math.degrees(sum(d)), 2)
        # edge gap: distance from end of copy i to start of copy i+1 along tangent (chord approx)
    if kw.get("Curve_Object") is line and cs:
        out["x"] = [round(c.x, 4) for c in cs]
    R[label] = out

R = {}
base = dict(Shape="Curve", Curve_Object=circ, Realize_Instances=True, Count=10)
if not STOCK_ONLY and not __import__("os").environ.get("SKIP_NEW"):
  run("circle_count_spacing_gap1mm", **base, Count_Method="Count & Spacing", Gap=0.001, Edge_to_Edge=True, Start_Offset=0.0)
  run("circle_center_to_center_0.2", **base, Count_Method="Count & Spacing", Gap=0.2, Edge_to_Edge=False)
  run("circle_wrap_count40", **{**base, "Count": 40}, Count_Method="Count & Spacing", Gap=0.1, Edge_to_Edge=True)
  run("line_open_extends_past_end", Shape="Curve", Curve_Object=line, Realize_Instances=True, Count=20,
      Count_Method="Count & Spacing", Gap=0.0, Edge_to_Edge=True, Start_Offset=0.05)
# bent open curve: (0,0)->(1,0)->(1,1). Past the end copies continue along +Y; negative start goes along -X
cu2 = bpy.data.curves.new("bent", "CURVE"); cu2.dimensions = "3D"
sp2 = cu2.splines.new("POLY"); sp2.points.add(2)
for i, co in enumerate([(0, 0, 0, 1), (1, 0, 0, 1), (1, 1, 0, 1)]): sp2.points[i].co = co
bent = bpy.data.objects.new("Bent", cu2); bpy.context.scene.collection.objects.link(bent)
if not STOCK_ONLY:
  setin(Shape="Curve", Curve_Object=bent, Realize_Instances=True, Count=4, Count_Method="Count & Spacing",
        Gap=0.4, Edge_to_Edge=True, Start_Offset=1.7); bpy.context.view_layer.update()
  R["bent_past_end_xy"] = [[round(c.x, 3), round(c.y, 3)] for c in copies()]
  setin(Start_Offset=-1.0, Count=2); bpy.context.view_layer.update()
  R["bent_before_start_xy"] = [[round(c.x, 3), round(c.y, 3)] for c in copies()]
run("stock_count_mode", **base, Count_Method="Count")
run("stock_distance_mode", **base, Count_Method="Distance", Distance=0.5)

# input visibility per mode
vis = {}
for m in (("Count", "Distance") if STOCK_ONLY else ("Count", "Distance", "Count & Spacing")):
    setin(Count_Method=m); bpy.context.view_layer.update()
    try:
        vis[m] = {k: bool(mod.is_input_used(ids[k])) if callable(getattr(mod, "is_input_used", None)) else None
                  for k in ("Count", "Distance", "Gap", "Edge to Edge", "Start Offset", "Per Curve") if k in ids}
    except Exception as e:
        vis[m] = str(e)
R["input_used"] = vis
print("JSON>>" + json.dumps(R))
