#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
BINARY_NAME="${BINARY_NAME:-freighthero}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist}"
TARGET_GOOS="${GOOS:-$(go env GOOS)}"
TARGET_GOARCH="${GOARCH:-$(go env GOARCH)}"
ARCHIVE="${ARCHIVE:-false}"

mkdir -p "$OUTPUT_DIR"
cd "$ROOT_DIR"

binary_path="$OUTPUT_DIR/$BINARY_NAME"
if [[ "$TARGET_GOOS" != "$(go env GOOS)" || "$TARGET_GOARCH" != "$(go env GOARCH)" ]]; then
	binary_path="$OUTPUT_DIR/${BINARY_NAME}_${TARGET_GOOS}_${TARGET_GOARCH}"
fi

CGO_ENABLED=0 GOOS="$TARGET_GOOS" GOARCH="$TARGET_GOARCH" go build -o "$binary_path" .

if [[ "$ARCHIVE" == "true" ]]; then
	archive_path="$OUTPUT_DIR/${BINARY_NAME}_${TARGET_GOOS}_${TARGET_GOARCH}.tar.gz"
	staging_dir="$(mktemp -d)"
	trap 'rm -rf "$staging_dir"' EXIT
	cp "$binary_path" "$staging_dir/$BINARY_NAME"
	tar -C "$staging_dir" -czf "$archive_path" "$BINARY_NAME"
	printf 'Built %s\n' "$archive_path"
	exit 0
fi

printf 'Built %s\n' "$binary_path"