#!/usr/bin/env bash
# Compiles every game script against the UnityEngine 2021.3 reference assemblies (from NuGet) with
# Mono's C# compiler - a quick way to catch compile errors without opening the Unity Editor.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BIN="$HERE/bin"
mkdir -p "$BIN"
if [ ! -d "$BIN/unityengine" ]; then
  curl -sSL -o "$BIN/unityengine.nupkg" https://api.nuget.org/v3-flatcontainer/unityengine.modules/2021.3.33/unityengine.modules.2021.3.33.nupkg
  unzip -o -q "$BIN/unityengine.nupkg" "lib/net45/*" -d "$BIN/unityengine"
fi
REFS=()
for dll in "$BIN"/unityengine/lib/net45/UnityEngine*.dll; do REFS+=("-r:$dll"); done
find "$ROOT/Assets/OjolRush/Scripts" -name '*.cs' -print0 | xargs -0 \
  mcs -target:library -nowarn:618 -warnaserror+ "${REFS[@]}" -out:"$BIN/OjolRush.dll"
echo "Compile check OK"
