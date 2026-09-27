# Sawit The Franchise — Blender asset style guide

All 3D assets are built by Python scripts that drive Blender 4.5 (`import bpy`,
installed as a pip module; run with `python3 blender/<script>.py`). No manual
Blender work, so every asset is reproducible.

## Look

Cozy stylised 3D in the vein of Animal Crossing / Coral Island, matched to the
reference screenshot in `art/reference/00_user_style_reference.png`:

* chunky, soft, slightly toy-like shapes; bevel every box edge (bevel width
  0.03–0.08 m, 2 segments) so edges catch the light;
* organic things (rocks, bushes, heads, fruit) are smooth-shaded, lightly
  irregular (jitter vertices a little), never perfect primitives;
* flat material colours only, no image textures; matte (roughness ≈ 0.9);
* warm, saturated-but-soft palette (see `PALETTE` in `common.py`, sampled from
  the Higgsfield reference images). Use palette keys; small deviations are fine.

## Technical rules

* 1 unit = 1 m, Z up. Object origin = ground centre (lowest point at z = 0).
* "Front" of characters and buildings (doors, faces) faces **-Y**.
  (glTF export converts this to +Z in Godot.)
* Each asset = one root Empty named after the asset, with meshes parented to it.
  Merge static meshes with `join()` where possible (fewer draw calls); keep ≤ 4
  materials per asset.
* Material names must be prefixed `M_` and describe the surface (`M_Roof`,
  `M_Wood`). Reserved names the game looks for:
  * `M_Frond` — palm leaves (the game fades these near the player);
  * `M_Glass` / `M_Lamp` — windows/lamps (lit at night).
* Poly budgets (triangles): mature palm ≤ 3000, building ≤ 4000,
  character ≤ 3000, small prop ≤ 600.
* Export with `export_glb(root, "<name>")` → `game/assets/models/<name>.glb`.
* Check your work: `render_preview(root, "<name>")` writes
  `blender/previews/<name>.png`; open it with the Read tool and iterate until
  it looks good from the game camera (~50–60° pitch, top-down-ish).
* Icons for UI: `render_icon(root, "icon_<name>")` → transparent 128 px PNG in
  `game/assets/icons/`.

## Scale references

* Characters are chibi and about 1.1 m tall (head ≈ 0.5 m diameter).
* Doors ≈ 1.5 m tall, 0.9 m wide. A one-room village house ≈ 5 × 4 m footprint.
* Palm planting grid is 3.2 m; a mature oil palm is ≈ 5 m tall with a crown
  ≈ 5.5 m across.
