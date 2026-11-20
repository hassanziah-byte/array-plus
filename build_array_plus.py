"""Build "Array Plus" by patching Blender's stock Geometry Nodes "Array" group.

Adds to the Curve shape:
  - Count Method "Count & Spacing": exactly `Count` copies, `Gap` apart, from `Start Offset`
  - "Copy Transform" panel: per-copy offset / rotation / scale, fixed or accumulated
  - Lock X/Y/Z: flatten the curve on locked axes so copies ignore points moved along them

Run headless (use run_blender.sh so your real Blender profile is untouched):
  ./run_blender.sh build_array_plus.py -- [<source.blend>] <out.blend>
<source.blend> defaults to the running Blender's datafiles/assets/nodes/geometry_nodes_essentials.blend.
"""
import bpy, sys, os

SRC_GROUP = "Array"
NEW_GROUP = "Array Plus"
MODE_NAME = "Count & Spacing"
GROUP_VERSION = 5  # bump on every node-group change (v1 Count & Spacing, v2 Copy Transform, v3 Location Lock, v4 per-point Axis Lock, v5 extend past curve end)


def redirect(ng, from_socket, new_from):
    """Move every link leaving `from_socket` to leave `new_from` instead.
    Target sockets are re-resolved after removal: removing a link can rebuild reroute sockets,
    which silently invalidates held socket references."""
    targets = [(l.to_node.name, l.to_socket.identifier) for l in ng.links if l.from_socket == from_socket]
    for l in [l for l in ng.links if l.from_socket == from_socket]:
        ng.links.remove(l)
    for node_name, ident in targets:
        to = next(s for s in ng.nodes[node_name].inputs if s.identifier == ident)
        ng.links.new(new_from, to)
        assert any(l.from_socket == new_from and l.to_node.name == node_name for l in ng.links), (node_name, ident)
    return len(targets)


def build(ng):
    nodes, links = ng.nodes, ng.links
    N = nodes.get

    # ---------------------------------------------------------------- interface
    iface = ng.interface
    items = {i.name: i for i in iface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"}
    dist_pos = items["Distance"].position

    def add_sock(name, stype, desc, default, subtype=None, mn=None, mx=None, pos=None):
        s = iface.new_socket(name, in_out="INPUT", socket_type=stype)
        s.description = desc
        if subtype: s.subtype = subtype
        s.default_value = default
        if mn is not None: s.min_value = mn
        if mx is not None: s.max_value = mx
        s.force_non_field = True
        iface.move(s, pos)
        return s

    s_gap = add_sock("Gap", "NodeSocketFloat",
                     "Space between copies along the curve (Count & Spacing)", 0.0, "DISTANCE", -10000.0, 10000.0, dist_pos + 1)
    s_edge = add_sock("Edge to Edge", "NodeSocketBool",
                      "Measure the gap between copy edges (adds the object's length). Off: gap is center-to-center distance",
                      True, pos=dist_pos + 2)
    s_start = add_sock("Start Offset", "NodeSocketFloat",
                       "Distance along the curve where the first copy is placed", 0.0, "DISTANCE", -10000.0, 10000.0, dist_pos + 3)

    # "Copy Transform" panel, placed before the stock "Align Rotation" panel
    first_panel = next(i for i in iface.items_tree if i.item_type == "PANEL" and i.parent.name == "")
    panel = iface.new_panel("Copy Transform", description="Per-copy offset, rotation and scale (Count & Spacing)",
                            default_closed=False)
    iface.move(panel, first_panel.position)

    def add_panel_sock(name, stype, desc, default, subtype=None):
        s = iface.new_socket(name, in_out="INPUT", socket_type=stype, parent=panel)
        s.description = desc
        if subtype: s.subtype = subtype
        s.default_value = default
        s.force_non_field = True
        return s

    add_panel_sock("Accumulate", "NodeSocketBool",
                   "On: each copy adds the values again (copy 3 gets 2x offset/rotation, scale squared); first copy unchanged. "
                   "Off: every copy gets the same offset/rotation/scale", True)
    add_panel_sock("Copy Offset", "NodeSocketVector",
                   "Offset along each copy's own axes: X = along the curve; on a flat curve Y = up out of the curve plane, Z = sideways (curve normal). World axes if Align Rotation is off",
                   (0.0, 0.0, 0.0), "TRANSLATION")
    add_panel_sock("Copy Rotation", "NodeSocketVector", "Rotation of each copy around its own axes", (0.0, 0.0, 0.0), "EULER")
    add_panel_sock("Copy Scale", "NodeSocketVector",
                   "Scale of each copy. With Edge to Edge, spacing follows each copy's scaled length (X)", (1.0, 1.0, 1.0), "XYZ")

    # Location Lock: right after "Relative Space" (all Curve count methods)
    rel_pos = next(i for i in iface.items_tree if i.item_type == "SOCKET" and i.name == "Relative Space").position
    for k, ax in enumerate("XYZ"):
        add_sock(f"Lock {ax}", "NodeSocketBool",
                 f"Flatten the curve on {ax}: copies ignore curve points moved along {ax} and stay level "
                 f"with the curve object's origin on that axis (no tilting up/down the slope)",
                 False, pos=rel_pos + 1 + k)

    # ---------------------------------------------------------------- menu item
    ms = N("Menu Switch.005")  # Count Method menu (INT: Count=0, Distance=1)
    item = ms.enum_items.new(MODE_NAME)
    item.description = "Fixed number of copies with a fixed gap; copies only cover part of the curve if they fit"
    ms.inputs[MODE_NAME].default_value = 2

    # Existing consumers read the INT output as an "is Distance" boolean. Re-route them to the menu's own
    # per-item boolean output for "Distance", so the new item doesn't read as Distance.
    out_dist = next(s for s in ms.outputs if s.type == "BOOLEAN" and s.name == "Distance")
    out_sp = next(s for s in ms.outputs if s.type == "BOOLEAN" and s.name == MODE_NAME)
    assert redirect(ng, ms.outputs["Output"], out_dist) >= 1

    class _Out:  # keeps the later `is_sp.outputs[0]` hookup unchanged
        outputs = [out_sp]
    is_sp = _Out

    # ---------------------------------------------------------------- new branch
    ox, oy = min(n.location.x for n in nodes) , min(n.location.y for n in nodes) - 600
    frame = nodes.new("NodeFrame"); frame.label = MODE_NAME; frame.name = "Frame Count Spacing"

    def nn(t, x, y, label=None, **props):
        n = nodes.new(t); n.location = (ox + x, oy + y); n.parent = frame
        if label: n.label = label
        for k, v in props.items(): setattr(n, k, v)
        return n

    gi = nn("NodeGroupInput", 0, 0)
    for s in gi.outputs: s.hide = not s.is_linked  # tidy
    def G(name):
        return next(s for s in gi.outputs if s.name == name)

    curve = N("Reroute.004").outputs[0]  # curve geometry after Relative Space + "No Curve" check

    def math(op, a, b=None, x=0, y=0, label=None, c=None):
        n = nn("ShaderNodeMath", x, y, label, operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: links.new(v, n.inputs[i])
        return n.outputs[0]

    def vscale(vec, fac, x, y, label):
        n = nn("ShaderNodeVectorMath", x, y, label, operation="SCALE")
        links.new(vec, n.inputs[0]); links.new(fac, n.inputs["Scale"])
        return n.outputs[0]

    def fswitch(cond, f_false, f_true, x, y, label=None, t="FLOAT"):
        n = nn("GeometryNodeSwitch", x, y, label, input_type=t)
        links.new(cond, n.inputs["Switch"])
        for key, v in (("False", f_false), ("True", f_true)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[key].default_value = v
            else: links.new(v, n.inputs[key])
        return n.outputs[0]

    # ---- per-copy factor: Accumulate ? index : 1   (and the previous copy's factor)
    idx = nn("GeometryNodeInputIndex", 300, -900).outputs[0]
    idx_prev = math("SUBTRACT", idx, 1.0, 500, -1000, "Index - 1")
    f = fswitch(G("Accumulate"), 1.0, idx, 700, -900, "Copy Factor")
    f_prev = fswitch(G("Accumulate"), 1.0, idx_prev, 700, -1050, "Prev Copy Factor")

    # ---- scale(f) = Copy Scale ^ f, per component
    sep_s = nn("ShaderNodeSeparateXYZ", 700, -1250); links.new(G("Copy Scale"), sep_s.inputs[0])
    def vpow(fac, x, y, label):
        comb = nn("ShaderNodeCombineXYZ", x + 200, y, label)
        for k, ax in enumerate("XYZ"):
            links.new(math("POWER", sep_s.outputs[ax], fac, x, y - 150 * k), comb.inputs[ax])
        return comb.outputs[0]
    scale_cur = vpow(f, 950, -1250, "Scale (this copy)")
    scale_prev = vpow(f_prev, 950, -1750, "Scale (prev copy)")

    # ---- object extent along the tangent axis (X after local rotation)
    rot_sw = nn("GeometryNodeSwitch", 300, -300, "Local Rot If Aligned", input_type="ROTATION")
    links.new(G("Align Rotation"), rot_sw.inputs["Switch"]); links.new(G("Local Rotation"), rot_sw.inputs["True"])
    xf = nn("GeometryNodeTransform", 550, -200)
    links.new(G("Geometry"), xf.inputs["Geometry"]); links.new(rot_sw.outputs[0], xf.inputs["Rotation"])
    bb = nn("GeometryNodeBoundBox", 800, -200)
    links.new(xf.outputs[0], bb.inputs["Geometry"])
    bmin = nn("ShaderNodeSeparateXYZ", 1000, -150, "Min"); links.new(bb.outputs["Min"], bmin.inputs[0])
    bmax = nn("ShaderNodeSeparateXYZ", 1000, -300, "Max"); links.new(bb.outputs["Max"], bmax.inputs[0])

    def extent(scale_vec, x, y, tag):
        sx = nn("ShaderNodeSeparateXYZ", x, y); links.new(scale_vec, sx.inputs[0])
        a = math("MULTIPLY", sx.outputs["X"], bmin.outputs["X"], x + 200, y)
        b = math("MULTIPLY", sx.outputs["X"], bmax.outputs["X"], x + 200, y - 150)
        return math("MINIMUM", a, b, x + 400, y, f"Lo {tag}"), math("MAXIMUM", a, b, x + 400, y - 150, f"Hi {tag}")
    lo_cur, _ = extent(scale_cur, 1300, -1250, "this")
    _, hi_prev = extent(scale_prev, 1300, -1750, "prev")

    # ---- step from previous copy: edge-to-edge = hi_prev - lo_cur + gap ; else gap. First copy: 0
    edge_step = math("ADD", math("SUBTRACT", hi_prev, lo_cur, 1900, -1400), G("Gap"), 2100, -1400, "Edge Step")
    step = fswitch(G("Edge to Edge"), G("Gap"), edge_step, 2300, -1300, "Step")
    is_first = nn("FunctionNodeCompare", 2300, -1500, "First Copy", data_type="INT", operation="EQUAL")
    links.new(idx, is_first.inputs["A"]); is_first.inputs["B"].default_value = 0
    step0 = fswitch(is_first.outputs[0], step, 0.0, 2500, -1300, "Step (0 for first)")
    acc = nn("GeometryNodeAccumulateField", 2700, -1300, data_type="FLOAT", domain="POINT")
    links.new(step0, acc.inputs["Value"])
    L_out = math("ADD", acc.outputs["Leading"], G("Start Offset"), 1850, -300, "Length Along Curve")

    total = nn("GeometryNodeCurveLength", 1600, -650)
    links.new(curve, total.inputs[0])
    cyc_in = nn("GeometryNodeInputSplineCyclic", 1600, -800)
    cyc = nn("GeometryNodeSampleIndex", 1850, -750, "First Spline Cyclic", data_type="BOOLEAN", domain="CURVE")
    links.new(curve, cyc.inputs["Geometry"]); links.new(cyc_in.outputs[0], cyc.inputs["Value"])

    # Closed curves wrap around. Open curves: copies past either end continue straight along the end tangent
    # (like the Curve modifier): sample at the clamped length, then push out by the overshoot.
    wrap = math("FLOORED_MODULO", L_out, total.outputs[0], 2100, -400, "Wrap")
    clamped = math("MINIMUM", math("MAXIMUM", L_out, 0.0, 1900, -500), total.outputs[0], 2100, -550, "Clamp To Curve")
    over = math("SUBTRACT", L_out, clamped, 2300, -550, "Overshoot")
    L_samp = fswitch(cyc.outputs[0], clamped, wrap, 2300, -300, "Sample Length")
    over_open = fswitch(cyc.outputs[0], over, 0.0, 2500, -550, "Overshoot (open only)")

    valid_node = nn("FunctionNodeInputBool", 2700, -600, "Valid (always)"); valid_node.boolean = True

    class _Valid:  # every copy is kept now (no dropping past the curve end)
        outputs = [valid_node.outputs[0]]
    valid = _Valid

    samp = nn("GeometryNodeSampleCurve", 2550, -250, mode="LENGTH", use_all_curves=True)
    links.new(curve, samp.inputs["Curves"]); links.new(L_samp, samp.inputs["Length"])
    tan_n = nn("ShaderNodeVectorMath", 2750, -400, "End Tangent", operation="NORMALIZE")
    links.new(samp.outputs["Tangent"], tan_n.inputs[0])
    ext = vscale(tan_n.outputs[0], over_open, 2950, -400, "Extension")
    pos_ext = nn("ShaderNodeVectorMath", 3100, -300, "Extended Position", operation="ADD")
    links.new(samp.outputs["Position"], pos_ext.inputs[0]); links.new(ext, pos_ext.inputs[1])

    pts = nn("GeometryNodePoints", 2550, 100)
    links.new(G("Count"), pts.inputs["Count"])
    cap = nn("GeometryNodeCaptureAttribute", 2800, 100, domain="POINT")
    links.new(pts.outputs[0], cap.inputs["Geometry"])
    for nm in ("Position", "Tangent", "Normal"):
        cap.capture_items.new("VECTOR", nm)
        links.new(pos_ext.outputs[0] if nm == "Position" else samp.outputs[nm], cap.inputs[nm])
    cap.capture_items.new("BOOLEAN", "Valid"); links.new(valid.outputs[0], cap.inputs["Valid"])

    a2r = nn("FunctionNodeAxesToRotation", 3050, -150, primary_axis="X", secondary_axis="Z")
    links.new(cap.outputs["Tangent"], a2r.inputs["Primary Axis"]); links.new(cap.outputs["Normal"], a2r.inputs["Secondary Axis"])

    # ---- offset in the curve frame (world axes if not aligned)
    fr = fswitch(G("Align Rotation"), None, a2r.outputs[0], 3250, -450, "Offset Frame", "ROTATION")
    off = vscale(G("Copy Offset"), f, 3050, -600, "Offset x Factor")
    rv = nn("FunctionNodeRotateVector", 3450, -500, "Offset In Frame")
    links.new(off, rv.inputs["Vector"]); links.new(fr, rv.inputs["Rotation"])

    setp = nn("GeometryNodeSetPosition", 3650, 100)
    links.new(cap.outputs["Geometry"], setp.inputs["Geometry"]); links.new(cap.outputs["Position"], setp.inputs["Position"])
    links.new(rv.outputs[0], setp.inputs["Offset"])

    # ---- rotation: curve frame -> Local Rotation -> per-copy rotation (all local)
    rr = nn("FunctionNodeRotateRotation", 3250, -150, rotation_space="LOCAL")
    links.new(a2r.outputs[0], rr.inputs["Rotation"]); links.new(G("Local Rotation"), rr.inputs["Rotate By"])
    rsw = fswitch(G("Align Rotation"), None, rr.outputs[0], 3450, -150, None, "ROTATION")
    eul = vscale(G("Copy Rotation"), f, 3250, -300, "Rotation x Factor")
    e2r = nn("FunctionNodeEulerToRotation", 3450, -300); links.new(eul, e2r.inputs[0])
    rfinal = nn("FunctionNodeRotateRotation", 3650, -150, "Copy Rotation", rotation_space="LOCAL")
    links.new(rsw, rfinal.inputs["Rotation"]); links.new(e2r.outputs[0], rfinal.inputs["Rotate By"])

    iop = nn("GeometryNodeInstanceOnPoints", 3900, 100)
    links.new(setp.outputs[0], iop.inputs["Points"]); links.new(cap.outputs["Valid"], iop.inputs["Selection"])
    links.new(G("Geometry"), iop.inputs["Instance"]); links.new(rfinal.outputs[0], iop.inputs["Rotation"])
    links.new(scale_cur, iop.inputs["Scale"])

    # ---------------------------------------------------------------- location lock (curve source, all curve modes)
    # Flatten the curve (points AND handles) onto the plane through the curve object's origin on locked axes:
    #   p' = scale(1 - mask) * (p - origin) + origin
    # origin = curve origin in the working space: its relative location (Relative Space on) or 0 (curve-local).
    rel_sw = N("Switch.006")      # Relative Space switch: True = Object Info (RELATIVE)
    oi_rel = N("Object Info.003")  # transform_space RELATIVE -> Location is relative to this object
    lx = rel_sw.location.x; ly = rel_sw.location.y - 400
    gi2 = nodes.new("NodeGroupInput"); gi2.location = (lx - 600, ly - 200)
    def G2(name): return next(s for s in gi2.outputs if s.name == name)
    mask = nodes.new("ShaderNodeCombineXYZ"); mask.location = (lx - 400, ly - 200); mask.label = "Lock Mask"
    for ax in "XYZ": links.new(G2(f"Lock {ax}"), mask.inputs[ax])
    keep = nodes.new("ShaderNodeVectorMath"); keep.operation = "SUBTRACT"; keep.location = (lx - 200, ly - 250)
    keep.inputs[0].default_value = (1.0, 1.0, 1.0); links.new(mask.outputs[0], keep.inputs[1]); keep.label = "Keep Axes"
    origin = nodes.new("GeometryNodeSwitch"); origin.input_type = "VECTOR"; origin.location = (lx - 200, ly - 50)
    origin.label = "Curve Origin"
    links.new(G2("Relative Space"), origin.inputs["Switch"]); links.new(oi_rel.outputs["Location"], origin.inputs["True"])
    neg = nodes.new("ShaderNodeVectorMath"); neg.operation = "SCALE"; neg.location = (lx, ly - 50)
    links.new(origin.outputs[0], neg.inputs[0]); neg.inputs["Scale"].default_value = -1.0
    to_origin = nodes.new("GeometryNodeTransform"); to_origin.location = (lx + 200, ly); to_origin.label = "To Curve Origin"
    flat = nodes.new("GeometryNodeTransform"); flat.location = (lx + 400, ly); flat.label = "Axis Lock (Flatten)"
    assert redirect(ng, rel_sw.outputs[0], flat.outputs[0]) >= 1
    links.new(rel_sw.outputs[0], to_origin.inputs["Geometry"]); links.new(neg.outputs[0], to_origin.inputs["Translation"])
    links.new(to_origin.outputs[0], flat.inputs["Geometry"])
    links.new(keep.outputs[0], flat.inputs["Scale"]); links.new(origin.outputs[0], flat.inputs["Translation"])
    for s in gi2.outputs: s.hide = not s.is_linked

    # ---------------------------------------------------------------- hook into output
    sw9 = N("Switch.009")
    out_sw = nodes.new("GeometryNodeSwitch"); out_sw.input_type = "GEOMETRY"; out_sw.label = MODE_NAME
    out_sw.location = sw9.location + type(sw9.location)((220, 0))
    assert redirect(ng, sw9.outputs[0], out_sw.outputs[0]) >= 1
    links.new(sw9.outputs[0], out_sw.inputs["False"]); links.new(iop.outputs[0], out_sw.inputs["True"])
    links.new(is_sp.outputs[0], out_sw.inputs["Switch"])

    for s in gi.outputs: s.hide = not s.is_linked


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    if len(a) == 1:
        src = os.path.join(bpy.utils.system_resource("DATAFILES"), "assets", "nodes", "geometry_nodes_essentials.blend")
        out = a[0]
    else:
        src, out = a[0], a[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(src) as (s, d):
        d.node_groups = [SRC_GROUP]
    ng = bpy.data.node_groups[SRC_GROUP]
    ng.name = NEW_GROUP
    build(ng)
    ng["array_plus_version"] = GROUP_VERSION  # the add-on upgrades older copies found in a .blend

    # Clean, portable output: replace every group with a fresh copy (drops the appended-from link that
    # stores the source file's absolute path), clear the stock asset flag, and write ONLY the node groups
    # (no window/UI data, which embeds local user folders).
    groups = [ng] + sorted({n.node_tree for n in ng.nodes if getattr(n, "node_tree", None)}, key=lambda g: g.name)
    clean = []
    for g in groups:
        name = g.name
        c = g.copy()
        g.user_remap(c)
        bpy.data.node_groups.remove(g)
        c.name = name
        if c.asset_data:
            c.asset_clear()
        c.use_fake_user = True
        clean.append(c)
    if os.path.exists(out):
        os.remove(out)
    bpy.data.libraries.write(out, set(clean), fake_user=True, compress=True)
    print("BUILT", NEW_GROUP, "->", out, [c.name for c in clean])


if __name__ == "__main__":
    main()
