# Higgsfield pipeline (runs in the Higgsfield sandbox, not locally)

The Higgsfield version of the game lives at https://hanoman-duta.higgsfield.app
(a Higgsfield "game" website). The container that builds this repo cannot reach
Higgsfield's CDN, so every Higgsfield asset is downloaded and packed inside the
Higgsfield sandbox (`sandbox_exec`) and served next to the Godot web build as
`hf/` + `hf/manifest.json`. `game/scripts/hf.gd` loads that pack at runtime;
without it the game falls back to the built-in Blender assets.

Pipeline (all Higgsfield tools, credits noted):

1. Concept art — GPT Image 2.5, full body A-pose on white (1.5 each).
2. `image_to_3d` (Meshy) with texture + auto-rig + first animation (38 each for
   humanoids: Hanoman, Wil, Buto Cakil, Buto Ijo, Rama, Jembawan, Sugriwa);
   static textured meshes for Sura, Baya, Yuyu Kangkang, Kijang Kencana (30 each).
3. Extra clips with `3d_rigging` on the result GLB (8 each).
   Hanoman: idle=Combat_Stance(89), run=RunFast(16), attack_1=Left_Slash(97),
   attack_3=Heavy_Hammer_Swing(128), dash=Roll_Dodge(158), cast=Charged_Spell_Cast(125),
   hit=Hit_Reaction(178), die=Dead(8). Enemies: walk (112/21/119), attack (97/4/127), hit (178).
4. Merge clips: `glb_merge_anims.py` from the website-builder workflow bundle.
5. `glb_shrink.py` (here): textures to 1024 px JPEG, rename clips.
6. Painted arena floors (GPT Image 2.5, top-down), portraits with
   `remove_background`, 45 voiced lines with Seed Audio (`tools/voice_lines.py`
   lists them; file name = first 12 hex of md5(text)).
7. `fetch.py` (here) builds `hf/` from `../../art/hf_assets.json`.
