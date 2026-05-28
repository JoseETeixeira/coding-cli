package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

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

// sessionStartMatchers lists the SessionStart sources that should re-run the
// codebase-index refresh. "startup" covers a brand-new session, "resume" a
// resumed one, and "clear" a /clear — together they mean "whenever a session is
// started". "compact" is intentionally omitted: it fires mid-session and the
// refresh would add churn without a folder change.
var sessionStartMatchers = []string{"startup", "resume", "clear"}

// mergeSessionStartHook ensures a SessionStart matcher referencing the given
// command exists for each source in sessionStartMatchers. Returns true when
// settings were mutated. Existing matchers and unrelated commands are left
// untouched, so the merge is idempotent.
func mergeSessionStartHook(settings map[string]any, command string) bool {
	hooks := ensureMap(settings, "hooks")
	matchers := ensureSlice(hooks, "SessionStart")

	changed := false
	for _, matcherName := range sessionStartMatchers {
		if sessionStartMatcherHasCommand(matchers, matcherName, command) {
			continue
		}
		matchers = append(matchers, map[string]any{
			"matcher": matcherName,
			"hooks": []any{
				map[string]any{
					"type":    "command",
					"command": command,
					"timeout": 10,
				},
			},
		})
		changed = true
	}

	if changed {
		hooks["SessionStart"] = matchers
	}

	return changed
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
