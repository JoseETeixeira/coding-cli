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

	want := jsonEscape(CocoIndexRefreshHookCommand(layout))
	if !strings.Contains(string(content), want) {
		t.Fatalf("settings missing hook command %q: %s", want, string(content))
	}

	hookCommand := CocoIndexRefreshHookCommand(layout)
	for _, matcher := range []string{"startup", "resume", "clear"} {
		if !sessionStartMatcherInJSON(t, content, matcher, hookCommand) {
			t.Fatalf("settings missing SessionStart %q matcher for hook command: %s", matcher, string(content))
		}
	}
}

// sessionStartMatcherInJSON parses settings JSON and reports whether a
// SessionStart matcher of the given name references command.
func sessionStartMatcherInJSON(t *testing.T, content []byte, matcherName string, command string) bool {
	t.Helper()

	parsed := map[string]any{}
	if err := json.Unmarshal(content, &parsed); err != nil {
		t.Fatalf("Unmarshal returned error: %v", err)
	}
	hooks, ok := parsed["hooks"].(map[string]any)
	if !ok {
		return false
	}
	matchers, ok := hooks["SessionStart"].([]any)
	if !ok {
		return false
	}
	return sessionStartMatcherHasCommand(matchers, matcherName, command)
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
	// 1 pre-existing "other-tool" startup matcher + our startup/resume/clear.
	if len(sessionStart) != 4 {
		t.Fatalf("SessionStart len = %d, want 4 (existing + startup/resume/clear)", len(sessionStart))
	}

	want := jsonEscape(CocoIndexRefreshHookCommand(layout))
	if !strings.Contains(string(content), want) {
		t.Fatalf("hook command missing: %s", string(content))
	}
	if !strings.Contains(string(content), "other-tool") {
		t.Fatalf("existing SessionStart entry was dropped: %s", string(content))
	}

	hookCommand := CocoIndexRefreshHookCommand(layout)
	for _, matcher := range []string{"startup", "resume", "clear"} {
		if !sessionStartMatcherInJSON(t, content, matcher, hookCommand) {
			t.Fatalf("missing SessionStart %q matcher for hook command: %s", matcher, string(content))
		}
	}
}

func TestInstallClaudeCodeHooksMigratesLegacyBarePathEntries(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")
	layout := repos.RepoLayout{CodingCLI: "/work/workspace/coding-cli"}

	// Seed the broken state older versions produced on Windows: SessionStart
	// entries whose command is the bare .sh path (not runnable via cmd).
	barePath := filepath.Join(layout.CodingCLI, ".claude", "hooks", "refresh-cocoindex.sh")
	seed := map[string]any{
		"hooks": map[string]any{
			"SessionStart": []any{
				map[string]any{"matcher": "startup", "hooks": []any{map[string]any{"type": "command", "command": barePath, "timeout": 10}}},
				map[string]any{"matcher": "resume", "hooks": []any{map[string]any{"type": "command", "command": barePath, "timeout": 10}}},
				map[string]any{"matcher": "clear", "hooks": []any{map[string]any{"type": "command", "command": barePath, "timeout": 10}}},
			},
		},
	}
	raw, _ := json.Marshal(seed)
	if err := os.WriteFile(settingsPath, raw, 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	profile := host.HostProfile{Kind: host.HostClaudeCode, Roots: host.HostRoots{SettingsPath: settingsPath}}

	result, err := InstallClaudeCodeHooks(profile, layout)
	if err != nil {
		t.Fatalf("InstallClaudeCodeHooks returned error: %v", err)
	}
	if result.Action != "updated" {
		t.Fatalf("result.Action = %q, want updated (legacy entries should be migrated)", result.Action)
	}

	content, err := os.ReadFile(settingsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	parsed := map[string]any{}
	if err := json.Unmarshal(content, &parsed); err != nil {
		t.Fatalf("Unmarshal returned error: %v", err)
	}
	sessionStart := parsed["hooks"].(map[string]any)["SessionStart"].([]any)

	// Exactly the 3 canonical entries — no duplicates left behind.
	if len(sessionStart) != 3 {
		t.Fatalf("SessionStart len = %d, want 3 (deduped canonical entries): %s", len(sessionStart), string(content))
	}

	wantCommand := CocoIndexRefreshHookCommand(layout)
	if !strings.HasPrefix(wantCommand, "bash ") {
		t.Fatalf("canonical command should be bash-wrapped, got %q", wantCommand)
	}
	for _, entry := range sessionStart {
		cmd := entry.(map[string]any)["hooks"].([]any)[0].(map[string]any)["command"].(string)
		if cmd != wantCommand {
			t.Fatalf("entry command = %q, want %q", cmd, wantCommand)
		}
	}
	if strings.Contains(string(content), jsonEscape(barePath)+"\"") {
		t.Fatalf("legacy bare-path command should have been removed: %s", string(content))
	}

	// Second run must be a no-op now that the config is canonical.
	second, err := InstallClaudeCodeHooks(profile, layout)
	if err != nil {
		t.Fatalf("second call returned error: %v", err)
	}
	if second.Action != "skipped" {
		t.Fatalf("second result.Action = %q, want skipped", second.Action)
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
