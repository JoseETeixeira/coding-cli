package update

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestIsNewer(t *testing.T) {
	cases := []struct {
		latest, current string
		want            bool
	}{
		{"v0.3.0", "dev", true},
		{"v0.3.0", "", true},
		{"v0.3.0", "v0.2.0", true},
		{"v0.3.0", "v0.3.0", false},
		{"v0.2.9", "v0.3.0", false},
		{"0.3.1", "v0.3.0", true},
		{"v0.3.0", "v0.3.0-rc1", true},
		{"v0.3.0-rc1", "v0.3.0", false},
		{"weird", "weird", false},
		{"weird", "other", true},
	}
	for _, tc := range cases {
		if got := IsNewer(tc.latest, tc.current); got != tc.want {
			t.Errorf("IsNewer(%q,%q)=%v want %v", tc.latest, tc.current, got, tc.want)
		}
	}
}

func TestAssetName(t *testing.T) {
	if got := AssetName("windows", "amd64"); got != "coding-cli_windows_amd64.zip" {
		t.Errorf("windows asset = %q", got)
	}
	if got := AssetName("linux", "arm64"); got != "coding-cli_linux_arm64.tar.gz" {
		t.Errorf("linux asset = %q", got)
	}
}

func TestTokenFromEnv(t *testing.T) {
	t.Setenv("GITHUB_PAT_TOKEN", "")
	t.Setenv("GH_TOKEN", "")
	t.Setenv("GITHUB_TOKEN", "zzz")
	if got := TokenFromEnv(); got != "zzz" {
		t.Errorf("token = %q want zzz", got)
	}
	t.Setenv("GH_TOKEN", "yyy")
	if got := TokenFromEnv(); got != "yyy" {
		t.Errorf("token precedence = %q want yyy", got)
	}
}

func TestSafeJoinRejectsTraversal(t *testing.T) {
	dest := t.TempDir()
	if _, err := safeJoin(dest, "../escape.txt"); err == nil {
		t.Fatal("expected traversal entry to be rejected")
	}
	if _, err := safeJoin(dest, "ok/inside.txt"); err != nil {
		t.Fatalf("legit entry rejected: %v", err)
	}
}

// makeSourceTarGz builds an in-memory release source tarball whose single
// top-level dir mimics GitHub's "<repo>-<tag>" layout.
func makeSourceTarGz(t *testing.T, root string, files map[string]string) []byte {
	t.Helper()
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	// directory entry
	if err := tw.WriteHeader(&tar.Header{Name: root + "/", Typeflag: tar.TypeDir, Mode: 0o755}); err != nil {
		t.Fatal(err)
	}
	for name, content := range files {
		full := root + "/" + name
		if err := tw.WriteHeader(&tar.Header{Name: full, Typeflag: tar.TypeReg, Mode: 0o644, Size: int64(len(content))}); err != nil {
			t.Fatal(err)
		}
		if _, err := tw.Write([]byte(content)); err != nil {
			t.Fatal(err)
		}
	}
	if err := tw.Close(); err != nil {
		t.Fatal(err)
	}
	if err := gz.Close(); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func TestLatestTagAndDownloadSourceAndOverlay(t *testing.T) {
	const tag = "v0.3.0"
	srcTar := makeSourceTarGz(t, "coding-cli-0.3.0", map[string]string{
		"prompts/sample.prompt.md":     "PROMPT",
		"skills/foo/SKILL.md":          "SKILL",
		".claude/hooks/sample.sh":      "#!/usr/bin/env bash\n",
		"internal/ignore/notcopied.go": "package ignore",
	})

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/repos/acme/coding-cli/releases/latest":
			_, _ = w.Write([]byte(`{"tag_name":"` + tag + `"}`))
		case "/acme/coding-cli/archive/refs/tags/" + tag + ".tar.gz":
			_, _ = w.Write(srcTar)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client := &Client{HTTP: server.Client(), APIBase: server.URL, DownloadBase: server.URL}

	gotTag, err := client.LatestTag(context.Background(), "acme", "coding-cli")
	if err != nil {
		t.Fatalf("LatestTag: %v", err)
	}
	if gotTag != tag {
		t.Fatalf("tag = %q want %q", gotTag, tag)
	}

	tmp := t.TempDir()
	root, err := client.DownloadSource(context.Background(), "acme", "coding-cli", tag, tmp)
	if err != nil {
		t.Fatalf("DownloadSource: %v", err)
	}
	if filepath.Base(root) != "coding-cli-0.3.0" {
		t.Fatalf("extracted root = %q", root)
	}

	codingCLI := filepath.Join(t.TempDir(), "coding-cli")
	applied, err := OverlayAssets(root, codingCLI, AssetSubdirs)
	if err != nil {
		t.Fatalf("OverlayAssets: %v", err)
	}
	if len(applied) != 3 {
		t.Fatalf("applied = %v want prompts/skills/.claude", applied)
	}

	for path, want := range map[string]string{
		filepath.Join(codingCLI, "prompts", "sample.prompt.md"):   "PROMPT",
		filepath.Join(codingCLI, "skills", "foo", "SKILL.md"):     "SKILL",
		filepath.Join(codingCLI, ".claude", "hooks", "sample.sh"): "#!/usr/bin/env bash\n",
	} {
		got, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("read %s: %v", path, err)
		}
		if string(got) != want {
			t.Errorf("%s = %q want %q", path, got, want)
		}
	}

	// internal/ is not an asset subdir, so it must not be overlaid.
	if _, err := os.Stat(filepath.Join(codingCLI, "internal")); !os.IsNotExist(err) {
		t.Errorf("internal/ should not be overlaid, stat err = %v", err)
	}
}

func TestReplaceExecutableSwapsFile(t *testing.T) {
	// Simulate a binary swap against a temp file (not the test binary).
	dir := t.TempDir()
	current := filepath.Join(dir, "coding-cli-bin")
	if err := os.WriteFile(current, []byte("OLD"), 0o755); err != nil {
		t.Fatal(err)
	}
	newBin := filepath.Join(dir, "new")
	if err := os.WriteFile(newBin, []byte("NEW"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := replaceFile(current, newBin); err != nil {
		t.Fatalf("replaceFile: %v", err)
	}
	got, _ := os.ReadFile(current)
	if string(got) != "NEW" {
		t.Fatalf("after swap = %q want NEW", got)
	}
}
