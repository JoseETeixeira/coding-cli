// Package state persists user-level coding-cli configuration that needs to
// survive across invocations from arbitrary working directories. The only
// thing tracked today is the "default workspace root" — the workspace whose
// query-code-mcp install hosts the venv, cocoindex executable, and codebase
// index that `run indexing` should reuse when the cwd is not inside any
// workspace layout.
package state

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

// State is the JSON shape persisted to disk.
type State struct {
	DefaultWorkspaceRoot string `json:"default_workspace_root,omitempty"`
}

// Path returns the absolute path to the state file for the current user.
// Honors $CODING_CLI_STATE_FILE for tests and unusual setups.
func Path() (string, error) {
	if override := os.Getenv("CODING_CLI_STATE_FILE"); override != "" {
		return override, nil
	}

	if dir := os.Getenv("CODING_CLI_STATE_DIR"); dir != "" {
		return filepath.Join(dir, "state.json"), nil
	}

	if runtime.GOOS == "windows" {
		appData := os.Getenv("APPDATA")
		if appData == "" {
			home, err := os.UserHomeDir()
			if err != nil {
				return "", fmt.Errorf("resolve home directory: %w", err)
			}
			appData = filepath.Join(home, "AppData", "Roaming")
		}
		return filepath.Join(appData, "coding-cli", "state.json"), nil
	}

	if configHome := os.Getenv("XDG_CONFIG_HOME"); configHome != "" {
		return filepath.Join(configHome, "coding-cli", "state.json"), nil
	}

	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve home directory: %w", err)
	}
	return filepath.Join(home, ".config", "coding-cli", "state.json"), nil
}

// Load returns the persisted state. When the state file is absent the
// returned State is the zero value and ok is false; both indicate "no state
// yet" rather than an error.
func Load() (State, bool, error) {
	path, err := Path()
	if err != nil {
		return State{}, false, err
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return State{}, false, nil
		}
		return State{}, false, fmt.Errorf("read %s: %w", path, err)
	}

	var parsed State
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return State{}, false, fmt.Errorf("parse %s: %w", path, err)
	}
	return parsed, true, nil
}

// Save writes the state file, creating the parent directory if needed.
func Save(s State) error {
	path, err := Path()
	if err != nil {
		return err
	}

	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("create directory for %s: %w", path, err)
	}

	body, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal state: %w", err)
	}

	if err := os.WriteFile(path, body, 0o644); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

// SetDefaultWorkspaceRoot is a convenience that merges workspaceRoot into the
// existing state (preserving other fields if any are added later).
func SetDefaultWorkspaceRoot(workspaceRoot string) error {
	current, _, err := Load()
	if err != nil {
		return err
	}
	current.DefaultWorkspaceRoot = workspaceRoot
	return Save(current)
}

// DefaultWorkspaceRoot returns the persisted workspace root, if any.
func DefaultWorkspaceRoot() (string, bool, error) {
	current, ok, err := Load()
	if err != nil {
		return "", false, err
	}
	if !ok {
		return "", false, nil
	}
	return current.DefaultWorkspaceRoot, current.DefaultWorkspaceRoot != "", nil
}
