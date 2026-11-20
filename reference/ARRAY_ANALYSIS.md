# Blender 5.3 Geometry Nodes "Array" Modifier — Analysis

Source: `Blender/5.3/datafiles/assets/nodes/geometry_nodes_essentials.blend` → node group `Array`
This is the analysis of the *stock* group that Array Plus is built on. Several of the "weak spots" listed at the end are what Array Plus addresses.

## Size
- **Array**: 365 nodes, 497 links, 16 frames (70 reroutes, 51 Group Input nodes)
- **Randomize Transforms** (nested): 39 nodes; the only sub-group used
- Flags: `is_modifier=True`, `is_tool=False`

## Pipeline

```
Geometry ─┬─ Line ──────┐
          ├─ Circle ────┤
          ├─ Curve ─────┼─ Index Switch (Shape) ─ Capture(random, index) ─ Store "instance_random" (vec, INSTANCE)
          └─ Transform ─┘                                                ─ Store "instance_index"  (int, INSTANCE)
                                                                          ─ [Randomize Transforms] (opt)
                                                                          ─ Realize ─ [Merge by Distance] (opt) ─ Output
```
Each shape branch is joined with its gizmos (Linear/Dial/Transform), so gizmos are live per mode.

## Interface (modifier panel)

| Input | Type | Default | Used by |
|---|---|---|---|
| Shape | Menu: Line / Circle / Curve / Transform | Line | top-level switch |
| Count Method | Menu: Count / Distance | Count | Curve only |
| Count | Int 1–10000 | 3 | all shapes |
| Distance | Float ≥0.01 | 1.0 | Curve (Distance mode) |
| Angular Distance | Float | 45° | Circle |
| Per Curve | Bool | True | Curve (multi-spline count) |
| Offset Method | Menu: Relative / Offset / Endpoint | Relative | Line |
| Transform Reference | Menu: Inputs / Object | Inputs | Transform |
| Translation / Offset | Vector | (1,0,0) | Line / Transform |
| Rotation | Rotation | 0 | Line, Transform |
| Scale | Vector | (1,1,1) | Line, Transform |
| Central Axis | Menu X/Y/Z | Z | Circle |
| Circle Segment | Menu Full / Arc | Full | Circle |
| Sweep Angle | Float 0–360° | 180° | Circle (Arc) |
| Radius | Float | 0 | Circle |
| Transform Object / Curve Object | Object | — | Transform / Curve |
| Relative Space | Bool | True | Curve, Transform (Object) |
| Realize Instances | Bool | True | output |
| **Panel: Align Rotation** (toggle) | + Local Rotation | on | Circle, Curve |
| **Panel: Randomize** (toggle) | Offset, Rotation, Scale Axes(Uniform/Per-axis), Scale, Flipping, Exclude First/Last, Seed | off | post-process |
| **Panel: Merge** (toggle) | Merge Distance 0.001 | off | needs Realize |

## How each shape works
- **Line** — `Points(Count)` → Set Position (index × offset; offset comes from Relative=bbox size × Offset, Offset=raw, Endpoint=total/(count-1)) → Instance on Points with per-index **Mix**ed rotation/scale (linear interpolation of Rotation/Scale over index — not compounding).
- **Circle** — Points on circle built from index × angle (Full = 360/count, Arc = sweep/(count-1), or Angular Distance), Central Axis via Index Switch of transforms; optional align rotation. Warns on invalid count.
- **Curve** — Object Info(Curve Object). Count mode: Sample Curve by factor per spline (Per Curve toggle, Single-Curve fallback). Distance mode: Resample-by-length style sampling + cyclic handling; rotation from tangent/normal (Axes to Rotation). Stable IDs via Hash + Set ID. Warnings: "Invalid Distance", "No Curve Selected".
- **Transform** — `Points(Count)` → Instance on Points → **Accumulate Field** of a Combine Transform (true compounding, like the classic Array modifier's object offset). Object reference mode reads Transform Object's matrix, optionally relative to self.

## Outputs worth knowing
- Instance attributes `instance_index` (int) and `instance_random` (vector) are stored on every copy → usable in shaders even after realize.
- Randomization runs on instances (Randomize Transforms sub-group, local space) before realize.

## Observations / weak spots (customization targets)
1. **No caps** (start/end geometry) — classic Array has them; GN version doesn't.
2. **No Fit Length** for Line (only Count; Distance exists only for Curve).
3. **Line rotation/scale are interpolated, not accumulated** → spiral/stair effects need Transform mode.
4. **No grid / multi-axis** (2D/3D arrays need stacked modifiers).
5. **No per-copy material/collection variation** — only one Geometry input; no "pick from collection" by index/random.
6. **No selection/skip pattern** (e.g., every Nth, random delete %).
7. Merge is plain Merge-by-Distance on everything — no "merge first & last" for cyclic loops (classic Array option).
8. Graph is heavy (51 Group Input nodes, 70 reroutes) — hard to edit by hand; easier to build a custom version programmatically.
