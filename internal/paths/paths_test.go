package paths

import (
	"path/filepath"
	"testing"
)

func TestResolverUsesVSCodeOverrides(t *testing.T) {
	t.Parallel()

	resolver := NewResolverWith("/tmp/home", "darwin", lookupMap(map[string]string{
		"VSCODE_USER_PROMPTS_FOLDER": "/tmp/custom-prompts",
		"USER_AGENTS_DIR":           "/tmp/custom-agents",
		"USER_INSTRUCTIONS_DIR":     "/tmp/custom-instructions",
		"USER_SKILLS_DIR":           "/tmp/custom-skills",
	}))

	if got := resolver.VSCodePromptDir(); got != "/tmp/custom-prompts" {
		t.Fatalf("VSCodePromptDir() = %q, want %q", got, "/tmp/custom-prompts")
	}
	if got := resolver.VSCodeAgentDir(); got != "/tmp/custom-agents" {
		t.Fatalf("VSCodeAgentDir() = %q, want %q", got, "/tmp/custom-agents")
	}
	if got := resolver.VSCodeInstructionDir(); got != "/tmp/custom-instructions" {
		t.Fatalf("VSCodeInstructionDir() = %q, want %q", got, "/tmp/custom-instructions")
	}
	if got := resolver.GenericSkillDir(); got != "/tmp/custom-skills" {
		t.Fatalf("GenericSkillDir() = %q, want %q", got, "/tmp/custom-skills")
	}
}

func TestResolverUsesDefaultMacPaths(t *testing.T) {
	t.Parallel()

	resolver := NewResolverWith("/Users/tester", "darwin", nil)

	if got := resolver.VSCodePromptDir(); got != filepath.Join("/Users/tester", "Library", "Application Support", "Code", "User", "prompts") {
		t.Fatalf("VSCodePromptDir() = %q", got)
	}
	if got := resolver.VSCodeMCPConfigPath(); got != filepath.Join("/Users/tester", "Library", "Application Support", "Code", "User", "mcp.json") {
		t.Fatalf("VSCodeMCPConfigPath() = %q", got)
	}
	if got := resolver.GenericSkillDir(); got != filepath.Join("/Users/tester", ".agents", "skills") {
		t.Fatalf("GenericSkillDir() = %q", got)
	}
}

func TestResolverUsesClaudeAndCodexOverrides(t *testing.T) {
	t.Parallel()

	resolver := NewResolverWith("/tmp/home", "linux", lookupMap(map[string]string{
		"CLAUDE_CONFIG_DIR": "~/custom-claude",
		"CODEX_HOME":        "~/custom-codex",
	}))

	if got := resolver.ClaudeRoot(); got != filepath.Join("/tmp/home", "custom-claude") {
		t.Fatalf("ClaudeRoot() = %q", got)
	}
	if got := resolver.ClaudeConfigPath(); got != filepath.Join("/tmp/home", ".claude.json") {
		t.Fatalf("ClaudeConfigPath() = %q", got)
	}
	if got := resolver.CodexRoot(); got != filepath.Join("/tmp/home", "custom-codex") {
		t.Fatalf("CodexRoot() = %q", got)
	}
	if got := resolver.CodexConfigPath(); got != filepath.Join("/tmp/home", "custom-codex", "config.toml") {
		t.Fatalf("CodexConfigPath() = %q", got)
	}
}

func lookupMap(values map[string]string) func(string) (string, bool) {
	return func(key string) (string, bool) {
		value, ok := values[key]
		return value, ok
	}
}