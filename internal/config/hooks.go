package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/repos"
)

// cocoIndexHookScriptBaseName identifies the shipped SessionStart hook script,
// used to recognize (and replace) any legacy or duplicate entry referencing it.
const cocoIndexHookScriptBaseName = "refresh-cocoindex.sh"

// cocoIndexHookScriptPath returns the absolute path to the SessionStart hook
// script shipped inside the coding-cli repository, derived from the resolved
// repo layout so each developer gets the script under their own clone.
func cocoIndexHookScriptPath(layout repos.RepoLayout) string {
	return filepath.Join(layout.CodingCLI, ".claude", "hooks", cocoIndexHookScriptBaseName)
}

// CocoIndexRefreshHookCommand returns the SessionStart hook command for the
// resolved repo layout. The script is invoked through `bash` rather than as a
// bare path: a `.sh` path is not directly executable on Windows (where Claude
// Code shells out via cmd), so a raw-path entry silently fails there. The path
// is forward-slashed and quoted because workspace paths can contain spaces.
func CocoIndexRefreshHookCommand(layout repos.RepoLayout) string {
	return fmt.Sprintf("bash %q", filepath.ToSlash(cocoIndexHookScriptPath(layout)))
}

// InstallClaudeCodeHooks merges the workspace SessionStart hook into the
// Claude Code user settings file. It is a no-op for any other host profile.
//
// The merge is idempotent and self-healing: it removes any existing SessionStart
// entry referencing the shipped hook script (including legacy raw-path entries
// from older versions) and rewrites exactly one canonical `bash "..."` entry per
// matcher. Unrelated SessionStart entries are preserved, and a settled config is
// left untouched.
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

// sessionStartMatchers lists the SessionStart sources that should re-run the
// codebase-index refresh. "startup" covers a brand-new session, "resume" a
// resumed one, and "clear" a /clear — together they mean "whenever a session is
// started". "compact" is intentionally omitted: it fires mid-session and the
// refresh would add churn without a folder change.
var sessionStartMatchers = []string{"startup", "resume", "clear"}

// mergeSessionStartHook rewrites the canonical SessionStart entries (one per
// source in sessionStartMatchers) referencing command. Any pre-existing entry
// that references the shipped hook script — in any command form, including a
// legacy bare-path entry — is dropped so stale or duplicate variants are
// migrated rather than accumulated. Unrelated SessionStart entries are kept in
// place. Returns true when settings were mutated.
func mergeSessionStartHook(settings map[string]any, command string) bool {
	hooks := ensureMap(settings, "hooks")
	matchers := ensureSlice(hooks, "SessionStart")

	kept := make([]any, 0, len(matchers))
	managed := make([]any, 0, len(matchers))
	for _, entry := range matchers {
		if sessionStartEntryReferencesScript(entry) {
			managed = append(managed, entry)
		} else {
			kept = append(kept, entry)
		}
	}

	desired := make([]any, 0, len(sessionStartMatchers))
	for _, matcherName := range sessionStartMatchers {
		desired = append(desired, map[string]any{
			"matcher": matcherName,
			"hooks": []any{
				map[string]any{
					"type":    "command",
					"command": command,
					"timeout": 10,
				},
			},
		})
	}

	if jsonEqual(managed, desired) {
		return false
	}

	hooks["SessionStart"] = append(kept, desired...)
	return true
}

// sessionStartEntryReferencesScript reports whether any hook command in a
// SessionStart entry references the shipped refresh-cocoindex.sh script, in any
// invocation form (bare path, bash-wrapped, forward- or back-slashed).
func sessionStartEntryReferencesScript(entry any) bool {
	matcher, ok := entry.(map[string]any)
	if !ok {
		return false
	}
	innerHooks, ok := matcher["hooks"].([]any)
	if !ok {
		return false
	}
	for _, hook := range innerHooks {
		hookMap, ok := hook.(map[string]any)
		if !ok {
			continue
		}
		command, ok := hookMap["command"].(string)
		if ok && strings.Contains(command, cocoIndexHookScriptBaseName) {
			return true
		}
	}
	return false
}

// jsonEqual compares two values by their canonical JSON encoding.
func jsonEqual(a, b any) bool {
	left, err := json.Marshal(a)
	if err != nil {
		return false
	}
	right, err := json.Marshal(b)
	if err != nil {
		return false
	}
	return string(left) == string(right)
}

// sessionStartMatcherHasCommand reports whether a SessionStart matcher of the
// given name already references command.
func sessionStartMatcherHasCommand(matchers []any, matcherName string, command string) bool {
	for _, entry := range matchers {
		matcher, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		if matcher["matcher"] != matcherName {
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
				return true
			}
		}
	}

	return false
}

func ensureSlice(root map[string]any, key string) []any {
	if existing, ok := root[key].([]any); ok {
		return existing
	}

	slice := []any{}
	root[key] = slice
	return slice
}
