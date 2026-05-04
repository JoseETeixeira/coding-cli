package assets

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/repos"
)

func TestRenderTemplateSubstitutesHarness(t *testing.T) {
	t.Parallel()

	rendered := string(RenderTemplate([]byte("python3 -m mempalace hook run --harness copilot"), "batman", "batman.agent.md"))
	if !strings.Contains(rendered, "--harness batman") {
		t.Fatalf("rendered = %q", rendered)
	}
}

func TestInsertManagedBlockReplacesExistingContent(t *testing.T) {
	t.Parallel()

	existing := "before\n<!-- freighthero:start -->\nold\n<!-- freighthero:end -->\nafter\n"
	updated := InsertManagedBlock(existing, "new")
	if strings.Contains(updated, "old") {
		t.Fatalf("updated block still contains old content: %q", updated)
	}
	if !strings.Contains(updated, "new") {
		t.Fatalf("updated block missing new content: %q", updated)
	}
}

func TestSyncAssetsCreatesBackupAndCopiesSkills(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	createAssetFixture(t, root)
	layout := repos.RepoLayout{CodingCLI: filepath.Join(root, "coding-cli")}
	profile := host.HostProfile{
		Kind:            host.HostBatman,
		DisplayName:     "Batman",
		Harness:         "batman",
		UsesVSCodeRoots: true,
		Roots: host.HostRoots{
			PromptDir:      filepath.Join(root, "user", "prompts"),
			InstructionDir: filepath.Join(root, "user", "prompts"),
			AgentDir:       filepath.Join(root, "user", "prompts"),
			SkillDir:       filepath.Join(root, "user", "skills"),
		},
	}

	destination := filepath.Join(profile.Roots.AgentDir, "batman.agent.md")
	if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.WriteFile(destination, []byte("old content"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	results, err := SyncAssets(layout, profile, SyncOptions{Force: true})
	if err != nil {
		t.Fatalf("SyncAssets returned error: %v", err)
	}
	if len(results) == 0 {
		t.Fatal("expected asset results")
	}
	if _, err := os.Stat(destination + ".bak"); err != nil {
		t.Fatalf("expected backup file, got error: %v", err)
	}
	skillPath := filepath.Join(profile.Roots.SkillDir, "example-skill", "SKILL.md")
	if _, err := os.Stat(skillPath); err != nil {
		t.Fatalf("expected copied skill file, got error: %v", err)
	}
	content, err := os.ReadFile(destination)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), "--harness batman") {
		t.Fatalf("expected harness substitution, got %q", string(content))
	}
}

func TestSyncAssetsSkipsConflictingFileWithoutForce(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	createAssetFixture(t, root)
	layout := repos.RepoLayout{CodingCLI: filepath.Join(root, "coding-cli")}
	profile := host.HostProfile{
		Kind:            host.HostBatman,
		DisplayName:     "Batman",
		Harness:         "batman",
		UsesVSCodeRoots: true,
		Roots: host.HostRoots{
			PromptDir:      filepath.Join(root, "user", "prompts"),
			InstructionDir: filepath.Join(root, "user", "prompts"),
			AgentDir:       filepath.Join(root, "user", "prompts"),
			SkillDir:       filepath.Join(root, "user", "skills"),
		},
	}

	destination := filepath.Join(profile.Roots.AgentDir, "batman.agent.md")
	if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.WriteFile(destination, []byte("old content"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	results, err := SyncAssets(layout, profile, SyncOptions{})
	if err != nil {
		t.Fatalf("SyncAssets returned error: %v", err)
	}

	foundConflict := false
	for _, result := range results {
		if result.Destination == destination {
			foundConflict = result.Action == "skipped-conflict"
		}
	}
	if !foundConflict {
		t.Fatal("expected batman.agent.md to be skipped as a conflict without --force")
	}
	content, err := os.ReadFile(destination)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if string(content) != "old content" {
		t.Fatalf("expected existing content to remain untouched, got %q", string(content))
	}
	if _, err := os.Stat(destination + ".bak"); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expected no backup file, got err=%v", err)
	}
}

func TestSyncAssetsMergesInstructionFileForCodex(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	createAssetFixture(t, root)
	layout := repos.RepoLayout{CodingCLI: filepath.Join(root, "coding-cli")}
	profile := host.HostProfile{
		Kind:        host.HostCodex,
		DisplayName: "Codex",
		Harness:     "codex",
		Roots: host.HostRoots{
			PromptDir:       filepath.Join(root, "codex", "prompts"),
			InstructionFile: filepath.Join(root, "codex", "AGENTS.md"),
			SkillDir:        filepath.Join(root, "codex", "skills"),
		},
	}

	results, err := SyncAssets(layout, profile, SyncOptions{})
	if err != nil {
		t.Fatalf("SyncAssets returned error: %v", err)
	}
	if len(results) == 0 {
		t.Fatal("expected results")
	}
	content, err := os.ReadFile(profile.Roots.InstructionFile)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), managedStart) {
		t.Fatalf("expected managed block in AGENTS.md, got %q", string(content))
	}
}

func createAssetFixture(t *testing.T, root string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Join(root, "coding-cli", "prompts"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, "coding-cli", "skills", "example-skill"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	files := map[string]string{
		filepath.Join(root, "coding-cli", "prompts", "demo.prompt.md"):            "prompt",
		filepath.Join(root, "coding-cli", "prompts", "demo.instructions.md"):      "instruction",
		filepath.Join(root, "coding-cli", "prompts", "batman.agent.md"):          "python3 -m mempalace hook run --harness copilot",
		filepath.Join(root, "coding-cli", "skills", "example-skill", "SKILL.md"): "skill",
	}
	for path, content := range files {
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatalf("WriteFile %s returned error: %v", path, err)
		}
	}
}