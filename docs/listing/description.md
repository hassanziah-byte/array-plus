Blender's Geometry Nodes **Array** modifier with exact control along curves.

The built-in Array always spreads copies over the **whole** curve. Array Plus lets you say *"10 copies, 1 mm apart, and stop there"*, and keeps everything the stock Array does (Line, Circle, Curve and Transform shapes, Randomize, Merge, gizmos).

### Count & Spacing
Exactly **N copies** with an exact **Gap** between them, starting at a **Start Offset**.
- Gap measured edge-to-edge (object length added automatically) or center-to-center
- Copies only cover as much of the curve as they need
- Closed curves wrap around; open curves drop copies past the end

### Copy Transform
Per-copy **Offset, Rotation and Scale** in X/Y/Z:
- **Accumulate on:** each copy adds the value again, for spirals, twists, rising stairs and tapering
- **Accumulate off:** every copy gets the same adjustment
- The gap stays exact when copies are scaled

### Lock X / Y / Z
Copies ignore curve points moved along a locked axis. They stay level and don't tilt up or down slopes. Works with Count, Distance and Count & Spacing.

### How to use
**Add Modifier → Generate → Array Plus**, set **Shape: Curve**, pick a curve, then **Count Method: Count & Spacing**.

Tip: use an un-beveled curve as the path (a beveled curve evaluates to a mesh).

Source, docs and issue tracker: https://github.com/hassanziah-byte/array-plus
