#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
BINARY_NAME="${BINARY_NAME:-coding-cli}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist}"
ARCHIVE="${ARCHIVE:-false}"

# Resolve host GOOS/GOARCH from `go env` while temporarily clearing any
# inherited values so we can tell whether the caller actually requested a
# cross-compile via GOOS=... / GOARCH=...
HOST_GOOS="$(GOOS= GOARCH= go env GOOS)"
HOST_GOARCH="$(GOOS= GOARCH= go env GOARCH)"
TARGET_GOOS="${GOOS:-$HOST_GOOS}"
TARGET_GOARCH="${GOARCH:-$HOST_GOARCH}"

mkdir -p "$OUTPUT_DIR"
cd "$ROOT_DIR"

binary_suffix=""
if [[ "$TARGET_GOOS" == "windows" ]]; then
	binary_suffix=".exe"
fi

binary_basename="${BINARY_NAME}${binary_suffix}"
binary_path="$OUTPUT_DIR/$binary_basename"
if [[ "$TARGET_GOOS" != "$HOST_GOOS" || "$TARGET_GOARCH" != "$HOST_GOARCH" ]]; then
	binary_path="$OUTPUT_DIR/${BINARY_NAME}_${TARGET_GOOS}_${TARGET_GOARCH}${binary_suffix}"
fi

CGO_ENABLED=0 GOOS="$TARGET_GOOS" GOARCH="$TARGET_GOARCH" go build -o "$binary_path" .

if [[ "$ARCHIVE" == "true" ]]; then
	staging_dir="$(mktemp -d)"
	trap 'rm -rf "$staging_dir"' EXIT
	cp "$binary_path" "$staging_dir/$binary_basename"

	if [[ "$TARGET_GOOS" == "windows" ]]; then
		archive_path="$OUTPUT_DIR/${BINARY_NAME}_${TARGET_GOOS}_${TARGET_GOARCH}.zip"
		rm -f "$archive_path"
		if command -v zip >/dev/null 2>&1; then
			(cd "$staging_dir" && zip -q "$archive_path" "$binary_basename")
		elif command -v powershell.exe >/dev/null 2>&1; then
			win_src="$staging_dir/$binary_basename"
			win_dest="$archive_path"
			if command -v cygpath >/dev/null 2>&1; then
				win_src="$(cygpath -w "$win_src")"
				win_dest="$(cygpath -w "$win_dest")"
			fi
			powershell.exe -NoProfile -NonInteractive -Command \
				"Compress-Archive -Path '$win_src' -DestinationPath '$win_dest' -Force" >/dev/null
		else
			printf 'Neither `zip` nor `powershell.exe` is available; cannot build zip archive.\n' >&2
			exit 1
		fi
	else
		archive_path="$OUTPUT_DIR/${BINARY_NAME}_${TARGET_GOOS}_${TARGET_GOARCH}.tar.gz"
		tar -C "$staging_dir" -czf "$archive_path" "$binary_basename"
	fi
	printf 'Built %s\n' "$archive_path"
	exit 0
fi

printf 'Built %s\n' "$binary_path"
