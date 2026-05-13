package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/coding-cli/coding-cli/internal/host"
)

func TestSetClaudeCodeDefaultAgentCreatesSettings(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, ".claude", "settings.json")

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}

	result, err := SetClaudeCodeDefaultAgent(profile)
	if err != nil {
		t.Fatalf("SetClaudeCodeDefaultAgent returned error: %v", err)
	}
	if result.Action != "created" {
		t.Fatalf("result.Action = %q, want created", result.Action)
	}

	parsed := readSettings(t, settingsPath)
	if got := parsed["agent"]; got != ClaudeCodeDefaultAgentName {
		t.Fatalf("agent = %v, want %q", got, ClaudeCodeDefaultAgentName)
	}
}

func TestSetClaudeCodeDefaultAgentIsIdempotent(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}

	if _, err := SetClaudeCodeDefaultAgent(profile); err != nil {
		t.Fatalf("first call returned error: %v", err)
	}

	result, err := SetClaudeCodeDefaultAgent(profile)
	if err != nil {
		t.Fatalf("second call returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("second result.Action = %q, want skipped", result.Action)
	}
}

func TestSetClaudeCodeDefaultAgentPreservesExistingSettings(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")
	initial := `{
		"hooks": {
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

	if _, err := SetClaudeCodeDefaultAgent(profile); err != nil {
		t.Fatalf("SetClaudeCodeDefaultAgent returned error: %v", err)
	}

	parsed := readSettings(t, settingsPath)
	if parsed["theme"] != "dark" {
		t.Fatalf("theme not preserved: %v", parsed["theme"])
	}
	if parsed["agent"] != ClaudeCodeDefaultAgentName {
		t.Fatalf("agent = %v, want %q", parsed["agent"], ClaudeCodeDefaultAgentName)
	}
	hooks, ok := parsed["hooks"].(map[string]any)
	if !ok {
		t.Fatalf("hooks missing or wrong type: %T", parsed["hooks"])
	}
	if _, ok := hooks["SessionStart"]; !ok {
		t.Fatal("SessionStart hook was dropped")
	}
}

func TestSetClaudeCodeDefaultAgentOverwritesDifferentValue(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")
	initial := `{"agent": "claude", "theme": "dark"}`
	if err := os.WriteFile(settingsPath, []byte(initial), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}

	result, err := SetClaudeCodeDefaultAgent(profile)
	if err != nil {
		t.Fatalf("SetClaudeCodeDefaultAgent returned error: %v", err)
	}
	if result.Action != "updated" {
		t.Fatalf("result.Action = %q, want updated", result.Action)
	}

	parsed := readSettings(t, settingsPath)
	if parsed["agent"] != ClaudeCodeDefaultAgentName {
		t.Fatalf("agent = %v, want %q", parsed["agent"], ClaudeCodeDefaultAgentName)
	}
	if parsed["theme"] != "dark" {
		t.Fatalf("theme not preserved: %v", parsed["theme"])
	}
}

func TestSetClaudeCodeDefaultAgentSkipsNonClaudeProfile(t *testing.T) {
	t.Parallel()

	profile := host.HostProfile{Kind: host.HostVSCode}

	result, err := SetClaudeCodeDefaultAgent(profile)
	if err != nil {
		t.Fatalf("SetClaudeCodeDefaultAgent returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("result.Action = %q, want skipped", result.Action)
	}
}

func TestSetClaudeCodeDefaultAgentRejectsEmptySettingsPath(t *testing.T) {
	t.Parallel()

	profile := host.HostProfile{Kind: host.HostClaudeCode}

	if _, err := SetClaudeCodeDefaultAgent(profile); err == nil {
		t.Fatal("expected error for empty settings path")
	}
}

func readSettings(t *testing.T, path string) map[string]any {
	t.Helper()

	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	parsed := map[string]any{}
	if err := json.Unmarshal(content, &parsed); err != nil {
		t.Fatalf("Unmarshal returned error: %v", err)
	}
	return parsed
}
