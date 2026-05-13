package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/repos"
)

func TestInstallClaudeCodeHooksCreatesSettings(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, ".claude", "settings.json")

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}
	layout := repos.RepoLayout{CodingCLI: "/work/workspace/coding-cli"}

	result, err := InstallClaudeCodeHooks(profile, layout)
	if err != nil {
		t.Fatalf("InstallClaudeCodeHooks returned error: %v", err)
	}
	if result.Action != "created" {
		t.Fatalf("result.Action = %q, want created", result.Action)
	}

	content, err := os.ReadFile(settingsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}

	want := jsonEscape(filepath.Join(layout.CodingCLI, ".claude", "hooks", "refresh-cocoindex.sh"))
	if !strings.Contains(string(content), want) {
		t.Fatalf("settings missing hook command %q: %s", want, string(content))
	}
}

// jsonEscape returns the JSON-encoded form of a path, which is what we expect
// to see on disk after json.Marshal. On Windows, filepath.Join produces
// backslashes that JSON encodes as `\\`, so strings.Contains needs the escaped
// form, not the raw filepath value.
func jsonEscape(value string) string {
	encoded, err := json.Marshal(value)
	if err != nil {
		return value
	}
	// Trim surrounding quotes added by json.Marshal.
	return string(encoded[1 : len(encoded)-1])
}

func TestInstallClaudeCodeHooksIsIdempotent(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}
	layout := repos.RepoLayout{CodingCLI: "/work/workspace/coding-cli"}

	if _, err := InstallClaudeCodeHooks(profile, layout); err != nil {
		t.Fatalf("first call returned error: %v", err)
	}

	result, err := InstallClaudeCodeHooks(profile, layout)
	if err != nil {
		t.Fatalf("second call returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("second result.Action = %q, want skipped", result.Action)
	}
}

func TestInstallClaudeCodeHooksPreservesExistingHooks(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")
	initial := `{
		"hooks": {
			"PreToolUse": [
				{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}
			],
			"SessionStart": [
				{"matcher": "startup", "hooks": [{"type": "command", "command": "other-tool"}]}
			]
		},
		"theme": "dark"
	}`
	if err := os.WriteFile(settingsPath, []byte(initial), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}
	layout := repos.RepoLayout{CodingCLI: "/work/workspace/coding-cli"}

	if _, err := InstallClaudeCodeHooks(profile, layout); err != nil {
		t.Fatalf("InstallClaudeCodeHooks returned error: %v", err)
	}

	content, err := os.ReadFile(settingsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}

	parsed := map[string]any{}
	if err := json.Unmarshal(content, &parsed); err != nil {
		t.Fatalf("Unmarshal returned error: %v", err)
	}

	if parsed["theme"] != "dark" {
		t.Fatalf("theme not preserved: %v", parsed["theme"])
	}

	hooks, ok := parsed["hooks"].(map[string]any)
	if !ok {
		t.Fatalf("hooks missing or wrong type: %T", parsed["hooks"])
	}
	if _, ok := hooks["PreToolUse"]; !ok {
		t.Fatal("PreToolUse hook was dropped")
	}

	sessionStart, ok := hooks["SessionStart"].([]any)
	if !ok {
		t.Fatalf("SessionStart wrong type: %T", hooks["SessionStart"])
	}
	if len(sessionStart) != 2 {
		t.Fatalf("SessionStart len = %d, want 2 (existing + ours)", len(sessionStart))
	}

	want := jsonEscape(filepath.Join(layout.CodingCLI, ".claude", "hooks", "refresh-cocoindex.sh"))
	if !strings.Contains(string(content), want) {
		t.Fatalf("hook command missing: %s", string(content))
	}
	if !strings.Contains(string(content), "other-tool") {
		t.Fatalf("existing SessionStart entry was dropped: %s", string(content))
	}
}

func TestInstallClaudeCodeHooksSkipsNonClaudeProfile(t *testing.T) {
	t.Parallel()

	profile := host.HostProfile{Kind: host.HostVSCode}
	layout := repos.RepoLayout{CodingCLI: "/work/workspace/coding-cli"}

	result, err := InstallClaudeCodeHooks(profile, layout)
	if err != nil {
		t.Fatalf("InstallClaudeCodeHooks returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("result.Action = %q, want skipped", result.Action)
	}
}

func TestInstallClaudeCodeHooksRejectsEmptySettingsPath(t *testing.T) {
	t.Parallel()

	profile := host.HostProfile{Kind: host.HostClaudeCode}
	layout := repos.RepoLayout{CodingCLI: "/work/workspace/coding-cli"}

	if _, err := InstallClaudeCodeHooks(profile, layout); err == nil {
		t.Fatal("expected error for empty settings path")
	}
}
