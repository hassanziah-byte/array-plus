"""Render README images (Workbench) into docs/images.
Run: ./run_blender.sh tests/render_docs.py -- <array_plus.blend> <out_dir>
"""
import bpy, sys, math, os, bmesh
from mathutils import Vector, Euler

blend, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(blend) as (s, d):
        d.node_groups = ["Array Plus"]
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 1200, 700
    sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.85, 0.55, 0.25)
    sc.display.shading.show_cavity = True; sc.display.shading.show_shadows = True
    sc.world = bpy.data.worlds.new("w") if not sc.world else sc.world
    sc.display.shading.background_type = "VIEWPORT"
    sc.display.shading.background_color = (0.12, 0.12, 0.13)
    return sc


def block(lx, ly=0.012, lz=0.012):
    me = bpy.data.meshes.new("blk"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co.x *= lx; v.co.y *= ly; v.co.z *= lz
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Block", me); bpy.context.scene.collection.objects.link(o); return o


def curve_obj(circle_r=None):
    bpy.ops.curve.primitive_bezier_circle_add(radius=circle_r)
    c = bpy.context.object
    return c


def show_path(c):
    """Visible copy of the path (a beveled curve evaluates to a mesh, so the array must use the un-beveled one)."""
    d = c.copy(); d.data = c.data.copy(); d.data.bevel_depth = 0.0008
    bpy.context.scene.collection.objects.link(d)
    return d


def array(o, crv, **kw):
    ng = bpy.data.node_groups["Array Plus"]
    ids = {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}
    m = o.modifiers.new("Array Plus", "NODES"); m.node_group = ng
    P = m.properties.inputs
    getattr(P, ids["Curve Object"]).value = crv
    for k, v in {"Shape": "Curve", "Count Method": "Count & Spacing", **kw}.items():
        getattr(P, ids[k]).value = v


def cam(loc, rot_deg, ortho=None):
    c = bpy.data.cameras.new("cam")
    if ortho: c.type = "ORTHO"; c.ortho_scale = ortho
    o = bpy.data.objects.new("cam", c); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = Euler([math.radians(a) for a in rot_deg])
    bpy.context.scene.camera = o


def render(name):
    bpy.context.scene.render.filepath = os.path.join(out, name)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)


# 1. 10 copies, 1 mm gap, half circle
fresh(); R = 0.1; N = 10; L = (math.pi * R - 9 * 0.001) / N
c = curve_obj(R); b = block(L)
array(b, c, Count=N, Gap=0.001, **{"Start Offset": L / 2}); show_path(c)
cam((0, 0.045, 1), (0, 0, 0), ortho=0.26); render("count_spacing_half_circle.png")

# 2. Accumulate: rising, twisting, shrinking
fresh(); c = curve_obj(0.1); b = block(0.03)
array(b, c, Count=16, Gap=0.002, Accumulate=True, **{"Copy Offset": (0, 0.004, 0),
      "Copy Rotation": (math.radians(8), 0, 0), "Copy Scale": (0.95, 0.95, 0.95)}); show_path(c)
cam((0.33, -0.33, 0.27), (62, 0, 45), ortho=0.3); render("copy_transform_accumulate.png")

# 3. Lock Z: raised curve point, copies stay level (left = off, right = on)
fresh()
for x, lock in ((-0.13, False), (0.13, True)):
    c = curve_obj(0.1); c.location.x = x
    p = c.data.splines[0].bezier_points[1]
    for attr in ("co", "handle_left", "handle_right"):
        v = getattr(p, attr); v.z += 0.06
    b = block(0.03); b.location.x = x
    array(b, c, Count=9, Gap=0.003, **{"Lock Z": lock}); show_path(c)
cam((0, -0.55, 0.22), (72, 0, 0), ortho=0.5); render("axis_lock_z.png")
