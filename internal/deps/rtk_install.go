package deps

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/coding-cli/coding-cli/internal/runner"
)

const githubAPIBase = "https://api.github.com"

type githubRelease struct {
	Assets []githubReleaseAsset `json:"assets"`
}

type githubReleaseAsset struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
}

func installRTK(ctx context.Context, _ runner.ProcessRunner) error {
	assetName, err := rtkAssetName(runtime.GOOS, runtime.GOARCH)
	if err != nil {
		return err
	}

	installDir, err := rtkInstallDir()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(installDir, 0o755); err != nil {
		return fmt.Errorf("create rtk install directory %s: %w", installDir, err)
	}

	assetURL, err := latestGitHubAssetURL(ctx, "rtk-ai", "rtk", assetName)
	if err != nil {
		return err
	}

	payload, err := downloadReleaseAsset(ctx, assetURL)
	if err != nil {
		return err
	}

	binaryName := "rtk"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}
	binary, err := extractReleaseBinary(payload, assetName, binaryName)
	if err != nil {
		return err
	}

	destination := filepath.Join(installDir, binaryName)
	if err := os.WriteFile(destination, binary, 0o755); err != nil {
		return fmt.Errorf("write rtk binary to %s: %w", destination, err)
	}

	return ensureInstallDirOnPath(ctx, installDir)
}

func rtkAssetName(goos string, goarch string) (string, error) {
	switch goos {
	case "darwin":
		switch goarch {
		case "arm64":
			return "rtk-aarch64-apple-darwin.tar.gz", nil
		case "amd64":
			return "rtk-x86_64-apple-darwin.tar.gz", nil
		}
	case "linux":
		switch goarch {
		case "arm64":
			return "rtk-aarch64-unknown-linux-gnu.tar.gz", nil
		case "amd64":
			return "rtk-x86_64-unknown-linux-musl.tar.gz", nil
		}
	case "windows":
		switch goarch {
		case "amd64":
			return "rtk-x86_64-pc-windows-msvc.zip", nil
		}
	}

	return "", fmt.Errorf("unsupported rtk platform %s/%s", goos, goarch)
}

func rtkInstallDir() (string, error) {
	for _, candidate := range rtkInstallCandidates() {
		if candidate == "" {
			continue
		}
		if !pathContains(candidate) {
			continue
		}
		if err := ensureWritableDir(candidate); err == nil {
			return candidate, nil
		}
	}

	for _, candidate := range rtkInstallCandidates() {
		if candidate == "" {
			continue
		}
		if err := ensureWritableDir(candidate); err == nil {
			return candidate, nil
		}
	}

	return "", fmt.Errorf("no writable install directory found for rtk")
}

func rtkInstallCandidates() []string {
	candidates := make([]string, 0, 4)
	if executable, err := os.Executable(); err == nil {
		executableDir := filepath.Dir(executable)
		if !strings.HasPrefix(executableDir, os.TempDir()) {
			candidates = append(candidates, executableDir)
		}
	}

	homeDir, err := os.UserHomeDir()
	if err != nil {
		return uniqueStrings(candidates)
	}

	switch runtime.GOOS {
	case "windows":
		if localAppData := os.Getenv("LOCALAPPDATA"); localAppData != "" {
			candidates = append(candidates, filepath.Join(localAppData, "Programs", "coding-cli", "bin"))
		}
		candidates = append(candidates, filepath.Join(homeDir, "bin"))
	default:
		candidates = append(candidates, filepath.Join(homeDir, ".local", "bin"), filepath.Join(homeDir, "bin"))
	}

	return uniqueStrings(candidates)
}

func latestGitHubAssetURL(ctx context.Context, owner string, repo string, assetName string) (string, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, fmt.Sprintf("%s/repos/%s/%s/releases/latest", githubAPIBase, owner, repo), nil)
	if err != nil {
		return "", fmt.Errorf("create GitHub release request: %w", err)
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("User-Agent", "coding-cli")
	if token := githubToken(); token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}

	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return "", fmt.Errorf("fetch latest rtk release metadata: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return "", fmt.Errorf("fetch latest rtk release metadata: %s: %s", response.Status, strings.TrimSpace(string(body)))
	}

	var release githubRelease
	if err := json.NewDecoder(response.Body).Decode(&release); err != nil {
		return "", fmt.Errorf("decode latest rtk release metadata: %w", err)
	}

	for _, asset := range release.Assets {
		if asset.Name == assetName {
			return asset.BrowserDownloadURL, nil
		}
	}

	return "", fmt.Errorf("rtk release asset %s not found", assetName)
}

func downloadReleaseAsset(ctx context.Context, assetURL string) ([]byte, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, assetURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create release asset request: %w", err)
	}
	request.Header.Set("User-Agent", "coding-cli")
	if token := githubToken(); token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}

	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return nil, fmt.Errorf("download release asset: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return nil, fmt.Errorf("download release asset: %s: %s", response.Status, strings.TrimSpace(string(body)))
	}

	payload, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read release asset: %w", err)
	}

	return payload, nil
}

func extractReleaseBinary(payload []byte, assetName string, binaryName string) ([]byte, error) {
	switch {
	case strings.HasSuffix(assetName, ".tar.gz"):
		return extractBinaryFromTarGz(payload, binaryName)
	case strings.HasSuffix(assetName, ".zip"):
		return extractBinaryFromZip(payload, binaryName)
	default:
		return nil, fmt.Errorf("unsupported archive format for %s", assetName)
	}
}

func extractBinaryFromTarGz(payload []byte, binaryName string) ([]byte, error) {
	gzipReader, err := gzip.NewReader(bytes.NewReader(payload))
	if err != nil {
		return nil, fmt.Errorf("open tar.gz archive: %w", err)
	}
	defer gzipReader.Close()

	tarReader := tar.NewReader(gzipReader)
	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read tar.gz archive: %w", err)
		}
		if header.Typeflag != tar.TypeReg {
			continue
		}
		if filepath.Base(header.Name) != binaryName {
			continue
		}

		binary, err := io.ReadAll(tarReader)
		if err != nil {
			return nil, fmt.Errorf("read %s from tar.gz archive: %w", binaryName, err)
		}
		return binary, nil
	}

	return nil, fmt.Errorf("binary %s not found in tar.gz archive", binaryName)
}

func extractBinaryFromZip(payload []byte, binaryName string) ([]byte, error) {
	zipReader, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return nil, fmt.Errorf("open zip archive: %w", err)
	}

	for _, file := range zipReader.File {
		if filepath.Base(file.Name) != binaryName {
			continue
		}
		reader, err := file.Open()
		if err != nil {
			return nil, fmt.Errorf("open %s from zip archive: %w", binaryName, err)
		}
		defer reader.Close()

		binary, err := io.ReadAll(reader)
		if err != nil {
			return nil, fmt.Errorf("read %s from zip archive: %w", binaryName, err)
		}
		return binary, nil
	}

	return nil, fmt.Errorf("binary %s not found in zip archive", binaryName)
}

func ensureWritableDir(path string) error {
	if err := os.MkdirAll(path, 0o755); err != nil {
		return err
	}

	probe, err := os.CreateTemp(path, ".coding-cli-probe-*")
	if err != nil {
		return err
	}
	probePath := probe.Name()
	if err := probe.Close(); err != nil {
		return err
	}
	return os.Remove(probePath)
}

func pathContains(candidate string) bool {
	for _, part := range filepath.SplitList(os.Getenv("PATH")) {
		if filepath.Clean(part) == filepath.Clean(candidate) {
			return true
		}
	}

	return false
}

func prependPath(path string) {
	parts := filepath.SplitList(os.Getenv("PATH"))
	filtered := []string{path}
	for _, part := range parts {
		if part == "" {
			continue
		}
		if filepath.Clean(part) == filepath.Clean(path) {
			continue
		}
		filtered = append(filtered, part)
	}
	if len(filtered) == 1 {
		_ = os.Setenv("PATH", path)
		return
	}
	_ = os.Setenv("PATH", strings.Join(filtered, string(os.PathListSeparator)))
}

func ensureInstallDirOnPath(ctx context.Context, installDir string) error {
	alreadyPresent := pathContains(installDir)
	prependPath(installDir)
	if alreadyPresent {
		return nil
	}

	if runtime.GOOS == "windows" {
		return persistWindowsUserPath(ctx, installDir)
	}

	return persistUnixShellPath(installDir)
}

func persistUnixShellPath(installDir string) error {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("resolve home directory for PATH update: %w", err)
	}

	profilePath, exportLine := unixShellProfile(homeDir, installDir)
	existing, err := os.ReadFile(profilePath)
	if err == nil && strings.Contains(string(existing), exportLine) {
		return nil
	}
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("read shell profile %s: %w", profilePath, err)
	}

	if err := os.MkdirAll(filepath.Dir(profilePath), 0o755); err != nil {
		return fmt.Errorf("create shell profile directory for %s: %w", profilePath, err)
	}

	file, err := os.OpenFile(profilePath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("open shell profile %s: %w", profilePath, err)
	}
	defer file.Close()

	block := "\n# Added by coding-cli for local tool installs\n" + exportLine + "\n"
	if _, err := file.WriteString(block); err != nil {
		return fmt.Errorf("update shell profile %s: %w", profilePath, err)
	}

	return nil
}

func unixShellProfile(homeDir string, installDir string) (string, string) {
	shell := strings.ToLower(filepath.Base(os.Getenv("SHELL")))
	switch shell {
	case "fish":
		return filepath.Join(homeDir, ".config", "fish", "config.fish"), fmt.Sprintf("fish_add_path -g %q", installDir)
	case "bash":
		if runtime.GOOS == "darwin" {
			return filepath.Join(homeDir, ".bash_profile"), fmt.Sprintf("export PATH=%q:$PATH", installDir)
		}
		return filepath.Join(homeDir, ".bashrc"), fmt.Sprintf("export PATH=%q:$PATH", installDir)
	default:
		return filepath.Join(homeDir, ".zshrc"), fmt.Sprintf("export PATH=%q:$PATH", installDir)
	}
}

func persistWindowsUserPath(ctx context.Context, installDir string) error {
	script := fmt.Sprintf(`$dir = %q; $current = [Environment]::GetEnvironmentVariable("Path", "User"); if ([string]::IsNullOrWhiteSpace($current)) { $new = $dir } elseif (($current -split ';') -contains $dir) { exit 0 } else { $new = $dir + ';' + $current }; [Environment]::SetEnvironmentVariable("Path", $new, "User")`, installDir)
	command := exec.CommandContext(ctx, "powershell", "-NoProfile", "-NonInteractive", "-Command", script)
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("persist rtk install directory in user PATH: %w: %s", err, strings.TrimSpace(string(output)))
	}

	return nil
}

func githubToken() string {
	for _, key := range []string{"GITHUB_PAT_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"} {
		if value := strings.TrimSpace(os.Getenv(key)); value != "" {
			return value
		}
	}

	return ""
}

func uniqueStrings(values []string) []string {
	seen := map[string]struct{}{}
	result := make([]string, 0, len(values))
	for _, value := range values {
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}

	return result
}
