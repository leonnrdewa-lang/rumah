# Hanoman Duta — Art & Animation v2 (target: "90% Hades")

User feedback on v1: models look boxy/low-poly, walk looks like "4 legs" (arms swinging like
legs from the top camera), attacks lack good animation, no audible sound. v2 fixes this.

## Look we are matching (Supergiant's Hades / Hades II)

* **Silhouettes first.** Heroic, exaggerated proportions: big hands/feet/weapons, small waists,
  broad shoulders, dynamic S-curves. Smooth organic surfaces (subdivision), never visible boxes
  or faceting on characters. Hard-surface props are bevelled and chunky, slightly irregular.
* **Painted shading.** Every surface reads as hand painted: dark ink lines around forms, deep
  crevices, light catching top edges, colour shifts (warmer in light, cooler/purpler in shadow),
  subtle brush texture. We get this from: (1) baked *vertex colours* (ambient occlusion +
  "dirty"/curvature: crevices dark, convex edges light), (2) the game's toon shader (bands,
  rim light, hatching in shadow, brush noise), (3) ink outlines.
* **Palette.** Dark, rich environments (deep teal, violet, near-black) with saturated glowing
  accents (gold, teal, magenta, fire orange). Characters brighter and more saturated than the
  background so they pop.
* **Detail density.** Environments are dense: floors with carved slabs, cracks, rubble,
  roots, glowing plants; rooms framed by architecture and foliage on all sides.

## Technical contract (Blender 4.5 via `python3 script.py`, output GLB)

### Characters / enemies / bosses (skinned + animated)
* One GLB per character: `hanoman/game/assets/models/<id>.glb`, containing ONE armature named
  `<id>_rig` with a skinned mesh (or a few skinned meshes) and **all animation clips as separate
  actions** (export with `export_animation_mode='ACTIONS'`, `export_force_sampling=True`,
  `export_def_bones=True`, `export_vertex_color='ACTIVE'` (4.2+ option name may be
  `export_vertex_color`; check), `export_apply=True`, `export_yup=True`).
* Units metres, feet on z=0, **front faces -Y** in Blender (becomes +Z in Godot). Animations are
  **in place** (no root translation except vertical bob / small lunges that return to origin).
* Mesh must be smooth: build with Skin modifier / metaballs / sculpt-like displacement / curves,
  apply a Subdivision Surface (level 1-2) before export, shade smooth (auto smooth for hard
  parts), then decimate to budget if needed. Budgets: hero 12k tris, NPC 10k, small enemy 6k,
  big enemy 10k, boss 16k.
* **Vertex colours** (colour attribute named `Col`, per-corner or per-point, sRGB) = baked AO ×
  curvature ("Dirty Vertex Colors" or Cycles AO bake to vertex colours): range ~0.35 (deep
  crevice) to 1.15 max stored as ≤1.0 (store `0.5 + 0.5*shade`, game decodes `shade = 2*c-1`;
  i.e. 0.5 means neutral). Material base colours stay flat per part (skin, fur, gold, cloth).
* Materials `M_<Surface>`; emissive ones `M_Glow<Name>` (base colour = glow colour).
  ≤ 6 materials per character.
* Bone names: humanoids use `hips, spine, chest, neck, head, shoulder.L/R, upper_arm.L/R,
  forearm.L/R, hand.L/R, thigh.L/R, shin.L/R, foot.L/R` (+ `tail_1..n`, `jaw`, `weapon`).
  A `weapon` bone parented to `hand.R` carries the weapon mesh (rigid-weighted).
* Clip names (exact, lowercase). Durations at 30 fps.
  * **hero `hanoman`**: `idle` (loop, 2 s, breathing, weapon ready), `run` (loop, 0.6 s —
    upright heroic run like Zagreus/Melinoë: torso leaning forward, arms bent ~90° with small
    counter-swing, weapon held back in right hand, tail streaming, NO arms swinging like legs),
    `attack_1` (0.30 s: horizontal right-to-left gada sweep with windup 0.08 s, hit frame at
    0.12 s, follow-through), `attack_2` (0.30 s: backhand left-to-right sweep), `attack_3`
    (0.50 s: jump + overhead two-hand slam, hit at 0.24 s), `special` (0.30 s: left-hand claw
    slash throwing a wind blade forward), `cast` (0.45 s: both arms raised then slammed down),
    `dash` (0.20 s: low forward lunge/roll pose), `hurt` (0.25 s), `die` (1.0 s, non-loop,
    ends lying down), `talk` (loop 2 s, NPC-style gesture for hub).
  * **NPCs `rama`, `jembawan`, `sugriwa`**: `idle` (loop), `talk` (loop), `walk` (loop).
  * **humanoid enemies `wil`, `cakil`, `buto_ijo`, `kijang_raksasa`**: `idle`, `walk` (loop),
    `windup` (hold pose, ≥0.4 s loopable), `attack` (strike, 0.3–0.5 s, hit ~40%), `hurt`,
    `die`. `cakil` also `dash_attack` (lunge with keris). `buto_ijo` `attack` = overhead slam.
  * **`banaspati`** (flaming skull): `idle` (loop float), `attack` (jaw open spit), `hurt`, `die`.
  * **`yuyu`** (giant crab): `idle`, `walk` (loop, sideways scuttle, 6 legs), `windup`,
    `attack` (double claw snap), `guard` (claws in front), `hurt`, `die`.
  * **`kijang`** (golden deer): `idle`, `run` (loop gallop), `windup` (rear up), `charge`
    (loop head-down charge), `hurt`, `die`.
  * **`sura`** (shark, ~5.5 m): `idle` (loop swim sway), `swim` (loop fast), `bite`,
    `rear` (rise half out of water, roar), `dive`, `hurt`, `die`.
  * **`baya`** (crocodile, ~6 m): `idle`, `walk` (loop), `bite`, `spin` (tail sweep 360°
    windup+strike, 0.6 s), `roll_charge` (loop), `rear` (roar), `hurt`, `die`.

### Static props / environment
* Same axis rules; single root; meshes joined per material; bevels on every hard edge
  (width 0.03–0.1, 2 segments); organic props (rocks, trees, roots, foliage) sculpted-looking:
  displaced subdivided meshes, not primitives. **Vertex colour AO/dirt** as above on every prop.
* Painted tiling textures (floors/walls) are generated in Python (numpy/Pillow) in
  `hanoman/tools/make_textures.py` style: hand-painted slabs with bevel highlight on top edges,
  dark ink outline around each slab, cracks, moss, carved kawung/parang motifs, brush strokes.

### Verification
Render every asset (Cycles, toon-ish) from the game camera (55° pitch, looking down) AND a
close-up, look at it, iterate until it reads as a Hades-quality painted asset. For animated
assets, render a contact sheet of 6–8 frames per clip and check the motion reads well from the
game camera (top-down 55°): limbs must read as arms vs legs, attacks must have clear windup,
smear and follow-through.
