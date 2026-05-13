#!/usr/bin/env bash

set -euo pipefail

OWNER="${OWNER:-JoseETeixeira}"
REPO="${REPO:-coding-cli}"
BINARY_NAME="${BINARY_NAME:-coding-cli}"
INSTALL_DIR_OVERRIDE="${INSTALL_DIR:-}"
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
	MINGW*|MSYS*|CYGWIN*)
		printf 'windows\n'
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

default_install_dir() {
	local os_name="$1"
	if [[ -n "$INSTALL_DIR_OVERRIDE" ]]; then
		printf '%s\n' "$INSTALL_DIR_OVERRIDE"
		return
	fi

	if [[ "$os_name" == "windows" ]]; then
		# Prefer %LOCALAPPDATA%\Programs\coding-cli\bin so the user PATH update is per-user.
		if [[ -n "${LOCALAPPDATA:-}" ]]; then
			# LOCALAPPDATA arrives as a Windows path under MSYS/Git Bash; convert if cygpath exists.
			if command -v cygpath >/dev/null 2>&1; then
				printf '%s\n' "$(cygpath -u "$LOCALAPPDATA")/Programs/coding-cli/bin"
				return
			fi
			printf '%s/Programs/coding-cli/bin\n' "$LOCALAPPDATA"
			return
		fi
		printf '%s/bin\n' "$HOME"
		return
	fi

	printf '%s/.local/bin\n' "$HOME"
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

ensure_path_unix() {
	local install_dir="$1"
	local profile_path
	local export_line

	if path_contains "$install_dir"; then
		return
	fi

	profile_path="$(resolve_profile_file)"
	export_line="export PATH=\"$install_dir:\$PATH\""
	mkdir -p "$(dirname "$profile_path")"
	if [[ ! -f "$profile_path" ]] || ! grep -Fqx "$export_line" "$profile_path"; then
		printf '\n# Added by coding-cli installer\n%s\n' "$export_line" >> "$profile_path"
	fi

	printf 'Added %s to PATH in %s\n' "$install_dir" "$profile_path"
	printf 'Reload shell or run: export PATH="%s:$PATH"\n' "$install_dir"
}

ensure_path_windows() {
	local install_dir="$1"
	local windows_dir="$install_dir"

	if command -v cygpath >/dev/null 2>&1; then
		windows_dir="$(cygpath -w "$install_dir")"
	fi

	if ! command -v powershell.exe >/dev/null 2>&1; then
		printf 'powershell.exe not found; add %s to PATH manually.\n' "$windows_dir"
		return
	fi

	# Use PowerShell to persist into the User PATH if not already present.
	powershell.exe -NoProfile -NonInteractive -Command \
		"\$dir = '${windows_dir//\\/\\\\}'; \$current = [Environment]::GetEnvironmentVariable('Path','User'); if ([string]::IsNullOrWhiteSpace(\$current)) { [Environment]::SetEnvironmentVariable('Path', \$dir, 'User') } elseif ((\$current -split ';') -notcontains \$dir) { [Environment]::SetEnvironmentVariable('Path', \$dir + ';' + \$current, 'User') }" \
		>/dev/null 2>&1 || printf 'Could not update user PATH automatically; add %s manually.\n' "$windows_dir"

	printf 'Ensured %s is on the user PATH (restart shell to pick up the change).\n' "$windows_dir"
}

install_binary() {
	local os_name
	local arch_name
	local asset_name
	local download_url
	local archive_path
	local install_dir
	local binary_basename

	require_command curl
	require_command mktemp

	os_name="$(detect_os)"
	arch_name="$(detect_arch)"
	install_dir="$(default_install_dir "$os_name")"
	binary_basename="$BINARY_NAME"
	if [[ "$os_name" == "windows" ]]; then
		binary_basename="${BINARY_NAME}.exe"
		require_command unzip
	else
		require_command tar
	fi

	if [[ -z "$VERSION" && -z "$INSTALL_BASE_URL" ]]; then
		VERSION="$(resolve_latest_version)"
	fi

	if [[ "$os_name" == "windows" ]]; then
		asset_name="${BINARY_NAME}_${os_name}_${arch_name}.zip"
	else
		asset_name="${BINARY_NAME}_${os_name}_${arch_name}.tar.gz"
	fi

	if [[ -n "$INSTALL_BASE_URL" ]]; then
		download_url="${INSTALL_BASE_URL%/}/${asset_name}"
	else
		download_url="https://github.com/${OWNER}/${REPO}/releases/download/${VERSION}/${asset_name}"
	fi

	TMP_DIR="$(mktemp -d)"
	archive_path="$TMP_DIR/$asset_name"

	printf 'Downloading %s\n' "$download_url"
	curl_download "$download_url" "$archive_path"

	if [[ "$os_name" == "windows" ]]; then
		unzip -q "$archive_path" -d "$TMP_DIR"
	else
		tar -xzf "$archive_path" -C "$TMP_DIR"
	fi

	mkdir -p "$install_dir"
	src="$TMP_DIR/$binary_basename"
	dest="$install_dir/$binary_basename"
	if command -v install >/dev/null 2>&1 && [[ "$os_name" != "windows" ]]; then
		install -m 0755 "$src" "$dest"
	else
		cp "$src" "$dest"
		chmod 0755 "$dest" 2>/dev/null || true
	fi

	if [[ "$os_name" == "windows" ]]; then
		ensure_path_windows "$install_dir"
	else
		ensure_path_unix "$install_dir"
	fi

	printf 'Installed %s to %s\n' "$binary_basename" "$dest"
}

install_binary
