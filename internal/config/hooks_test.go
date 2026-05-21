package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
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
	layout := repos.RepoLayout{CodingCLI: "/work/coding-cli"}

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
	layout := repos.RepoLayout{CodingCLI: "/work/coding-cli"}

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
	layout := repos.RepoLayout{CodingCLI: "/work/coding-cli"}

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
	layout := repos.RepoLayout{CodingCLI: "/work/coding-cli"}

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
	layout := repos.RepoLayout{CodingCLI: "/work/coding-cli"}

	if _, err := InstallClaudeCodeHooks(profile, layout); err == nil {
		t.Fatal("expected error for empty settings path")
	}
}

// setupCodingCLIWithGuardrailScript writes a stub coding-cli hooks directory
// containing block-dangerous-git.sh under tempRoot/coding-cli so the install
// flow can copy a real source file. Returns the layout pointing at it.
func setupCodingCLIWithGuardrailScript(t *testing.T, tempRoot string) repos.RepoLayout {
	t.Helper()
	codingCLI := filepath.Join(tempRoot, "coding-cli")
	hooksDir := filepath.Join(codingCLI, ".claude", "hooks")
	if err := os.MkdirAll(hooksDir, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	scriptPath := filepath.Join(hooksDir, "block-dangerous-git.sh")
	if err := os.WriteFile(scriptPath, []byte("#!/bin/bash\nexit 0\n"), 0o755); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}
	return repos.RepoLayout{CodingCLI: codingCLI}
}

func TestInstallGitGuardrailsClaudeCodeCreates(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, ".claude", "settings.json")
	layout := setupCodingCLIWithGuardrailScript(t, dir)

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}

	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
	}
	if result.Action != "created" {
		t.Fatalf("Action = %q, want created", result.Action)
	}

	destScript := filepath.Join(dir, ".claude", "hooks", "block-dangerous-git.sh")
	info, err := os.Stat(destScript)
	if err != nil {
		t.Fatalf("Stat hook script returned error: %v", err)
	}
	// Windows does not honour unix executable bits, so this assertion only
	// fires on POSIX hosts where the bit actually carries meaning.
	if runtime.GOOS != "windows" && info.Mode().Perm()&0o111 == 0 {
		t.Fatalf("hook script not executable: mode=%v", info.Mode())
	}

	content, err := os.ReadFile(settingsPath)
	if err != nil {
		t.Fatalf("ReadFile settings returned error: %v", err)
	}
	if !strings.Contains(string(content), jsonEscape(destScript)) {
		t.Fatalf("settings missing hook command %q: %s", destScript, string(content))
	}
}

func TestInstallGitGuardrailsClaudeCodeIsIdempotent(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, ".claude", "settings.json")
	layout := setupCodingCLIWithGuardrailScript(t, dir)

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}

	if _, err := InstallGitGuardrails(profile, layout); err != nil {
		t.Fatalf("first call returned error: %v", err)
	}
	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("second call returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("second Action = %q, want skipped", result.Action)
	}
}

func TestInstallGitGuardrailsClaudeCodePreservesExistingHooks(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, ".claude", "settings.json")
	layout := setupCodingCLIWithGuardrailScript(t, dir)

	initial := `{
		"hooks": {
			"PreToolUse": [
				{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}
			]
		},
		"theme": "dark"
	}`
	if err := os.MkdirAll(filepath.Dir(settingsPath), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}
	if err := os.WriteFile(settingsPath, []byte(initial), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	profile := host.HostProfile{
		Kind:  host.HostClaudeCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}

	if _, err := InstallGitGuardrails(profile, layout); err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
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
	if !strings.Contains(string(content), "rtk hook claude") {
		t.Fatalf("existing rtk hook dropped: %s", string(content))
	}
	if !strings.Contains(string(content), "block-dangerous-git.sh") {
		t.Fatalf("guardrail hook missing: %s", string(content))
	}
}

func TestInstallGitGuardrailsVSCodeCreates(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")

	profile := host.HostProfile{
		Kind:  host.HostVSCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}
	layout := repos.RepoLayout{}

	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
	}
	if result.Action != "created" {
		t.Fatalf("Action = %q, want created", result.Action)
	}

	content, err := os.ReadFile(settingsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	parsed := map[string]any{}
	if err := json.Unmarshal(content, &parsed); err != nil {
		t.Fatalf("Unmarshal returned error: %v", err)
	}
	autoApprove, ok := parsed["chat.tools.terminal.autoApprove"].(map[string]any)
	if !ok {
		t.Fatalf("chat.tools.terminal.autoApprove missing or wrong type: %T", parsed["chat.tools.terminal.autoApprove"])
	}
	if len(autoApprove) == 0 {
		t.Fatalf("autoApprove has no entries")
	}
	for key, value := range autoApprove {
		ruleMap, ok := value.(map[string]any)
		if !ok {
			t.Fatalf("autoApprove[%q] not an object: %T", key, value)
		}
		if ruleMap["approve"] != false {
			t.Fatalf("autoApprove[%q].approve = %v, want false", key, ruleMap["approve"])
		}
		if ruleMap["matchCommandLine"] != true {
			t.Fatalf("autoApprove[%q].matchCommandLine = %v, want true", key, ruleMap["matchCommandLine"])
		}
	}
}

func TestInstallGitGuardrailsVSCodeIsIdempotent(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")

	profile := host.HostProfile{
		Kind:  host.HostVSCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}
	layout := repos.RepoLayout{}

	if _, err := InstallGitGuardrails(profile, layout); err != nil {
		t.Fatalf("first call returned error: %v", err)
	}
	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("second call returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("second Action = %q, want skipped", result.Action)
	}
}

func TestInstallGitGuardrailsVSCodePreservesExistingSettings(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	settingsPath := filepath.Join(dir, "settings.json")
	initial := `{
		"editor.fontSize": 14,
		"chat.tools.terminal.autoApprove": {
			"/^npm test/": true
		}
	}`
	if err := os.WriteFile(settingsPath, []byte(initial), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	profile := host.HostProfile{
		Kind:  host.HostVSCode,
		Roots: host.HostRoots{SettingsPath: settingsPath},
	}
	layout := repos.RepoLayout{}

	if _, err := InstallGitGuardrails(profile, layout); err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
	}

	content, err := os.ReadFile(settingsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	parsed := map[string]any{}
	if err := json.Unmarshal(content, &parsed); err != nil {
		t.Fatalf("Unmarshal returned error: %v", err)
	}
	if parsed["editor.fontSize"] != float64(14) {
		t.Fatalf("editor.fontSize not preserved: %v", parsed["editor.fontSize"])
	}
	autoApprove, _ := parsed["chat.tools.terminal.autoApprove"].(map[string]any)
	if autoApprove["/^npm test/"] != true {
		t.Fatalf("existing autoApprove entry not preserved: %v", autoApprove["/^npm test/"])
	}
}

func TestInstallGitGuardrailsCodexCreates(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	agentsPath := filepath.Join(dir, "AGENTS.md")

	profile := host.HostProfile{
		Kind:  host.HostCodex,
		Roots: host.HostRoots{InstructionFile: agentsPath},
	}
	layout := repos.RepoLayout{}

	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
	}
	if result.Action != "created" {
		t.Fatalf("Action = %q, want created", result.Action)
	}

	content, err := os.ReadFile(agentsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	body := string(content)
	if !strings.Contains(body, codexGuardrailMarkerStart) || !strings.Contains(body, codexGuardrailMarkerEnd) {
		t.Fatalf("guardrail markers missing: %s", body)
	}
	if !strings.Contains(body, "git push") {
		t.Fatalf("guardrail content missing: %s", body)
	}
}

func TestInstallGitGuardrailsCodexIsIdempotent(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	agentsPath := filepath.Join(dir, "AGENTS.md")

	profile := host.HostProfile{
		Kind:  host.HostCodex,
		Roots: host.HostRoots{InstructionFile: agentsPath},
	}
	layout := repos.RepoLayout{}

	if _, err := InstallGitGuardrails(profile, layout); err != nil {
		t.Fatalf("first call returned error: %v", err)
	}
	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("second call returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("second Action = %q, want skipped", result.Action)
	}
}

func TestInstallGitGuardrailsCodexPreservesExistingAGENTS(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	agentsPath := filepath.Join(dir, "AGENTS.md")
	initial := "# Codex Project Notes\n\nDo X. Avoid Y.\n"
	if err := os.WriteFile(agentsPath, []byte(initial), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	profile := host.HostProfile{
		Kind:  host.HostCodex,
		Roots: host.HostRoots{InstructionFile: agentsPath},
	}
	layout := repos.RepoLayout{}

	if _, err := InstallGitGuardrails(profile, layout); err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
	}

	content, err := os.ReadFile(agentsPath)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	body := string(content)
	if !strings.Contains(body, "Codex Project Notes") {
		t.Fatalf("existing AGENTS.md content dropped: %s", body)
	}
	if !strings.Contains(body, "Do X. Avoid Y.") {
		t.Fatalf("existing AGENTS.md body dropped: %s", body)
	}
	if !strings.Contains(body, codexGuardrailMarkerStart) {
		t.Fatalf("guardrail block missing: %s", body)
	}
}

func TestInstallGitGuardrailsSkipsUnknownProfile(t *testing.T) {
	t.Parallel()

	profile := host.HostProfile{Kind: host.HostKind("unknown")}
	layout := repos.RepoLayout{}

	result, err := InstallGitGuardrails(profile, layout)
	if err != nil {
		t.Fatalf("InstallGitGuardrails returned error: %v", err)
	}
	if result.Action != "skipped" {
		t.Fatalf("Action = %q, want skipped", result.Action)
	}
}
