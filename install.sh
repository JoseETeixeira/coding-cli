#!/usr/bin/env bash

set -euo pipefail

OWNER="${OWNER:-Freight-Hero}"
REPO="${REPO:-coding-cli}"
BINARY_NAME="${BINARY_NAME:-freighthero}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
PROFILE_FILE="${PROFILE_FILE:-}"
VERSION="${VERSION:-}"
INSTALL_BASE_URL="${INSTALL_BASE_URL:-}"
GITHUB_API_VERSION="${GITHUB_API_VERSION:-2026-03-10}"
GITHUB_AUTH_TOKEN="${GITHUB_AUTH_TOKEN:-${GITHUB_PAT_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}}"
TMP_DIR=""

cleanup() {
	if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
		rm -rf "$TMP_DIR"
	fi
}

trap cleanup EXIT

require_command() {
	if ! command -v "$1" >/dev/null 2>&1; then
		printf 'Missing required command: %s\n' "$1" >&2
		exit 1
	fi
}

curl_api() {
	if [[ -n "$GITHUB_AUTH_TOKEN" ]]; then
		curl -fsSL \
			-H "Accept: application/vnd.github+json" \
			-H "Authorization: Bearer $GITHUB_AUTH_TOKEN" \
			-H "X-GitHub-Api-Version: $GITHUB_API_VERSION" \
			"$1"
		return
	fi

	curl -fsSL \
		-H "Accept: application/vnd.github+json" \
		-H "X-GitHub-Api-Version: $GITHUB_API_VERSION" \
		"$1"
}

curl_download() {
	if [[ -n "$GITHUB_AUTH_TOKEN" ]]; then
		curl -fsSL \
			-H "Authorization: Bearer $GITHUB_AUTH_TOKEN" \
			"$1" \
			-o "$2"
		return
	fi

	curl -fsSL "$1" -o "$2"
}

detect_os() {
	case "$(uname -s)" in
	Darwin)
		printf 'darwin\n'
		;;
	Linux)
		printf 'linux\n'
		;;
	*)
		printf 'Unsupported operating system: %s\n' "$(uname -s)" >&2
		exit 1
		;;
	esac
}

detect_arch() {
	case "$(uname -m)" in
	x86_64|amd64)
		printf 'amd64\n'
		;;
	aarch64|arm64)
		printf 'arm64\n'
		;;
	*)
		printf 'Unsupported CPU architecture: %s\n' "$(uname -m)" >&2
		exit 1
		;;
	esac
}

resolve_latest_version() {
	local api_url
	local release_json
	local tag

	api_url="https://api.github.com/repos/${OWNER}/${REPO}/releases/latest"
	release_json="$(curl_api "$api_url")"
	tag="$(printf '%s\n' "$release_json" | sed -nE 's/.*"tag_name":[[:space:]]*"([^"]+)".*/\1/p' | head -n 1)"
	if [[ -z "$tag" ]]; then
		if [[ -z "$GITHUB_AUTH_TOKEN" ]]; then
			printf 'Could not resolve latest release tag from %s. If repository is private, export GITHUB_PAT_TOKEN, GH_TOKEN, or GITHUB_TOKEN and rerun.\n' "$api_url" >&2
		else
			printf 'Could not resolve latest release tag from %s\n' "$api_url" >&2
		fi
		exit 1
	fi

	printf '%s\n' "$tag"
}

path_contains() {
	case ":$PATH:" in
	*":$1:"*)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

resolve_profile_file() {
	if [[ -n "$PROFILE_FILE" ]]; then
		printf '%s\n' "$PROFILE_FILE"
		return
	fi

	case "${SHELL##*/}" in
	zsh)
		if [[ -f "$HOME/.zshrc" ]]; then
			printf '%s\n' "$HOME/.zshrc"
		else
			printf '%s\n' "$HOME/.zprofile"
		fi
		;;
	bash)
		if [[ -f "$HOME/.bashrc" ]]; then
			printf '%s\n' "$HOME/.bashrc"
		elif [[ -f "$HOME/.bash_profile" ]]; then
			printf '%s\n' "$HOME/.bash_profile"
		else
			printf '%s\n' "$HOME/.profile"
		fi
		;;
	*)
		printf '%s\n' "$HOME/.profile"
		;;
	esac
}

ensure_path() {
	local profile_path
	local export_line

	if path_contains "$INSTALL_DIR"; then
		return
	fi

	profile_path="$(resolve_profile_file)"
	export_line="export PATH=\"$INSTALL_DIR:\$PATH\""
	mkdir -p "$(dirname "$profile_path")"
	if [[ ! -f "$profile_path" ]] || ! grep -Fqx "$export_line" "$profile_path"; then
		printf '\n# Added by FreightHero installer\n%s\n' "$export_line" >> "$profile_path"
	fi

	printf 'Added %s to PATH in %s\n' "$INSTALL_DIR" "$profile_path"
	printf 'Reload shell or run: export PATH="%s:$PATH"\n' "$INSTALL_DIR"
}

install_binary() {
	local os_name
	local arch_name
	local asset_name
	local download_url
	local archive_path

	require_command curl
	require_command tar
	require_command mktemp

	os_name="$(detect_os)"
	arch_name="$(detect_arch)"
	if [[ -z "$VERSION" && -z "$INSTALL_BASE_URL" ]]; then
		VERSION="$(resolve_latest_version)"
	fi

	asset_name="${BINARY_NAME}_${os_name}_${arch_name}.tar.gz"
	if [[ -n "$INSTALL_BASE_URL" ]]; then
		download_url="${INSTALL_BASE_URL%/}/${asset_name}"
	else
		download_url="https://github.com/${OWNER}/${REPO}/releases/download/${VERSION}/${asset_name}"
	fi

	TMP_DIR="$(mktemp -d)"
	archive_path="$TMP_DIR/$asset_name"

	printf 'Downloading %s\n' "$download_url"
	curl_download "$download_url" "$archive_path"
	tar -xzf "$archive_path" -C "$TMP_DIR"

	mkdir -p "$INSTALL_DIR"
	if command -v install >/dev/null 2>&1; then
		install -m 0755 "$TMP_DIR/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
	else
		cp "$TMP_DIR/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
		chmod 0755 "$INSTALL_DIR/$BINARY_NAME"
	fi

	ensure_path
	printf 'Installed %s to %s/%s\n' "$BINARY_NAME" "$INSTALL_DIR" "$BINARY_NAME"
}

install_binary