"""Render extensions.blender.org listing images: icon (256x256), featured (1920x1080), previews (1920x1080).
Run: ./run_blender.sh tests/render_listing.py -- <array_plus.blend> <out_dir>
"""
import bpy, sys, math, os, bmesh
from mathutils import Euler

blend, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)
ORANGE = (0.91, 0.49, 0.05)
BG = (0.009, 0.009, 0.011)  # linear (~#1a1a1d on screen)


def fresh(w, h, color=ORANGE):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(blend) as (s, d):
        d.node_groups = ["Array Plus"]
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sh = sc.display.shading
    sh.light = "STUDIO"; sh.color_type = "OBJECT"
    sh.show_cavity = True; sh.show_shadows = True
    sh.background_type = "VIEWPORT"; sh.background_color = BG
    sc.view_settings.view_transform = "Standard"
    w_ = bpy.data.worlds.new("bg"); w_.color = BG; sc.world = w_   # Workbench renders use the world color
    return sc


def block(lx, ly=0.012, lz=0.012, x=0.0):
    me = bpy.data.meshes.new("blk"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co.x *= lx; v.co.y *= ly; v.co.z *= lz
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Block", me); o.location.x = x; o.color = (*ORANGE, 1)
    bpy.context.scene.collection.objects.link(o); return o


def circle(r, x=0.0, lift=0.0, show=True):
    bpy.ops.curve.primitive_bezier_circle_add(radius=r, location=(x, 0, 0))
    c = bpy.context.object
    if lift:
        p = c.data.splines[0].bezier_points[1]
        for a in ("co", "handle_left", "handle_right"):
            v = getattr(p, a); v.z += lift
    if show:  # visible path copy (a beveled curve evaluates to a mesh, so the array uses the plain one)
        d = c.copy(); d.data = c.data.copy(); d.data.bevel_depth = 0.0009
        d.color = (0.5, 0.5, 0.53, 1); bpy.context.scene.collection.objects.link(d)
    return c


def array(o, crv, **kw):
    ng = bpy.data.node_groups["Array Plus"]
    ids = {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}
    m = o.modifiers.new("Array Plus", "NODES"); m.node_group = ng
    P = m.properties.inputs
    getattr(P, ids["Curve Object"]).value = crv
    for k, v in {"Shape": "Curve", "Count Method": "Count & Spacing", **kw}.items():
        getattr(P, ids[k]).value = v


def text(body, loc, size, color=(0.95, 0.95, 0.95)):
    cu = bpy.data.curves.new("t", "FONT"); cu.body = body; cu.size = size; cu.align_x = "CENTER"
    o = bpy.data.objects.new("t", cu); o.location = loc
    bpy.context.scene.collection.objects.link(o)
    o.color = (*color, 1)
    return o


def cam(loc, rot_deg, ortho):
    c = bpy.data.cameras.new("cam"); c.type = "ORTHO"; c.ortho_scale = ortho
    o = bpy.data.objects.new("cam", c); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = Euler([math.radians(a) for a in rot_deg])
    bpy.context.scene.camera = o


def render(name, fmt="JPEG"):
    sc = bpy.context.scene
    sc.render.image_settings.file_format = fmt
    if fmt == "JPEG": sc.render.image_settings.quality = 92
    sc.render.filepath = os.path.join(out, name)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)


def half_circle_scene(R=0.1, N=10, gap=0.001, x=0.0):
    L = (math.pi * R - (N - 1) * gap) / N
    c = circle(R, x=x); b = block(L, x=x)
    array(b, c, Count=N, Gap=gap, **{"Start Offset": L / 2})


def spiral_scene(x=0.0):
    c = circle(0.1, x=x); b = block(0.03, x=x)
    array(b, c, Count=16, Gap=0.002, Accumulate=True, **{"Copy Offset": (0, 0.004, 0),
          "Copy Rotation": (math.radians(8), 0, 0), "Copy Scale": (0.95, 0.95, 0.95)})


# ---- icon 256x256: top view arc of blocks
fresh(256, 256)
R = 0.1; N = 7; gap = 0.004; L = (math.pi * 1.25 * R - (N - 1) * gap) / N
c = circle(R, show=False); b = block(L, 0.03, 0.03)
array(b, c, Count=N, Gap=gap, **{"Start Offset": -0.6 * R})
cam((0, 0, 1), (0, 0, 0), ortho=0.26); render("icon.png", "PNG")

# ---- featured 1920x1080: title + half circle + spiral
fresh(1920, 1080)
half_circle_scene(x=-0.17)
spiral_scene(x=0.17)
text("Array Plus", (0, 0.185, 0), 0.05)
text("exact spacing  ·  copy transforms  ·  axis lock", (0, 0.152, 0), 0.017, (0.7, 0.7, 0.72))
cam((0, 0.06, 1), (0, 0, 0), ortho=0.66); render("featured.jpg")

# ---- previews 1920x1080
fresh(1920, 1080); half_circle_scene()
cam((0, 0.035, 1), (0, 0, 0), ortho=0.27); render("preview_1_count_spacing.jpg")

fresh(1920, 1080); spiral_scene()
cam((0.33, -0.33, 0.27), (62, 0, 45), ortho=0.3); render("preview_2_copy_transform.jpg")

fresh(1920, 1080)
for x, lock in ((-0.13, False), (0.13, True)):
    c = circle(0.1, x=x, lift=0.06); b = block(0.03, x=x)
    array(b, c, Count=9, Gap=0.003, **{"Lock Z": lock})
cam((0, -0.55, 0.22), (72, 0, 0), ortho=0.5); render("preview_3_axis_lock.jpg")
