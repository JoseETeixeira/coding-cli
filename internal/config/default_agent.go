package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/host"
)

// ClaudeCodeDefaultAgentName is the frontmatter `name:` value of the Batman
// agent that the coding-cli installs into ~/.claude/agents/. Setting the
// top-level `agent` key in settings.json to this string makes Claude Code
// select Batman as the default session agent instead of the built-in
// catch-all.
const ClaudeCodeDefaultAgentName = "Batman Agent"

// SetClaudeCodeDefaultAgent ensures the user-level Claude Code settings.json
// pins the Batman agent as the default. It is a no-op for any other host
// profile.
//
// The merge is idempotent: when `agent` already resolves to
// ClaudeCodeDefaultAgentName the file is left unchanged.
func SetClaudeCodeDefaultAgent(profile host.HostProfile) (ConfigResult, error) {
	if profile.Kind != host.HostClaudeCode {
		return ConfigResult{Action: "skipped"}, nil
	}

	settingsPath := profile.Roots.SettingsPath
	if settingsPath == "" {
		return ConfigResult{}, clierrors.New(clierrors.KindConfig, "claude-code profile has no settings path")
	}

	settings := map[string]any{}
	if existing, err := os.ReadFile(settingsPath); err == nil {
		if unmarshalErr := json.Unmarshal(existing, &settings); unmarshalErr != nil {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", settingsPath), unmarshalErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", settingsPath), err)
	}

	if current, ok := settings["agent"].(string); ok && current == ClaudeCodeDefaultAgentName {
		return ConfigResult{Path: settingsPath, Action: "skipped"}, nil
	}

	settings["agent"] = ClaudeCodeDefaultAgentName

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
