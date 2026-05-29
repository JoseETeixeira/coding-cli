// Package update downloads a coding-cli release and refreshes the local
// install: it overlays the shipped prompts/skills/hooks onto the workspace
// source tree and optionally self-replaces the running binary.
//
// Network access is funneled through Client, whose API and download base URLs
// are overridable so the resolution/extraction logic can be exercised against
// an httptest server without hitting GitHub.
package update

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
)

const (
	// DefaultOwner and DefaultRepo point at the public release repository that
	// install.sh / install.ps1 also resolve releases from.
	DefaultOwner = "JoseETeixeira"
	DefaultRepo  = "coding-cli"
	// BinaryName is the released binary basename (no extension).
	BinaryName = "coding-cli"

	defaultAPIBase      = "https://api.github.com"
	defaultDownloadBase = "https://github.com"
	githubAPIVersion    = "2026-03-10"
)

// AssetSubdirs are the source-tree directories the updater overlays from a
// release tarball: shipped prompts, skills, and the Claude Code hook scripts.
var AssetSubdirs = []string{"prompts", "skills", ".claude"}

// Client talks to the GitHub release API and download host.
type Client struct {
	HTTP         *http.Client
	APIBase      string
	DownloadBase string
	Token        string
}

// NewClient returns a Client configured for the public GitHub endpoints with a
// token resolved from the environment (needed only for private repositories).
func NewClient() *Client {
	return &Client{
		HTTP:         &http.Client{Timeout: 90 * time.Second},
		APIBase:      defaultAPIBase,
		DownloadBase: defaultDownloadBase,
		Token:        TokenFromEnv(),
	}
}

// TokenFromEnv mirrors install.sh: GITHUB_PAT_TOKEN > GH_TOKEN > GITHUB_TOKEN.
func TokenFromEnv() string {
	for _, name := range []string{"GITHUB_PAT_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"} {
		if value := strings.TrimSpace(os.Getenv(name)); value != "" {
			return value
		}
	}
	return ""
}

func (c *Client) get(ctx context.Context, url string, accept string) (*http.Response, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, clierrors.Wrap(clierrors.KindValidation, fmt.Sprintf("build request for %s", url), err)
	}
	if accept != "" {
		request.Header.Set("Accept", accept)
	}
	request.Header.Set("X-GitHub-Api-Version", githubAPIVersion)
	if c.Token != "" {
		request.Header.Set("Authorization", "Bearer "+c.Token)
	}
	response, err := c.HTTP.Do(request)
	if err != nil {
		return nil, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("request %s", url), err)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 512))
		_ = response.Body.Close()
		hint := ""
		if response.StatusCode == http.StatusNotFound && c.Token == "" {
			hint = " (if the repository is private, set GITHUB_PAT_TOKEN, GH_TOKEN, or GITHUB_TOKEN)"
		}
		return nil, clierrors.New(clierrors.KindConfig,
			fmt.Sprintf("GET %s returned %d%s: %s", url, response.StatusCode, hint, strings.TrimSpace(string(body))))
	}
	return response, nil
}

// LatestTag resolves the tag_name of the latest published release.
func (c *Client) LatestTag(ctx context.Context, owner, repo string) (string, error) {
	url := fmt.Sprintf("%s/repos/%s/%s/releases/latest", strings.TrimRight(c.APIBase, "/"), owner, repo)
	response, err := c.get(ctx, url, "application/vnd.github+json")
	if err != nil {
		return "", err
	}
	defer func() { _ = response.Body.Close() }()

	var payload struct {
		TagName string `json:"tag_name"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return "", clierrors.Wrap(clierrors.KindConfig, "decode latest release", err)
	}
	if strings.TrimSpace(payload.TagName) == "" {
		return "", clierrors.New(clierrors.KindConfig, fmt.Sprintf("could not resolve latest release tag from %s", url))
	}
	return payload.TagName, nil
}

// DownloadSource fetches the source tarball for tag and extracts it under
// destDir, returning the extracted repository root (the single top-level
// directory GitHub names "<repo>-<tag-without-v>").
func (c *Client) DownloadSource(ctx context.Context, owner, repo, tag, destDir string) (string, error) {
	url := fmt.Sprintf("%s/%s/%s/archive/refs/tags/%s.tar.gz", strings.TrimRight(c.DownloadBase, "/"), owner, repo, tag)
	response, err := c.get(ctx, url, "")
	if err != nil {
		return "", err
	}
	defer func() { _ = response.Body.Close() }()

	if err := extractTarGz(response.Body, destDir); err != nil {
		return "", err
	}
	return singleChildDir(destDir)
}

// DownloadBinary fetches the release binary asset for the current OS/arch and
// extracts it under destDir, returning the path to the executable.
func (c *Client) DownloadBinary(ctx context.Context, owner, repo, tag, destDir string) (string, error) {
	asset := AssetName(runtime.GOOS, runtime.GOARCH)
	url := fmt.Sprintf("%s/%s/%s/releases/download/%s/%s", strings.TrimRight(c.DownloadBase, "/"), owner, repo, tag, asset)
	response, err := c.get(ctx, url, "")
	if err != nil {
		return "", err
	}
	defer func() { _ = response.Body.Close() }()

	binaryName := BinaryName
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
		archivePath := filepath.Join(destDir, asset)
		if err := writeStreamToFile(response.Body, archivePath); err != nil {
			return "", err
		}
		if err := extractZip(archivePath, destDir); err != nil {
			return "", err
		}
	} else if err := extractTarGz(response.Body, destDir); err != nil {
		return "", err
	}

	binaryPath := filepath.Join(destDir, binaryName)
	if _, err := os.Stat(binaryPath); err != nil {
		return "", clierrors.New(clierrors.KindConfig, fmt.Sprintf("release asset %s did not contain %s", asset, binaryName))
	}
	return binaryPath, nil
}

// AssetName returns the release archive name for an OS/arch pair, matching the
// names produced by build.sh / build.ps1.
func AssetName(goos, goarch string) string {
	if goos == "windows" {
		return fmt.Sprintf("%s_%s_%s.zip", BinaryName, goos, goarch)
	}
	return fmt.Sprintf("%s_%s_%s.tar.gz", BinaryName, goos, goarch)
}

// OverlayAssets copies each subdir from srcRoot over the matching directory in
// codingCLIDir, creating files and overwriting existing ones. Runtime state not
// present in the release (e.g. query-code-mcp/.venv) is left untouched because
// only the named subdirs are walked. Returns the subdirs that were applied.
func OverlayAssets(srcRoot, codingCLIDir string, subdirs []string) ([]string, error) {
	applied := make([]string, 0, len(subdirs))
	for _, subdir := range subdirs {
		source := filepath.Join(srcRoot, subdir)
		info, err := os.Stat(source)
		if err != nil || !info.IsDir() {
			// A release may legitimately omit a subdir; skip silently.
			continue
		}
		if err := copyTree(source, filepath.Join(codingCLIDir, subdir)); err != nil {
			return applied, err
		}
		applied = append(applied, subdir)
	}
	return applied, nil
}

// ReplaceExecutable atomically swaps the currently running executable with the
// file at newBinaryPath. On Windows a running image cannot be deleted but can
// be renamed aside, so the current binary is moved to "<exe>.old" first.
func ReplaceExecutable(newBinaryPath string) error {
	current, err := os.Executable()
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, "resolve current executable", err)
	}
	if resolved, symErr := filepath.EvalSymlinks(current); symErr == nil {
		current = resolved
	}
	return replaceFile(current, newBinaryPath)
}

// replaceFile swaps the file at current with the contents of newBinaryPath via
// a stage-rename-rename dance: on Windows a running image cannot be deleted but
// can be renamed aside, so current is moved to "<file>.old" before the new file
// takes its place.
func replaceFile(current, newBinaryPath string) error {
	data, err := os.ReadFile(newBinaryPath)
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, "read downloaded binary", err)
	}

	staged := current + ".new"
	if err := os.WriteFile(staged, data, 0o755); err != nil {
		return clierrors.Wrap(clierrors.KindConfig, "stage new binary", err)
	}

	backup := current + ".old"
	_ = os.Remove(backup)
	if err := os.Rename(current, backup); err != nil {
		_ = os.Remove(staged)
		return clierrors.Wrap(clierrors.KindConfig, "move current binary aside", err)
	}
	if err := os.Rename(staged, current); err != nil {
		// Best-effort rollback so the install is never left without a binary.
		_ = os.Rename(backup, current)
		_ = os.Remove(staged)
		return clierrors.Wrap(clierrors.KindConfig, "install new binary", err)
	}
	// The old image may still be locked while running; remove best-effort.
	_ = os.Remove(backup)
	return nil
}

// IsNewer reports whether the released tag is newer than the installed version.
// A "dev" (unversioned) install is always considered out of date. Unparsable
// versions fall back to a string inequality so the update still proceeds when
// the two differ.
func IsNewer(latest, current string) bool {
	if current == "" || current == "dev" {
		return true
	}
	lat, latPre, latOK := parseSemver(latest)
	cur, curPre, curOK := parseSemver(current)
	if !latOK || !curOK {
		// Undefined ordering for non-semver tags: proceed with the update when
		// the tags differ, stay put when they are identical.
		return normalizeTag(latest) != normalizeTag(current)
	}
	for i := 0; i < 3; i++ {
		if lat[i] != cur[i] {
			return lat[i] > cur[i]
		}
	}
	// Same base version. A clean release outranks a pre-release/dev build of the
	// same base (e.g. v0.3.0 > v0.3.0-rc1 > v0.3.0-5-gSHA).
	if latPre == curPre {
		return false
	}
	if latPre == "" {
		return true
	}
	if curPre == "" {
		return false
	}
	return latPre > curPre
}

func normalizeTag(tag string) string {
	return strings.TrimPrefix(strings.TrimSpace(tag), "v")
}

// parseSemver splits a tag into its MAJOR.MINOR.PATCH base and any pre-release/
// build suffix (the text after the first '-' or '+' in the patch component).
func parseSemver(tag string) (base [3]int, pre string, ok bool) {
	parts := strings.SplitN(normalizeTag(tag), ".", 3)
	if len(parts) != 3 {
		return base, "", false
	}
	for i, part := range parts {
		if i == 2 {
			if idx := strings.IndexAny(part, "-+"); idx >= 0 {
				pre = part[idx+1:]
				part = part[:idx]
			}
		}
		value, err := strconv.Atoi(part)
		if err != nil {
			return base, "", false
		}
		base[i] = value
	}
	return base, pre, true
}

// --- archive + filesystem helpers -----------------------------------------

func extractTarGz(reader io.Reader, dest string) error {
	gzReader, err := gzip.NewReader(reader)
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, "open gzip stream", err)
	}
	defer func() { _ = gzReader.Close() }()

	tarReader := tar.NewReader(gzReader)
	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return clierrors.Wrap(clierrors.KindConfig, "read tar entry", err)
		}
		target, err := safeJoin(dest, header.Name)
		if err != nil {
			return err
		}
		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0o755); err != nil {
				return clierrors.Wrap(clierrors.KindConfig, "create directory", err)
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return clierrors.Wrap(clierrors.KindConfig, "create parent directory", err)
			}
			mode := os.FileMode(header.Mode)
			if mode == 0 {
				mode = 0o644
			}
			if err := writeFileFrom(tarReader, target, mode); err != nil {
				return err
			}
		}
	}
}

func extractZip(archivePath, dest string) error {
	reader, err := zip.OpenReader(archivePath)
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, "open zip archive", err)
	}
	defer func() { _ = reader.Close() }()

	for _, file := range reader.File {
		target, err := safeJoin(dest, file.Name)
		if err != nil {
			return err
		}
		if file.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o755); err != nil {
				return clierrors.Wrap(clierrors.KindConfig, "create directory", err)
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return clierrors.Wrap(clierrors.KindConfig, "create parent directory", err)
		}
		opened, err := file.Open()
		if err != nil {
			return clierrors.Wrap(clierrors.KindConfig, "open zip entry", err)
		}
		mode := file.Mode()
		if mode == 0 {
			mode = 0o644
		}
		writeErr := writeFileFrom(opened, target, mode)
		_ = opened.Close()
		if writeErr != nil {
			return writeErr
		}
	}
	return nil
}

func copyTree(source, destination string) error {
	return filepath.Walk(source, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, relative)
		if info.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		opened, err := os.Open(path)
		if err != nil {
			return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("open %s", path), err)
		}
		mode := info.Mode()
		if mode == 0 {
			mode = 0o644
		}
		writeErr := writeFileFrom(opened, target, mode)
		_ = opened.Close()
		return writeErr
	})
}

func writeFileFrom(reader io.Reader, target string, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return clierrors.Wrap(clierrors.KindConfig, "create parent directory", err)
	}
	out, err := os.OpenFile(target, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, mode)
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("create %s", target), err)
	}
	if _, err := io.Copy(out, reader); err != nil {
		_ = out.Close()
		return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("write %s", target), err)
	}
	return out.Close()
}

func writeStreamToFile(reader io.Reader, target string) error {
	return writeFileFrom(reader, target, 0o644)
}

// safeJoin joins dest and name, rejecting entries that would escape dest via
// "../" traversal or absolute paths (zip-slip / tar-slip guard).
func safeJoin(dest, name string) (string, error) {
	target := filepath.Join(dest, filepath.FromSlash(name))
	rel, err := filepath.Rel(dest, target)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", clierrors.New(clierrors.KindConfig, fmt.Sprintf("archive entry %q escapes destination", name))
	}
	return target, nil
}

func singleChildDir(dir string) (string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return "", clierrors.Wrap(clierrors.KindConfig, "read extracted archive", err)
	}
	var found string
	for _, entry := range entries {
		if entry.IsDir() {
			if found != "" {
				return "", clierrors.New(clierrors.KindConfig, "release archive contained multiple top-level directories")
			}
			found = filepath.Join(dir, entry.Name())
		}
	}
	if found == "" {
		return "", clierrors.New(clierrors.KindConfig, "release archive contained no source directory")
	}
	return found, nil
}
