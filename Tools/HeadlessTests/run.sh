#!/usr/bin/env bash
# Runs the engine-independent Ojol Rush tests (score/combo/rating/orders/rush levels/city map/
# traffic AI simulation) with Mono + NUnitLite, without Unity.
# Requires: mono-mcs + mono-runtime (apt install mono-mcs mono-runtime), curl, unzip.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BIN="$HERE/bin"
mkdir -p "$BIN"
NUNIT_VERSION=3.13.3
for pkg in nunit nunitlite; do
  if [ ! -f "$BIN/$pkg.dll" ] && [ ! -f "$BIN/${pkg}.framework.dll" ]; then
    curl -sSL -o "$BIN/$pkg.nupkg" "https://api.nuget.org/v3-flatcontainer/$pkg/$NUNIT_VERSION/$pkg.$NUNIT_VERSION.nupkg"
    unzip -o -q "$BIN/$pkg.nupkg" "lib/net45/*" -d "$BIN/$pkg"
    cp "$BIN/$pkg"/lib/net45/*.dll "$BIN/"
  fi
done
S="$ROOT/Assets/OjolRush/Scripts"
mcs -nowarn:618,414 -r:"$BIN/nunit.framework.dll" -r:"$BIN/nunitlite.dll" \
  "$HERE/UnityShim.cs" "$HERE/Runner.cs" \
  "$S/Core/Geo.cs" "$S/Core/GameConfig.cs" \
  "$S/Gameplay/ComboSystem.cs" "$S/Gameplay/ScoreManager.cs" \
  "$S/World/CityMap.cs" \
  "$S/Traffic/TrafficLights.cs" "$S/Traffic/VehicleSpec.cs" "$S/Traffic/TrafficSensing.cs" "$S/Traffic/TrafficVehicle.cs" \
  "$ROOT"/Assets/OjolRush/Tests/EditMode/*.cs \
  -out:"$BIN/OjolRushHeadlessTests.exe"
cd "$BIN"
mono OjolRushHeadlessTests.exe --noresult "$@"
