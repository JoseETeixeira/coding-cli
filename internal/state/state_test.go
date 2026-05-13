package state

import (
	"os"
	"path/filepath"
	"testing"
)

func TestSaveAndLoadRoundtrip(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("CODING_CLI_STATE_FILE", filepath.Join(dir, "state.json"))

	if err := SetDefaultWorkspaceRoot("/abs/path/to/workspace"); err != nil {
		t.Fatalf("SetDefaultWorkspaceRoot returned error: %v", err)
	}

	root, ok, err := DefaultWorkspaceRoot()
	if err != nil {
		t.Fatalf("DefaultWorkspaceRoot returned error: %v", err)
	}
	if !ok {
		t.Fatal("expected DefaultWorkspaceRoot to be set after save")
	}
	if root != "/abs/path/to/workspace" {
		t.Fatalf("DefaultWorkspaceRoot = %q, want %q", root, "/abs/path/to/workspace")
	}
}

func TestLoadReturnsFalseWhenMissing(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("CODING_CLI_STATE_FILE", filepath.Join(dir, "missing.json"))

	got, ok, err := Load()
	if err != nil {
		t.Fatalf("Load returned error: %v", err)
	}
	if ok {
		t.Fatalf("Load returned ok=true for missing file; got=%+v", got)
	}
}

func TestSaveCreatesParentDirectory(t *testing.T) {
	dir := t.TempDir()
	nested := filepath.Join(dir, "a", "b", "c", "state.json")
	t.Setenv("CODING_CLI_STATE_FILE", nested)

	if err := Save(State{DefaultWorkspaceRoot: "/x"}); err != nil {
		t.Fatalf("Save returned error: %v", err)
	}
	if _, err := os.Stat(nested); err != nil {
		t.Fatalf("expected state file at %s, got error: %v", nested, err)
	}
}

func TestPathRespectsStateDirOverride(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("CODING_CLI_STATE_FILE", "")
	t.Setenv("CODING_CLI_STATE_DIR", dir)

	got, err := Path()
	if err != nil {
		t.Fatalf("Path returned error: %v", err)
	}
	want := filepath.Join(dir, "state.json")
	if got != want {
		t.Fatalf("Path = %q, want %q", got, want)
	}
}
