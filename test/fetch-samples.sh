#!/usr/bin/env bash
# Fetch the DiscoC v0.2.0 SNES demo payloads (GPL-3.0; compiler output for the SuperFX, with the
# assembly listings the compiler wrote). Pinned URL + SHA-256; nothing is committed.
#   test/fetch-samples.sh <dir>
set -euo pipefail
D=$(mkdir -p "$1" && cd "$1" && pwd)
URL=https://github.com/DiscoLabOfficial/DiscoC/releases/download/v0.2.0/discoc-v0.2.0-snes-demos.zip
SHA=e8b2be90510d3500bec89050d639d849a2c41f62d804114d3f6e9617c7e4e60a
if [[ ! -f $D/demos.zip ]] || ! echo "$SHA  $D/demos.zip" | sha256sum -c --status; then
	curl -fsSL "$URL" -o "$D/demos.zip"
	echo "$SHA  $D/demos.zip" | sha256sum -c --status || { echo "SHA-256 mismatch for $URL" >&2; exit 1; }
fi
[[ -d $D/build-inputs ]] || unzip -q -o "$D/demos.zip" 'build-inputs/*' -d "$D"
echo "$D/build-inputs"
