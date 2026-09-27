# Sawit The Franchise — Art direction v2 (visual overhaul)

The v1 build looked sparse (flat grass, thin palms, brown soil discs) and the
characters moved stiffly (rigid limbs rotated in code). v2 must look like the
target screenshot the user supplied:

**`art/reference/07_target_gameplay.png`** — read it before doing anything.

What makes that image work, and what every part of v2 must deliver:

1. **Lush, layered vegetation everywhere.** The ground is almost never bare:
   ferns, broad-leaf shrubs, taro/keladi, grass clumps, tiny white/yellow
   flowers, fallen palm fronds, rocks with moss. Bare dirt appears only on roads
   and paths, which have soft grassy edges.
2. **Big, full oil palms.** Thick rough trunks covered in cut frond bases;
   a dense crown of ~20 wide, arching, glossy fronds whose leaflets are broad
   and overlap (the crown reads as a full green mass, not a skeleton); large
   orange-red spiky fruit bunches hanging right under the crown. Ripe bunches
   are clearly visible from the camera.
3. **Soft warm light.** Warm sun from the upper left, soft semi-transparent
   shadows, strong ambient/contact darkening under plants and trees (fake AO),
   saturated but not neon greens, cream highlights.
4. **Camera.** Perspective, ~45° pitch, closer than v1: roughly 20 m of ground
   across the screen. The player is clearly visible (~1/10 of screen height).
5. **Smooth, alive animation.** Skinned characters with authored, eased
   animation clips (idle breathing, walk, run, harvest, chop, plant, talk,
   cheer, sad, wave) cross-faded in Godot. Foliage sways, birds and butterflies
   move, chimney smokes, fireflies at night.
6. **UI like the target.** Cream rounded pills with round icon badges (coins,
   sun, leaf for Reputasi, eye for Kecurigaan), a tool hotbar bottom-right with
   number badges, key prompts bottom-left ("E  Panen"). Dialogs show a large
   **half-body 2D anime-style portrait** of the speaker next to a cream speech
   panel; choices are rounded pills with a dark dot bullet, in a 2-column grid.

Palette sampled from the target (use these as anchors):
`#98ac4d #7fa047 #b8c75e` light/mid leaf greens, `#5b7536 #405f2f #384126`
shade greens, `#c7ba6b #dbcb94 #b7a96e` dry grass / path highlights,
`#97865c #725839` dirt & wood, `#fcf2dd #f3e2c1` UI cream, fruit
`#e0572a #c43b1c #f08a3a` with near-black tips `#3a1f18`.

---

## Technical contract (everyone must follow this)

### Blender side (Python + `bpy` 4.5, Cycles only — no Eevee)
* 1 unit = 1 m, Z up, origin at ground centre, fronts face **-Y**.
* Export with `blender/common.py:export_glb` **or** an equivalent call that adds
  `export_vertex_color='ACTIVE'` when the mesh has a baked AO colour
  attribute, and `export_animations=True, export_animation_mode='ACTIONS'` for
  characters.
* **Vertex AO:** static assets should bake ambient occlusion into an active
  colour attribute named `Col` (Cycles bake, type AO, target vertex colours),
  multiplied softly (never darker than ~0.45). The game multiplies albedo by
  vertex colour.
* **Alpha cards:** leaves/grass may use image textures with alpha on simple
  card geometry. The material must export as glTF `alphaMode: MASK`
  (texture alpha → Math *Greater Than* / *Round* → BSDF Alpha, per the Blender
  glTF manual) and be double-sided (backface culling off). Verify by reading
  the exported glTF JSON. Textures ≤ 512 px, saved as PNG in
  `game/assets/textures/foliage/` and embedded in the GLB.
* Material names keep the `M_` prefix. Foliage materials must contain one of
  these words so the game gives them wind + two-sided lighting:
  `Frond Leaf Leaves Grass Foliage Canopy Bush Fern Petal Flower Plant`.
* Previews: render with Cycles and look at them; compare against the target.

### Characters (`game/assets/models/char_<name>.glb`, same 12 names as v1)
* One skinned mesh per character (joined parts are fine, but all weighted to an
  armature — no loose rigid objects), smooth shading, ≤ 6000 triangles,
  ≤ 6 materials, ~1.1 m tall (anak ~0.85 m, preman ~1.25 m), faces -Y.
* Armature bone names (exact): `hips` (root, at pelvis), `spine`, `chest`,
  `neck`, `head`, `upperarm_L`, `forearm_L`, `hand_L`, `upperarm_R`,
  `forearm_R`, `hand_R`, `thigh_L`, `shin_L`, `foot_L`, `thigh_R`, `shin_R`,
  `foot_R`. Optional extra bones for secondary motion (hat, hair, sarong)
  must be children of `head`/`hips` and named `extra_<what>`.
  `_L` is the character's own left (+X in Blender when facing -Y).
* Actions (exact names, 30 fps, in place, no root motion, smooth Bezier
  easing, overlapping motion — head/torso lag, arms follow through):
  `idle` (loop ~2.4 s: breathing, weight shift, small head look),
  `walk` (loop ~0.9 s, bouncy chibi walk with arm swing and body bob),
  `run` (loop ~0.6 s), `harvest` (~1.2 s: lift a long pole with both hands,
  thrust up, yank down), `chop` (~0.8 s machete swing with the right hand),
  `plant` (~1.2 s crouch, dig, place, stand), `talk` (loop ~2.4 s hand
  gestures), `cheer` (~1.2 s), `sad` (loop ~2.4 s slumped), `wave` (~1.2 s).
  Loops must be seamless (first frame == last frame).
* Tools are NOT part of the character; the game attaches them to `hand_R`.

### Vegetation / environment assets (`game/assets/models/*.glb`)
Replace in place (same names, `sawit_3` keeps a child Empty `Fruits` with the
fruit bunches as separate meshes): `sawit_0..3`, `tbs`, `tree_big`, `banana`,
`bush_a`, `bush_b`, `grass_tuft`, `flowers`, `rock_a/b/c` (add moss tint).
New assets: `piringan` (cleared mulch circle around a palm, ~2.4 m, flat
alpha decal, reddish-brown mulch + dead frond bits), `frond_fallen`
(dead frond lying on the ground), `fern_a`, `fern_b`, `keladi` (taro),
`shrub_a`, `shrub_b` (broad-leaf bushes), `grass_a`, `grass_b` (dense grass
clumps), `flowers_white`, `flowers_yellow`, `vine_log` (mossy log),
`pile_fronds` (stack of cut fronds). Budgets: sawit_3 ≤ 4500 tris, trees ≤
3500, undergrowth ≤ 350 each.

### Ground textures (`game/assets/textures/ground/*.png`, 512² tileable)
`grass.png` (painterly lush grass with clover/leaf detail), `grass_dry.png`,
`dirt.png` (packed earth path with pebbles and faint tyre tracks), `sand.png`,
`mulch.png`. Neutral enough to be tinted slightly by the shader.

### Portraits (`game/assets/portraits/<name>.png`)
Half-body 2D anime-style illustration of each character, transparent
background, facing slightly right, 1024 px tall, consistent style across all.
Names: `player kakek ibu kades nenek pemuda petani anak preman calo petugas
buruh mak hq` (`mak` = Mak Inah the warung owner, `hq` = the franchise boss on
the phone). Generated on Higgsfield (`gpt_image_2_5`, 1K). If the Higgsfield
CDN is unreachable from this container, the job ids/URLs are recorded in
`art/reference/portraits.json` and the game falls back to
`game/assets/icons/portrait_<name>.png`.

### Godot side
* Shaders take an optional albedo texture + alpha scissor, multiply by vertex
  colour (AO), keep the see-through hole around the player.
* Camera ~45° pitch, ~16 m distance, FOV ~35.
  **Chosen (polish round, `world.gd`): 45° pitch, 16.5 m, FOV 35 (≈19 m of ground
  across 16:9 at the player).** The look point sits 1.6 m up-screen (north) of the
  player, plus ~0.3 s of walking look-ahead, so the player stands a little below the
  centre and the crowns of the palms just behind them stay in frame. Portrait phones
  pull back (distance × (2 − aspect), FOV up to 42°: ~8.5 m across at 9:19.5). The
  shadow range follows the ground at the frame's top edge (~31 m at 16:9); camera far
  plane 90 m. (v2 had shipped 52° / 17 m because at 45° without the look-ahead the
  crowns next to the player left the top edge.)
* Post: glow (subtle), colour adjustment (saturation 1.0 since the polish round:
  the palette is set in the materials/light instead, contrast ~1.05).
* Undergrowth is scattered densely (`blender/terrain.py`, ~19k plants: modelled
  ferns / shrubs / keladi in thickets over a carpet of grass cards and the cheap
  procedural `fern_low` / `leaf_low` rosettes built in `undergrowth.gd`) and drawn as
  one MultiMesh per model holding only the plants under the camera's view (4 m cells
  re-packed as the view moves); "Hemat baterai" draws half of every cell.
