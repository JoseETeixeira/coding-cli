package codingcli

import (
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/coding-cli/coding-cli/internal/output"
)

func mkdirAll(t *testing.T, path string) error {
	t.Helper()
	return os.MkdirAll(path, 0o755)
}

func writeFile(t *testing.T, path string, body string) error {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(body), 0o644)
}

func newQuietDeps() Dependencies {
	return Dependencies{Logger: output.New(io.Discard, io.Discard, false)}
}

func TestBuildIndexingTargetWhenCwdIsWorkspaceRoot(t *testing.T) {
	t.Parallel()

	root := filepath.Join("workspaces", "demo")
	target := buildIndexingTarget(root, root, newQuietDeps())

	if len(target.Projects) != 0 || len(target.ProjectPaths) != 0 {
		t.Fatalf("expected empty target (legacy auto-discover), got %+v", target)
	}
}

func TestBuildIndexingTargetWhenCwdIsTopLevelProject(t *testing.T) {
	t.Parallel()

	root := filepath.Join("workspaces", "demo")
	cwd := filepath.Join(root, "project-a")
	target := buildIndexingTarget(root, cwd, newQuietDeps())

	if len(target.ProjectPaths) != 0 {
		t.Fatalf("expected no absolute project paths, got %+v", target.ProjectPaths)
	}
	if len(target.Projects) != 1 || target.Projects[0] != "project-a" {
		t.Fatalf("expected Projects=[project-a], got %+v", target.Projects)
	}
}

func TestBuildIndexingTargetWhenCwdIsDeepInsideProject(t *testing.T) {
	t.Parallel()

	root := filepath.Join("workspaces", "demo")
	cwd := filepath.Join(root, "project-a", "src", "handlers")
	target := buildIndexingTarget(root, cwd, newQuietDeps())

	if len(target.Projects) != 1 || target.Projects[0] != "project-a" {
		t.Fatalf("expected Projects=[project-a] (top-level ancestor), got %+v", target.Projects)
	}
}

func TestBuildIndexingTargetWhenCwdIsOutsideWorkspace(t *testing.T) {
	t.Parallel()

	root := filepath.Join("workspaces", "demo")
	cwd := filepath.Join("totally", "elsewhere", "side-project")
	target := buildIndexingTarget(root, cwd, newQuietDeps())

	if len(target.Projects) != 0 {
		t.Fatalf("expected no relative Projects for outside-workspace cwd, got %+v", target.Projects)
	}
	if len(target.ProjectPaths) != 1 {
		t.Fatalf("expected exactly 1 ProjectPaths entry, got %+v", target.ProjectPaths)
	}
	entry := target.ProjectPaths[0]
	if !strings.HasPrefix(entry.Name, "side-project-") {
		t.Fatalf("expected display name to start with %q, got %q", "side-project-", entry.Name)
	}
	if entry.Path != cwd {
		t.Fatalf("ProjectPaths[0].Path = %q, want %q", entry.Path, cwd)
	}
}

func TestExternalProjectNameIsStableAcrossCalls(t *testing.T) {
	t.Parallel()

	a := externalProjectName(filepath.Join("foo", "bar", "myproj"))
	b := externalProjectName(filepath.Join("foo", "bar", "myproj"))
	if a != b {
		t.Fatalf("externalProjectName not stable: %q vs %q", a, b)
	}
}

func TestExternalProjectNameDiffersForDifferentPaths(t *testing.T) {
	t.Parallel()

	a := externalProjectName(filepath.Join("foo", "bar", "myproj"))
	b := externalProjectName(filepath.Join("baz", "qux", "myproj"))
	if a == b {
		t.Fatalf("externalProjectName collided for distinct absolute paths: %q", a)
	}
	if !strings.HasPrefix(a, "myproj-") || !strings.HasPrefix(b, "myproj-") {
		t.Fatalf("both names should retain the basename prefix, got %q and %q", a, b)
	}
}

func TestResolveIndexingWorkspaceFlagWins(t *testing.T) {
	t.Parallel()

	workspace := t.TempDir()
	codingCLI := filepath.Join(workspace, "coding-cli")
	if err := mkdirAll(t, codingCLI); err != nil {
		t.Fatal(err)
	}

	layout, source, err := resolveIndexingWorkspace(workspace, t.TempDir())
	if err != nil {
		t.Fatalf("resolveIndexingWorkspace returned error: %v", err)
	}
	if source != "--workspace-root" {
		t.Fatalf("source = %q, want --workspace-root", source)
	}
	if layout.Root != workspace {
		t.Fatalf("layout.Root = %q, want %q", layout.Root, workspace)
	}
}

func TestResolveIndexingWorkspaceCwdAncestorWins(t *testing.T) {
	t.Parallel()

	workspace := t.TempDir()
	codingCLI := filepath.Join(workspace, "coding-cli")
	cwd := filepath.Join(workspace, "project-a", "src")
	for _, dir := range []string{codingCLI, cwd} {
		if err := mkdirAll(t, dir); err != nil {
			t.Fatal(err)
		}
	}

	layout, source, err := resolveIndexingWorkspace("", cwd)
	if err != nil {
		t.Fatalf("resolveIndexingWorkspace returned error: %v", err)
	}
	if source != "cwd ancestry" {
		t.Fatalf("source = %q, want cwd ancestry", source)
	}
	if layout.Root != workspace {
		t.Fatalf("layout.Root = %q, want %q", layout.Root, workspace)
	}
}

func TestResolveIndexingWorkspacePersistedFallback(t *testing.T) {
	workspace := t.TempDir()
	codingCLI := filepath.Join(workspace, "coding-cli")
	if err := mkdirAll(t, codingCLI); err != nil {
		t.Fatal(err)
	}

	stateFile := filepath.Join(t.TempDir(), "state.json")
	t.Setenv("CODING_CLI_STATE_FILE", stateFile)
	// Persist the workspace as the default.
	if err := writeFile(t, stateFile, `{"default_workspace_root":"`+filepath.ToSlash(workspace)+`"}`); err != nil {
		t.Fatal(err)
	}

	// cwd is entirely unrelated.
	unrelated := t.TempDir()
	layout, source, err := resolveIndexingWorkspace("", unrelated)
	if err != nil {
		t.Fatalf("resolveIndexingWorkspace returned error: %v", err)
	}
	if source != "persisted default" {
		t.Fatalf("source = %q, want persisted default", source)
	}
	if layout.Root != workspace {
		t.Fatalf("layout.Root = %q, want %q", layout.Root, workspace)
	}
}

func TestResolveIndexingWorkspaceFailsWithoutPersistedDefault(t *testing.T) {
	stateFile := filepath.Join(t.TempDir(), "missing.json")
	t.Setenv("CODING_CLI_STATE_FILE", stateFile)

	unrelated := t.TempDir()
	if _, _, err := resolveIndexingWorkspace("", unrelated); err == nil {
		t.Fatal("expected error when cwd has no workspace ancestor and no persisted default")
	}
}
