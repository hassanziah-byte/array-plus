"""Upgrade path: a modifier using an older Array Plus group keeps its values (incl. menus) after get_group().
Run: ./run_blender.sh tests/verify_upgrade.py -- <old_group.blend> <extension_dir>
"""
import bpy, sys, json, importlib.util, os
a = sys.argv[sys.argv.index("--") + 1:]
old_blend, ext_dir = a
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(old_blend) as (s, d):
    d.node_groups = ["Array Plus"]
old = bpy.data.node_groups["Array Plus"]
if "array_plus_version" in old: del old["array_plus_version"]  # simulate v1

bpy.ops.mesh.primitive_cube_add(size=0.1); ob = bpy.context.object
bpy.ops.curve.primitive_bezier_circle_add(radius=1); circ = bpy.context.object
md = ob.modifiers.new("Array Plus", "NODES"); md.node_group = old
def ids(ng): return {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}
I = ids(old); P = md.properties.inputs
vals = {"Shape": "Curve", "Count Method": "Count & Spacing", "Count": 7, "Gap": 0.003, "Start Offset": 0.02}
for k, v in vals.items(): getattr(P, I[k]).value = v
getattr(P, I["Curve Object"]).value = circ

spec = importlib.util.spec_from_file_location("ext", os.path.join(ext_dir, "__init__.py"))
ext = importlib.util.module_from_spec(spec); spec.loader.exec_module(ext)
new = ext.get_group()
I2 = ids(new); P = md.properties.inputs
after = {k: getattr(P, I2[k]).value for k in vals}
print("JSON>>" + json.dumps({"before": vals, "after": after, "version": md.node_group.get("array_plus_version"),
                             "groups": [g.name for g in bpy.data.node_groups]}))
