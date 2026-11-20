"""Array Plus: Blender's Geometry Nodes Array with extra curve controls.

- Count & Spacing: exact number of copies with an exact gap along a curve
- Copy Transform: per-copy offset / rotation / scale (fixed or accumulated)
- Lock X/Y/Z: copies ignore curve points moved along a locked axis

Adds Object > Add Modifier > Generate > "Array Plus".
The node group is appended from the bundled array_plus.blend (older copies in a file are upgraded in place).
"""
import bpy
import os

GROUP = "Array Plus"
BLEND = os.path.join(os.path.dirname(__file__), "array_plus.blend")


GROUP_VERSION = 5  # must match build_array_plus.GROUP_VERSION


def get_group():
    """Return the file's Array Plus group, appending (or upgrading an older copy) as needed.
    An upgrade remaps every existing modifier to the new group; their input values are kept by socket identifier."""
    old = bpy.data.node_groups.get(GROUP)
    if old and not old.library and old.get("array_plus_version", 1) >= GROUP_VERSION:
        return old
    with bpy.data.libraries.load(BLEND, link=False) as (src, dst):
        dst.node_groups = [GROUP]
    new = dst.node_groups[0]
    if old and not old.library:
        nested_old = {n.node_tree for n in old.nodes if getattr(n, "node_tree", None)}
        old.user_remap(new)
        bpy.data.node_groups.remove(old)
        new.name = GROUP
        # drop the old version's sub-groups if nothing else uses them, and give the new ones their clean names
        for g in nested_old:
            if g.users - int(g.use_fake_user) == 0:
                base = g.name
                bpy.data.node_groups.remove(g)
                for n in new.nodes:
                    t = getattr(n, "node_tree", None)
                    if t and t.name.rsplit(".", 1)[0] == base and base not in bpy.data.node_groups:
                        t.name = base
    return new


class OBJECT_OT_add_array_plus(bpy.types.Operator):
    """Add the Array Plus geometry nodes modifier"""
    bl_idname = "object.add_array_plus"
    bl_label = "Array Plus"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type in {"MESH", "CURVE", "CURVES", "POINTCLOUD", "FONT", "GREASEPENCIL"}

    def execute(self, context):
        ng = get_group()
        targets = [o for o in context.selected_objects if o.type == context.object.type] or [context.object]
        for ob in targets:
            mod = ob.modifiers.new(GROUP, "NODES")
            mod.node_group = ng
            ob.modifiers.active = mod
        return {"FINISHED"}


def menu_func(self, context):
    self.layout.operator(OBJECT_OT_add_array_plus.bl_idname, icon="MOD_ARRAY")


MENUS = ("OBJECT_MT_modifier_add_generate",)


def register():
    bpy.utils.register_class(OBJECT_OT_add_array_plus)
    for m in MENUS:
        menu = getattr(bpy.types, m, None)
        if menu:
            menu.append(menu_func)


def unregister():
    for m in MENUS:
        menu = getattr(bpy.types, m, None)
        if menu:
            menu.remove(menu_func)
    bpy.utils.unregister_class(OBJECT_OT_add_array_plus)
