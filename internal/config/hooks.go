package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/repos"
)

// CocoIndexRefreshHookCommand returns the absolute path to the SessionStart hook
// script shipped inside the coding-cli repository. The path is derived from the
// resolved repo layout so each developer gets the script that lives under their
// own clone.
func CocoIndexRefreshHookCommand(layout repos.RepoLayout) string {
	return filepath.Join(layout.CodingCLI, ".claude", "hooks", "refresh-cocoindex.sh")
}

// InstallClaudeCodeHooks merges the workspace SessionStart hook into the
// Claude Code user settings file. It is a no-op for any other host profile.
//
// The merge is idempotent: if a SessionStart matcher already references the
// workspace hook command, the file is left unchanged.
func InstallClaudeCodeHooks(profile host.HostProfile, layout repos.RepoLayout) (ConfigResult, error) {
	if profile.Kind != host.HostClaudeCode {
		return ConfigResult{Action: "skipped"}, nil
	}

	settingsPath := profile.Roots.SettingsPath
	if settingsPath == "" {
		return ConfigResult{}, clierrors.New(clierrors.KindConfig, "claude-code profile has no settings path")
	}

	hookCommand := CocoIndexRefreshHookCommand(layout)

	settings := map[string]any{}
	if existing, err := os.ReadFile(settingsPath); err == nil {
		if unmarshalErr := json.Unmarshal(existing, &settings); unmarshalErr != nil {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", settingsPath), unmarshalErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", settingsPath), err)
	}

	if !mergeSessionStartHook(settings, hookCommand) {
		return ConfigResult{Path: settingsPath, Action: "skipped"}, nil
	}

	content, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("marshal %s", settingsPath), err)
	}

	action, err := writeConfigFile(settingsPath, content)
	if err != nil {
		return ConfigResult{}, err
	}

	return ConfigResult{Path: settingsPath, Action: action}, nil
}

// mergeSessionStartHook ensures a SessionStart "startup" matcher referencing
// the given command exists. Returns true when settings were mutated.
func mergeSessionStartHook(settings map[string]any, command string) bool {
	hooks := ensureMap(settings, "hooks")
	matchers := ensureSlice(hooks, "SessionStart")

	for _, entry := range matchers {
		matcher, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		if matcher["matcher"] != "startup" {
			continue
		}
		innerHooks, ok := matcher["hooks"].([]any)
		if !ok {
			continue
		}
		for _, hook := range innerHooks {
			hookMap, ok := hook.(map[string]any)
			if !ok {
				continue
			}
			if hookMap["command"] == command {
				return false
			}
		}
	}

	hooks["SessionStart"] = append(matchers, map[string]any{
		"matcher": "startup",
		"hooks": []any{
			map[string]any{
				"type":    "command",
				"command": command,
				"timeout": 10,
			},
		},
	})

	return true
}

func ensureSlice(root map[string]any, key string) []any {
	if existing, ok := root[key].([]any); ok {
		return existing
	}

	slice := []any{}
	root[key] = slice
	return slice
}

// blockDangerousGitScriptName is the file name of the bundled hook script
// that blocks destructive git commands. The source copy lives under
// coding-cli/.claude/hooks/.
const blockDangerousGitScriptName = "block-dangerous-git.sh"

// codexGuardrailMarkerStart and codexGuardrailMarkerEnd delimit the managed
// guardrail block that InstallGitGuardrails maintains inside Codex AGENTS.md.
// Content outside the markers is preserved untouched.
const (
	codexGuardrailMarkerStart = "<!-- coding-cli:git-guardrails:start -->"
	codexGuardrailMarkerEnd   = "<!-- coding-cli:git-guardrails:end -->"
)

// dangerousGitDenyPatterns is the canonical list of git command patterns that
// every provider blocks. The Claude Code hook reads them from the bundled
// shell script (kept in sync manually). VS Code and Codex pull the same set
// from this slice.
var dangerousGitDenyPatterns = []string{
	`\bgit\s+push\b`,
	`\bgit\s+reset\s+--hard\b`,
	`\bgit\s+clean\s+-f(d)?\b`,
	`\bgit\s+branch\s+-D\b`,
	`\bgit\s+checkout\s+\.`,
	`\bgit\s+restore\s+\.`,
}

// BlockDangerousGitSourcePath returns the absolute path to the hook script
// shipped inside the coding-cli repository. The destination copy installed
// into the user's Claude Code hooks directory is derived from the resolved
// settings path so each developer gets the script that lives under their
// own clone.
func BlockDangerousGitSourcePath(layout repos.RepoLayout) string {
	return filepath.Join(layout.CodingCLI, ".claude", "hooks", blockDangerousGitScriptName)
}

// InstallGitGuardrails installs provider-appropriate guardrails against
// destructive git commands. Behavior per host:
//
//   - Claude Code: copies block-dangerous-git.sh from coding-cli to
//     ~/.claude/hooks/ and merges a PreToolUse Bash hook into settings.json.
//   - VS Code / Batman: merges deny rules into chat.tools.terminal.autoApprove
//     in VS Code user settings.json.
//   - Codex: maintains a managed guardrail block in ~/.codex/AGENTS.md.
//
// The function is idempotent: re-running leaves an already-configured host
// unchanged and returns Action == "skipped".
func InstallGitGuardrails(profile host.HostProfile, layout repos.RepoLayout) (ConfigResult, error) {
	switch profile.Kind {
	case host.HostClaudeCode:
		return installClaudeCodeGitGuardrails(profile, layout)
	case host.HostVSCode, host.HostBatman:
		return installVSCodeGitGuardrails(profile)
	case host.HostCodex:
		return installCodexGitGuardrails(profile)
	default:
		return ConfigResult{Action: "skipped"}, nil
	}
}

func installClaudeCodeGitGuardrails(profile host.HostProfile, layout repos.RepoLayout) (ConfigResult, error) {
	settingsPath := profile.Roots.SettingsPath
	if settingsPath == "" {
		return ConfigResult{}, clierrors.New(clierrors.KindConfig, "claude-code profile has no settings path")
	}

	hooksDir := filepath.Join(filepath.Dir(settingsPath), "hooks")
	destScript := filepath.Join(hooksDir, blockDangerousGitScriptName)

	sourceScript := BlockDangerousGitSourcePath(layout)
	if err := copyExecutable(sourceScript, destScript); err != nil {
		return ConfigResult{}, err
	}

	settings := map[string]any{}
	if existing, err := os.ReadFile(settingsPath); err == nil {
		if unmarshalErr := json.Unmarshal(existing, &settings); unmarshalErr != nil {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", settingsPath), unmarshalErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", settingsPath), err)
	}

	if !mergePreToolUseHook(settings, destScript) {
		return ConfigResult{Path: settingsPath, Action: "skipped"}, nil
	}

	content, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("marshal %s", settingsPath), err)
	}

	action, err := writeConfigFile(settingsPath, content)
	if err != nil {
		return ConfigResult{}, err
	}

	return ConfigResult{Path: settingsPath, Action: action}, nil
}

// mergePreToolUseHook adds the git-guardrails hook to the existing Bash
// matcher under PreToolUse, or creates the matcher entry when absent. Other
// matchers and hooks are preserved. Returns true when settings mutated.
func mergePreToolUseHook(settings map[string]any, command string) bool {
	hooks := ensureMap(settings, "hooks")
	matchers := ensureSlice(hooks, "PreToolUse")

	for index, entry := range matchers {
		matcher, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		if matcher["matcher"] != "Bash" {
			continue
		}
		innerHooks, _ := matcher["hooks"].([]any)
		for _, hook := range innerHooks {
			hookMap, ok := hook.(map[string]any)
			if !ok {
				continue
			}
			if hookMap["command"] == command {
				return false
			}
		}
		innerHooks = append(innerHooks, map[string]any{
			"type":    "command",
			"command": command,
		})
		matcher["hooks"] = innerHooks
		matchers[index] = matcher
		hooks["PreToolUse"] = matchers
		return true
	}

	hooks["PreToolUse"] = append(matchers, map[string]any{
		"matcher": "Bash",
		"hooks": []any{
			map[string]any{
				"type":    "command",
				"command": command,
			},
		},
	})
	return true
}

func installVSCodeGitGuardrails(profile host.HostProfile) (ConfigResult, error) {
	settingsPath := profile.Roots.SettingsPath
	if settingsPath == "" {
		return ConfigResult{}, clierrors.New(clierrors.KindConfig, "vscode profile has no settings path")
	}

	settings := map[string]any{}
	if existing, err := os.ReadFile(settingsPath); err == nil {
		if unmarshalErr := json.Unmarshal(existing, &settings); unmarshalErr != nil {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", settingsPath), unmarshalErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", settingsPath), err)
	}

	if !mergeVSCodeDenyRules(settings) {
		return ConfigResult{Path: settingsPath, Action: "skipped"}, nil
	}

	content, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("marshal %s", settingsPath), err)
	}

	action, err := writeConfigFile(settingsPath, content)
	if err != nil {
		return ConfigResult{}, err
	}

	return ConfigResult{Path: settingsPath, Action: action}, nil
}

// mergeVSCodeDenyRules adds each dangerous git pattern as a deny entry under
// chat.tools.terminal.autoApprove. Existing user entries are preserved. Each
// pattern uses matchCommandLine:true so the rule fires even when the git call
// is chained behind a cd, &&, |, etc.
func mergeVSCodeDenyRules(settings map[string]any) bool {
	autoApprove := ensureMap(settings, "chat.tools.terminal.autoApprove")
	mutated := false
	for _, pattern := range dangerousGitDenyPatterns {
		key := fmt.Sprintf("/%s/", pattern)
		desired := map[string]any{
			"approve":          false,
			"matchCommandLine": true,
		}
		if existing, ok := autoApprove[key]; ok {
			if equalDenyRule(existing, desired) {
				continue
			}
		}
		autoApprove[key] = desired
		mutated = true
	}
	return mutated
}

func equalDenyRule(existing any, desired map[string]any) bool {
	asMap, ok := existing.(map[string]any)
	if !ok {
		return false
	}
	if asMap["approve"] != desired["approve"] {
		return false
	}
	if asMap["matchCommandLine"] != desired["matchCommandLine"] {
		return false
	}
	return true
}

func installCodexGitGuardrails(profile host.HostProfile) (ConfigResult, error) {
	agentsPath := profile.Roots.InstructionFile
	if agentsPath == "" {
		return ConfigResult{}, clierrors.New(clierrors.KindConfig, "codex profile has no instruction file path")
	}

	var existing string
	raw, err := os.ReadFile(agentsPath)
	if err != nil {
		if !errors.Is(err, os.ErrNotExist) {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", agentsPath), err)
		}
	} else {
		existing = string(raw)
	}

	rendered := renderCodexGuardrailBlock()
	updated, changed := upsertManagedBlock(existing, codexGuardrailMarkerStart, codexGuardrailMarkerEnd, rendered)
	if !changed {
		return ConfigResult{Path: agentsPath, Action: "skipped"}, nil
	}

	action, err := writeConfigFile(agentsPath, []byte(updated))
	if err != nil {
		return ConfigResult{}, err
	}

	return ConfigResult{Path: agentsPath, Action: action}, nil
}

// upsertManagedBlock replaces content between start/end markers with newBody.
// When markers are absent, newBody is appended (separated from prior content
// by a blank line). Returns (newContent, mutated).
func upsertManagedBlock(existing, startMarker, endMarker, newBody string) (string, bool) {
	startIdx := strings.Index(existing, startMarker)
	endIdx := strings.Index(existing, endMarker)
	block := startMarker + "\n" + newBody + "\n" + endMarker + "\n"

	if startIdx >= 0 && endIdx > startIdx {
		before := existing[:startIdx]
		after := existing[endIdx+len(endMarker):]
		after = strings.TrimLeft(after, "\n")
		next := before + block
		if after != "" {
			next += "\n" + after
		}
		if next == existing {
			return existing, false
		}
		return next, true
	}

	if existing == "" {
		return block, true
	}
	trimmed := strings.TrimRight(existing, "\n")
	return trimmed + "\n\n" + block, true
}

func renderCodexGuardrailBlock() string {
	var builder strings.Builder
	builder.WriteString("## Dangerous Git Commands\n\n")
	builder.WriteString("Do NOT execute these commands without explicit user approval. If the user has not just asked for one of these actions, refuse and surface the request instead.\n\n")
	builder.WriteString("- `git push` (any variant, including `--force`)\n")
	builder.WriteString("- `git reset --hard`\n")
	builder.WriteString("- `git clean -f` / `git clean -fd`\n")
	builder.WriteString("- `git branch -D`\n")
	builder.WriteString("- `git checkout .` / `git restore .`\n\n")
	builder.WriteString("Codex does not have a shell-level PreToolUse hook, so this guardrail is advisory: the agent itself must enforce it.\n")
	return builder.String()
}

func copyExecutable(source, dest string) error {
	in, err := os.Open(source)
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("open %s", source), err)
	}
	defer in.Close()

	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("create directory for %s", dest), err)
	}

	out, err := os.OpenFile(dest, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o755)
	if err != nil {
		return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("create %s", dest), err)
	}
	defer out.Close()

	if _, err := io.Copy(out, in); err != nil {
		return clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("copy to %s", dest), err)
	}
	return nil
}
