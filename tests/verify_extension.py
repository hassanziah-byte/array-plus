"""Install the packaged extension zip into the isolated profile and use it end to end."""
import bpy, sys, json, addon_utils
zp = sys.argv[sys.argv.index("--") + 1]
R = {}
R["install"] = list(bpy.ops.extensions.package_install_files(filepath=zp, repo="user_default", enable_on_install=True))
R["enabled"] = [m for m in bpy.context.preferences.addons.keys() if "array_plus" in m]
R["menu_exists"] = hasattr(bpy.types, "OBJECT_MT_modifier_add_generate")
bpy.ops.wm.read_factory_settings(use_empty=False) if False else None
bpy.ops.mesh.primitive_cube_add(size=0.1)
ob = bpy.context.object
R["op"] = list(bpy.ops.object.add_array_plus())
R["modifier"] = [(m.name, m.type, m.node_group.name if m.node_group else None) for m in ob.modifiers]
ng = bpy.data.node_groups["Array Plus"]
ids = {i.name: i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}
P = ob.modifiers[-1].properties.inputs
bpy.ops.curve.primitive_bezier_circle_add(radius=1.0); circ = bpy.context.object
getattr(P, ids["Shape"]).value = "Curve"; getattr(P, ids["Curve Object"]).value = circ
getattr(P, ids["Count Method"]).value = "Count & Spacing"; getattr(P, ids["Count"]).value = 10
getattr(P, ids["Gap"]).value = 0.001
bpy.context.view_layer.update()
ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
R["verts"] = len(ev.vertices); R["copies"] = len(ev.vertices) // 8
R["count_method_items"] = [e.identifier for e in getattr(P, ids["Count Method"]).bl_rna.properties["value"].enum_items]
print("JSON>>" + json.dumps(R))
