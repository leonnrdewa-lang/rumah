class_name SawitSystems
extends RefCounted
## The farm-sim systems added in the "systems" round, held by GS as `GS.sys`:
## seasons & weather (weather_sys.gd), the TBS market & gudang (market_sys.gd), the
## crew (crew_sys.gd) and the upgrade tree (tech_sys.gd). GS.start_new_day calls
## before_growth / after_growth / economy / flush_events in that order; the state is
## saved under "sys" in the save file (older saves load with the defaults).

var weather := WeatherSys.new()
var market := MarketSys.new()
var crew := CrewSys.new()
var tech := TechSys.new()
## morning events raised by the systems today ("kabut_asap", "banjir", "mogok",
## "ikan_mati"); merged into GS.pending_events after the day's random event
var events: Array = []


func bind(gs: Node) -> void:
	for s in [weather, market, crew, tech]:
		s.gs = gs


func reset() -> void:
	weather.reset()
	market.reset()
	crew.reset()
	tech.reset()
	events.clear()


func before_growth(report: Array) -> void:
	events.clear()
	weather.roll(report)


func after_growth(report: Array) -> void:
	weather.after_growth(report)


func economy(report: Array) -> void:
	## the market moves and the gudang ages, the crew is paid and works, the truck /
	## mini mill / dirty upgrades do their thing
	market.new_day(report)
	crew.new_day(report)
	tech.new_day(report)


func flush_events(pending: Array) -> void:
	for e in events:
		if not e in pending:
			pending.append(e)
	events.clear()


func to_dict() -> Dictionary:
	return {"weather": weather.to_dict(), "market": market.to_dict(), "crew": crew.to_dict(), "tech": tech.to_dict()}


func from_dict(d: Dictionary) -> void:
	reset()
	if typeof(d.get("weather")) == TYPE_DICTIONARY:
		weather.from_dict(d["weather"])
	if typeof(d.get("market")) == TYPE_DICTIONARY:
		market.from_dict(d["market"])
	if typeof(d.get("crew")) == TYPE_DICTIONARY:
		crew.from_dict(d["crew"])
	else:
		crew.normalize()
	if typeof(d.get("tech")) == TYPE_DICTIONARY:
		tech.from_dict(d["tech"])
