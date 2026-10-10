class_name Codex
extends RefCounted
## The Lontar of Tales: entries about the Ramayana and the legend of Surabaya,
## unlocked the first time Hanoman meets someone (G.unlock_codex).
## id -> [name, subtitle, text, portrait id]

const ENTRIES := {
	"hanoman": ["Hanoman", "Son of Batara Bayu, envoy of Rama",
		"A white monkey born of the wind god and the nymph Anjani. Swift as a storm and loyal beyond measure, he was chosen by Rama to cross the ocean and find Dewi Sinta. In wayang he is called Anoman, Anjaniputra, Bayutanaya, and his staff and claws (Pancanaka) never miss.", "hanoman"],
	"rama": ["King Rama", "Prince of Ayodhya, incarnation of Wisnu",
		"Exiled to the forest with his wife Sinta and brother Laksmana, Rama lost Sinta to the demon king Rahwana. He now camps at Pancawati with the monkey army of Kiskenda, waiting for word from his envoy.", "rama"],
	"jembawan": ["Sage Jembawan", "Elder of the Wanara",
		"An ancient bear-sage who has seen ages come and go. It was Jembawan who reminded Hanoman of the strength he had forgotten, and who still teaches the old Kesaktian to those who bring him the flower of life.", "jembawan"],
	"sugriwa": ["King Sugriwa", "Lord of Kiskenda",
		"King of the monkeys, restored to his throne by Rama's help. In return he swore his whole army to Rama's cause. He loves Hanoman like a younger brother, and teases him like one too.", "sugriwa"],
	"kijang": ["Kijang Kencana", "The Golden Deer, Kala Marica",
		"The demon Marica took the shape of a golden deer to lure Rama away from Sinta, so that Rahwana could carry her off. The deceiver still haunts the Dandaka forest, splitting into illusions to mock those who chase him.", "kijang"],
	"sura": ["Sura", "Shark King of the Southern Sea",
		"A great white shark who ruled the waters. Sura and Baya once agreed to split the world: the sea for Sura, the land for Baya. But both wanted the rich estuary where the river meets the sea.", "sura"],
	"baya": ["Baya", "Crocodile King of Kali Mas",
		"The crocodile lord of the Kali Mas river. His endless battle with Sura in the estuary gave the city of Surabaya its name: sura (shark) and baya (crocodile), still locked together on the city's emblem today.", "baya"],
	"surabaya": ["The Legend of Surabaya", "Sura ing Baya",
		"East Java's capital takes its name from the fight between the shark Sura and the crocodile Baya. The phrase 'sura ing baya' is also read as 'brave in the face of danger', the city's motto.", ""],
	"kumbakarna": ["Kumbakarna", "Rahwana's giant brother",
		"A colossal raksasa cursed to sleep for months at a time. Unlike his brother he knew Rahwana was in the wrong, yet he fought for Alengka out of loyalty to his land, not to the king. Wayang honours him as a true patriot.", "kumbakarna"],
	"indrajit": ["Indrajit", "Meghanada, son of Rahwana",
		"The greatest warrior of Alengka, who once defeated Batara Indra himself and took his name. A master of illusion and of the Nagapasa, the serpent arrow that binds its target in coils of snakes.", "indrajit"],
	"wil": ["Wil", "Forest imps",
		"Small, quick raksasa that swarm travellers in the Dandaka forest. Alone they are pests; in a pack they are deadly.", ""],
	"cakil": ["Buto Cakil", "The jutting-jawed ogre",
		"A wayang favourite: a raksasa with a jutting lower jaw and a kris, all bluster and fury. He always attacks first and always loses to the hero.", ""],
	"buto_ijo": ["Buto Ijo", "The green giant",
		"A huge green ogre from Javanese folklore, slow but crushing. Parents still warn children that Buto Ijo comes for those who stay out at dusk.", ""],
	"banaspati": ["Banaspati", "Flaming spirit",
		"A burning head that flies through the night in Javanese tales, setting fires where it passes.", ""],
	"yuyu": ["Yuyu Kangkang", "The giant crab",
		"The crab who ferried travellers across the river in the tale of Ande-Ande Lumut, always for a price. His shell turns any blow from the front.", ""],
	"pemanah": ["Alengka Archers", "Rahwana's bowmen",
		"Raksasa archers of Alengka's army. They draw a red line of sight before every shot; step out of it.", ""],
	"dukun": ["Alengka Sorcerers", "Summoners of Wil",
		"Hedge-wizards in Rahwana's pay who call Wil out of thin air and vanish when cornered. Kill them first.", ""],
	"tameng": ["Shield-bearers", "Alengka's front line",
		"Heavily armoured raksasa whose great shields stop any blow from the front. Dash behind them or bind them with a Spell.", ""],
	"alengka": ["Alengka", "Kingdom of Rahwana",
		"An island kingdom of gold beyond the southern ocean, ruled by the ten-headed demon king Rahwana. In its Asoka garden (Argasoka) Dewi Sinta waits, refusing every word of the king.", ""],
}

const ORDER := ["hanoman", "rama", "jembawan", "sugriwa", "kijang", "sura", "baya", "surabaya",
	"kumbakarna", "indrajit", "alengka", "wil", "cakil", "buto_ijo", "banaspati", "yuyu", "pemanah", "dukun", "tameng"]


static func unlocked() -> Array:
	var out := []
	for id in ORDER:
		if G.seen("codex_" + id):
			out.append(id)
	return out


static func records_text() -> String:
	var t := G.stat("playtime")
	var fastest := G.stat("fastest")
	var lines := [
		"Journeys: %d    Victories: %d    Falls: %d" % [int(G.meta.runs), int(G.meta.wins), int(G.meta.deaths)],
		"Ogres defeated: %d    Bosses defeated: %d" % [int(G.stat("kills")), int(G.meta.get("boss_kills", 0))],
		"Deepest chamber: %d    Highest Heat: %d" % [int(G.meta.best_room), int(G.meta.get("max_heat", 0))],
		"Time on the road: %dh %02dm" % [int(t / 3600.0), int(fmod(t, 3600.0) / 60.0)],
	]
	if fastest > 0.0:
		lines.append("Fastest victory: %dm %02ds" % [int(fastest / 60.0), int(fmod(fastest, 60.0))])
	return "\n".join(lines)
