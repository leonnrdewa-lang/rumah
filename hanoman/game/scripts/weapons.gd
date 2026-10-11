class_name Weapons
extends RefCounted
## Hanoman's pusaka (Infernal-Arms style). The staff is the default; Jembawan
## can teach the others for Wijayakusuma Blossoms, and the weapon rack in
## Pancawati switches between them. Each weapon has its own attack chain and
## its own Special.
##   tongkat  Extending Staff: 3-hit combo, Special = staff laser
##   gada     Rujakpolo Mace: slow crushing 3-hit combo, Special = Earthquake
##   panah    Sacred Bow: arrows (3rd is a piercing volley), Special = Arrow Rain
##   cakra    Sudarsana Chakra: thrown disc that returns, Special = Orbiting discs

const ALL := {
	"tongkat": {"name": "Extending Staff", "desc": "Fast 3-hit combo. Special: the staff shoots out like a laser.",
		"cost": 0, "icon": "res://assets/icons/slot_serang.png"},
	"gada": {"name": "Rujakpolo Mace", "desc": "Slow, crushing blows that stagger anything. Special: Earthquake around you.",
		"cost": 4, "icon": "res://assets/icons/slot_serang.png"},
	"panah": {"name": "Sacred Bow", "desc": "Strike from afar; every third shot is a piercing volley. Special: Arrow Rain.",
		"cost": 5, "icon": "res://assets/icons/slot_jurus.png"},
	"cakra": {"name": "Sudarsana Chakra", "desc": "Hurl a disc that cuts on the way out and back. Special: three orbiting discs.",
		"cost": 6, "icon": "res://assets/icons/slot_ajian.png"},
}

## Attack chains (same fields as Player.COMBO).
const COMBOS := {
	"gada": [
		{"anim": "swing_a", "len": 0.48, "hit": 0.22, "dmg": 20.0, "range": 2.9, "arc": 2.4, "lunge": 2.0},
		{"anim": "swing_b", "len": 0.48, "hit": 0.22, "dmg": 20.0, "range": 2.9, "arc": 2.4, "lunge": 2.0},
		{"anim": "slam", "len": 0.75, "hit": 0.4, "dmg": 46.0, "range": 3.6, "arc": 6.3, "lunge": 3.0},
	],
	"panah": [
		{"anim": "thrust", "len": 0.28, "hit": 0.1, "dmg": 11.0, "range": 0.0, "arc": 0.0, "lunge": -1.5},
		{"anim": "thrust", "len": 0.28, "hit": 0.1, "dmg": 11.0, "range": 0.0, "arc": 0.0, "lunge": -1.5},
		{"anim": "thrust", "len": 0.4, "hit": 0.15, "dmg": 9.0, "range": 0.0, "arc": 0.0, "lunge": -2.5},
	],
	"cakra": [
		{"anim": "swing_a", "len": 0.34, "hit": 0.12, "dmg": 13.0, "range": 0.0, "arc": 0.0, "lunge": 1.0},
		{"anim": "swing_b", "len": 0.34, "hit": 0.12, "dmg": 13.0, "range": 0.0, "arc": 0.0, "lunge": 1.0},
	],
}


static func current() -> String:
	var w := String(G.meta.get("weapon", "tongkat"))
	return w if unlocked(w) else "tongkat"


static func unlocked(w: String) -> bool:
	return w == "tongkat" or G.meta.get("weapons", []).has(w)


static func color(p: Player) -> Color:
	var holder := Boons.slot_holder("serang")
	return G.GOD_COLORS[Boons.god_of(holder)] if holder != "" else Color(1.0, 0.85, 0.45)


## Ranged / thrown attacks for the bow and the chakra (melee weapons use the
## player's arc hit with their own combo table).
static func shoot(p: Player, i: int, dir: Vector3, dmg: float) -> void:
	var col := color(p)
	var from := p.global_position + dir * 0.6
	match current():
		"panah":
			var shots := [0.0] if i < 2 else [-0.18, 0.0, 0.18]
			for a in shots:
				var d: Vector3 = dir.rotated(Vector3.UP, a)
				var pr := Projectile.spawn(from, d, 26.0, "player", dmg, col, 0.14)
				pr.pierce = i == 2
				pr.knockback = 2.5
				pr.on_hit = _boon_hit.bind(p)
			Au.sfx("sfx_swing1", -4.0, 0.1, 1.6)
			Fx.sprite("k_trace", from + Vector3(0, 1.0, 0), 1.4, col, 0.12, {"dir": dir, "tint": 0.4, "intensity": 2.0})
		"cakra":
			var disc := Chakram.new()
			disc.owner_player = p
			disc.dmg = dmg
			disc.dir = dir
			disc.col = col
			Fx.layer.add_child(disc)
			disc.global_position = Vector3(from.x, 1.0, from.z)
			Au.sfx("sfx_tail", -6.0, 0.1, 1.5)


static func _boon_hit(e, proj, p: Player) -> void:
	p._deal(e, proj.damage, proj.knockback, proj.color)
	if Boons.owned("surya_serang"):
		e.apply_burn(Boons.val("surya_serang"))
	if Boons.owned("baruna_serang"):
		e.apply_wet(0.3)
	if Boons.owned("indra_serang"):
		p.chain_lightning(e, Boons.val("indra_serang"), 2)


## Specials for the non-staff weapons. Returns false for the staff (the player
## fires its laser itself).
static func special(p: Player, dir: Vector3, col: Color) -> bool:
	var mult := 1.0 + Boons.val("bayu_jurus") / 100.0
	match current():
		"gada":
			var c := p.global_position
			Fx.shock(c, 5.5, col, 0.5, true)
			Fx.sprite("k_dirt", c + Vector3(0, 0.4, 0), 9.0, Color(0.8, 0.6, 0.4), 0.6, {"flat": true, "from": 0.3, "grow": 1.1, "tint": 0.4, "intensity": 1.2})
			Au.sfx("sfx_staff_slam", 0.0, 0.05, 0.7)
			G.main.shake(0.6)
			G.vibrate(80)
			for e in G.main.enemies():
				if not e.dead and e.global_position.distance_to(c) < 5.5 + e.radius:
					p._deal(e, 30.0 * mult, 9.0, col)
					e.stagger = maxf(e.stagger, 1.2)
			return true
		"panah":
			var centre: Vector3 = G.main.clamp_to_room(p.global_position + dir * 7.0, 1.0)
			Fx.magic_circle(centre, 3.8, col, 1.2, 2.0)
			Au.sfx("sfx_cast", -3.0)
			for k in 14:
				var off := Vector3(randf_range(-3.5, 3.5), 0, randf_range(-3.5, 3.5))
				var at := centre + off
				var tw := p.create_tween()
				tw.tween_interval(0.25 + k * 0.06)
				tw.tween_callback(func():
					Fx.sprite("k_trace", at + Vector3(0, 1.5, 0), 2.2, col, 0.18, {"billboard": 2.0, "stretch": Vector2(0.3, 1.6), "tint": 0.4, "intensity": 2.4})
					Fx.impact(at + Vector3(0, 0.2, 0), col)
					for e in G.main.enemies():
						if not e.dead and Vector2(e.global_position.x - at.x, e.global_position.z - at.z).length() < 1.3 + e.radius:
							p._deal(e, 9.0 * mult, 2.0, col))
			return true
		"cakra":
			for k in 3:
				var orb := Chakram.new()
				orb.owner_player = p
				orb.dmg = 10.0 * mult
				orb.col = col
				orb.orbit = true
				orb.orbit_phase = TAU * k / 3.0
				Fx.layer.add_child(orb)
				orb.global_position = p.global_position + Vector3(0, 1.0, 0)
			Au.sfx("sfx_cast", -3.0, 0.0, 1.3)
			return true
	return false


## Visual for the weapon in Hanoman's hand: restyles the Staff node.
static func dress(staff: Staff) -> void:
	if staff == null:
		return
	staff.set_style(current())
