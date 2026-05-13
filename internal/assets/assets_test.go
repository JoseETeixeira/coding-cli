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

	rendered := string(RenderTemplate([]byte("python3 -m mempalace hook run --harness {{MEMPALACE_HARNESS}}"), "codex", "batman.agent.md"))
	if !strings.Contains(rendered, "--harness codex") {
		t.Fatalf("rendered = %q", rendered)
	}
}

func TestRenderTemplateAppliesClaudeCodeTransforms(t *testing.T) {
	t.Parallel()

	input := "name: \"Batman Agent\"\n" +
		vscodeBatmanFrontmatterTools + "\n" +
		"hooks:\n" +
		"   Stop:\n" +
		"      - {type: command, command: \"python3 -m mempalace hook run --hook stop --harness {{MEMPALACE_HARNESS}}\", timeout: 30}\n" +
		"   PreCompact:\n" +
		"      - {type: command, command: \"python3 -m mempalace hook run --hook precompact --harness {{MEMPALACE_HARNESS}}\", timeout: 30}\n" +
		"Use #tool:vscode/askQuestions to clarify.\n" +
		"Run #tool:agent/runSubagent to research.\n"

	rendered := string(RenderTemplate([]byte(input), "claude-code", "batman.agent.md"))

	if !strings.Contains(rendered, "tools: [Bash,") {
		t.Fatalf("expected Claude Code tools list, got %q", rendered)
	}
	if !strings.Contains(rendered, "mcp__github__get_me") {
		t.Fatalf("expected GitHub tools in Claude Code tools list, got %q", rendered)
	}
	if !strings.Contains(rendered, `model: "opus"`) {
		t.Fatalf("model field should be preserved, got %q", rendered)
	}
	if strings.Contains(rendered, "vscode, execute") {
		t.Fatalf("VS Code tools should not be present, got %q", rendered)
	}
	if strings.Contains(rendered, "hooks:") {
		t.Fatalf("hooks block should be stripped for claude-code, got %q", rendered)
	}
	if strings.Contains(rendered, "#tool:vscode/askQuestions") {
		t.Fatalf("#tool:vscode/askQuestions should be replaced, got %q", rendered)
	}
	if strings.Contains(rendered, "#tool:agent/runSubagent") {
		t.Fatalf("#tool:agent/runSubagent should be replaced, got %q", rendered)
	}
	if !strings.Contains(rendered, "AskUserQuestion") {
		t.Fatalf("AskUserQuestion should be present, got %q", rendered)
	}
	if !strings.Contains(rendered, "Agent") {
		t.Fatalf("Agent should be present, got %q", rendered)
	}
	if strings.Contains(rendered, mempalaceHarnessPlaceholder) {
		t.Fatalf("harness placeholder should be resolved, got %q", rendered)
	}
}

func TestRenderTemplatePreservesVSCodeToolsForCopilot(t *testing.T) {
	t.Parallel()

	input := "name: \"Batman Agent\"\n" +
		vscodeBatmanFrontmatterTools + "\n" +
		"Use #tool:vscode/askQuestions to clarify.\n"

	rendered := string(RenderTemplate([]byte(input), "codex", "batman.agent.md"))

	if !strings.Contains(rendered, "#tool:vscode/askQuestions") {
		t.Fatalf("copilot render should preserve VS Code tool refs, got %q", rendered)
	}
	if !strings.Contains(rendered, "vscode, execute") {
		t.Fatalf("copilot render should preserve VS Code tools list, got %q", rendered)
	}
	if strings.Contains(rendered, `model: "opus"`) {
		t.Fatalf("copilot render must not inject model field, got %q", rendered)
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
		Harness:         "codex",
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
	if !strings.Contains(string(content), "--harness codex") {
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
		Harness:         "codex",
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

func TestSyncAssetsInstallsInstructionsForClaudeCode(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	promptsDir := filepath.Join(root, "coding-cli", "prompts")
	if err := os.MkdirAll(promptsDir, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, "coding-cli", "skills"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.WriteFile(filepath.Join(promptsDir, "batman.agent.md"), []byte("agent"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}
	if err := os.WriteFile(filepath.Join(promptsDir, "codeReview.instructions.md"), []byte("# Code Review"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	claudeRoot := filepath.Join(root, "claude")
	instructionFile := filepath.Join(claudeRoot, "CLAUDE.md")
	layout := repos.RepoLayout{CodingCLI: filepath.Join(root, "coding-cli")}
	profile := host.HostProfile{
		Kind:    host.HostClaudeCode,
		Harness: string(host.HostClaudeCode),
		Roots: host.HostRoots{
			AgentDir:        filepath.Join(claudeRoot, "agents"),
			InstructionDir:  claudeRoot,
			InstructionFile: instructionFile,
		},
	}

	if _, err := SyncAssets(layout, profile, SyncOptions{}); err != nil {
		t.Fatalf("SyncAssets returned error: %v", err)
	}

	// Individual instruction file must be installed to InstructionDir so Batman can read it explicitly.
	individualPath := filepath.Join(claudeRoot, "codeReview.instructions.md")
	if _, err := os.Stat(individualPath); err != nil {
		t.Fatalf("expected codeReview.instructions.md at %s, got error: %v", individualPath, err)
	}

	// Content must also be merged into CLAUDE.md.
	merged, err := os.ReadFile(instructionFile)
	if err != nil {
		t.Fatalf("ReadFile CLAUDE.md returned error: %v", err)
	}
	if !strings.Contains(string(merged), managedStart) {
		t.Fatalf("expected managed block in CLAUDE.md, got %q", string(merged))
	}
	if !strings.Contains(string(merged), "# Code Review") {
		t.Fatalf("expected instruction content in CLAUDE.md, got %q", string(merged))
	}
}

func TestSyncAssetsInstallsAgentToClaudeAgentDirNotCommandDir(t *testing.T) {
	t.Parallel()

	root := t.TempDir()

	// Create a fixture with the VS Code Batman tool syntax so we can verify transforms fire.
	promptsDir := filepath.Join(root, "coding-cli", "prompts")
	if err := os.MkdirAll(promptsDir, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, "coding-cli", "skills"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	agentSrc := vscodeBatmanFrontmatterTools + "\n" +
		"hooks:\n" +
		"   Stop:\n" +
		"      - {type: command, command: \"mempalace --harness {{MEMPALACE_HARNESS}}\", timeout: 30}\n" +
		"Use #tool:vscode/askQuestions to clarify.\n" +
		"Run #tool:agent/runSubagent to research.\n"
	if err := os.WriteFile(filepath.Join(promptsDir, "batman.agent.md"), []byte(agentSrc), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	commandDir := filepath.Join(root, "claude", "commands")
	agentDir := filepath.Join(root, "claude", "agents")
	layout := repos.RepoLayout{CodingCLI: filepath.Join(root, "coding-cli")}
	profile := host.HostProfile{
		Kind:        host.HostClaudeCode,
		DisplayName: "Claude Code",
		Harness:     string(host.HostClaudeCode),
		Roots: host.HostRoots{
			PromptDir: commandDir,
			AgentDir:  agentDir,
		},
	}

	if _, err := SyncAssets(layout, profile, SyncOptions{}); err != nil {
		t.Fatalf("SyncAssets returned error: %v", err)
	}

	// Agent must be in the agents dir, not the commands dir.
	agentDest := filepath.Join(agentDir, "batman.agent.md")
	if _, err := os.Stat(agentDest); err != nil {
		t.Fatalf("expected batman.agent.md in agents dir, got error: %v", err)
	}
	if _, err := os.Stat(filepath.Join(commandDir, "batman.agent.md")); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("batman.agent.md must not be placed in the commands dir")
	}

	// Claude Code transforms must have been applied.
	content, err := os.ReadFile(agentDest)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	rendered := string(content)
	if strings.Contains(rendered, "#tool:vscode/askQuestions") {
		t.Fatal("VS Code tool refs should be replaced in claude-code install")
	}
	if !strings.Contains(rendered, "AskUserQuestion") {
		t.Fatal("AskUserQuestion should be present in claude-code install")
	}
	if strings.Contains(rendered, "hooks:") {
		t.Fatal("hooks block should be stripped in claude-code install")
	}
	if !strings.Contains(rendered, "tools: [Bash,") {
		t.Fatal("Claude Code tools list should be present in claude-code install")
	}
	if !strings.Contains(rendered, "mcp__github__get_me") {
		t.Fatal("GitHub MCP tools should be present in claude-code install")
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

func TestMergeClaudeHooksCreatesFileWhenMissing(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "settings.json")
	result, err := mergeClaudeHooks(path)
	if err != nil {
		t.Fatalf("mergeClaudeHooks() error = %v", err)
	}
	if result.Action != "created" {
		t.Fatalf("expected action=created, got %q", result.Action)
	}
	assertSettingsHasMempalaceHooks(t, path)
}

func TestMergeClaudeHooksPreservesExistingSettings(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "settings.json")
	existing := `{
    "theme": "dark",
    "hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]
    }
}`
	if err := os.WriteFile(path, []byte(existing), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	if _, err := mergeClaudeHooks(path); err != nil {
		t.Fatalf("mergeClaudeHooks() error = %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	content := string(raw)

	if !strings.Contains(content, `"theme"`) {
		t.Fatal("expected theme key to be preserved")
	}
	if !strings.Contains(content, "rtk hook claude") {
		t.Fatal("expected existing PreToolUse hook to be preserved")
	}
	assertSettingsHasMempalaceHooks(t, path)
}

func TestMergeClaudeHooksOverwritesExistingMempalaceHooks(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "settings.json")
	existing := `{
    "hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "old-stop-command"}]}],
        "PreCompact": [{"hooks": [{"type": "command", "command": "old-precompact-command"}]}]
    }
}`
	if err := os.WriteFile(path, []byte(existing), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	if _, err := mergeClaudeHooks(path); err != nil {
		t.Fatalf("mergeClaudeHooks() error = %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	content := string(raw)

	if strings.Contains(content, "old-stop-command") {
		t.Fatal("expected old Stop command to be replaced")
	}
	if strings.Contains(content, "old-precompact-command") {
		t.Fatal("expected old PreCompact command to be replaced")
	}
	assertSettingsHasMempalaceHooks(t, path)
}

func TestSyncAssetsWritesHooksForClaudeCode(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	promptsDir := filepath.Join(root, "coding-cli", "prompts")
	if err := os.MkdirAll(promptsDir, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, "coding-cli", "skills"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.WriteFile(filepath.Join(promptsDir, "batman.agent.md"), []byte("agent"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	settingsPath := filepath.Join(root, "claude", "settings.json")
	layout := repos.RepoLayout{CodingCLI: filepath.Join(root, "coding-cli")}
	profile := host.HostProfile{
		Kind:    host.HostClaudeCode,
		Harness: string(host.HostClaudeCode),
		Roots: host.HostRoots{
			AgentDir:     filepath.Join(root, "claude", "agents"),
			SettingsPath: settingsPath,
		},
	}

	if _, err := SyncAssets(layout, profile, SyncOptions{}); err != nil {
		t.Fatalf("SyncAssets returned error: %v", err)
	}

	assertSettingsHasMempalaceHooks(t, settingsPath)
}

func assertSettingsHasMempalaceHooks(t *testing.T, path string) {
	t.Helper()

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile %s returned error: %v", path, err)
	}
	content := string(raw)

	if !strings.Contains(content, "--hook stop --harness claude-code") {
		t.Fatalf("expected stop hook in settings, got %q", content)
	}
	if !strings.Contains(content, "--hook precompact --harness claude-code") {
		t.Fatalf("expected precompact hook in settings, got %q", content)
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
		filepath.Join(root, "coding-cli", "prompts", "demo.prompt.md"):           "prompt",
		filepath.Join(root, "coding-cli", "prompts", "demo.instructions.md"):     "instruction",
		filepath.Join(root, "coding-cli", "prompts", "batman.agent.md"):          "python3 -m mempalace hook run --harness {{MEMPALACE_HARNESS}}",
		filepath.Join(root, "coding-cli", "skills", "example-skill", "SKILL.md"): "skill",
	}
	for path, content := range files {
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatalf("WriteFile %s returned error: %v", path, err)
		}
	}
}
