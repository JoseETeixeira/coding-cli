package config

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/repos"
	toml "github.com/pelletier/go-toml/v2"
)

type ManagedServer struct {
	Type               string            `json:"type,omitempty"`
	Command            string            `json:"command,omitempty"`
	Args               []string          `json:"args,omitempty"`
	CWD                string            `json:"cwd,omitempty"`
	Env                map[string]string `json:"env,omitempty"`
	URL                string            `json:"url,omitempty"`
	BearerTokenEnvVar  string            `json:"bearer_token_env_var,omitempty"`
}

type ConfigResult struct {
	Path   string
	Action string
}

func WriteConfig(profile host.HostProfile, layout repos.RepoLayout) (ConfigResult, error) {
	servers := ManagedServers(layout, profile)
	switch profile.MCPConfigFormat {
	case "vscode-json":
		return writeJSONConfig(profile.Roots.MCPConfigPath, "servers", servers)
	case "claude-json":
		return writeJSONConfig(profile.Roots.MCPConfigPath, "mcpServers", servers)
	case "codex-toml":
		return writeTOMLConfig(profile.Roots.MCPConfigPath, servers)
	default:
		return ConfigResult{}, clierrors.New(clierrors.KindConfig, fmt.Sprintf("unsupported config format %q", profile.MCPConfigFormat))
	}
}

func ManagedServers(layout repos.RepoLayout, profile host.HostProfile) map[string]ManagedServer {
	servers := map[string]ManagedServer{
		"query-code": {
			Command: "node",
			Args:    []string{filepath.Join(layout.QueryCodeMCP, "dist", "index.js")},
			CWD:     layout.QueryCodeMCP,
			Env: map[string]string{
				"CODEBASE_INDEX_DIR": layout.CodebaseIndex,
				"WORKSPACE_ROOT":     layout.Root,
			},
		},
		"mempalace": {
			Command: "python3",
			Args:    []string{"-m", "mempalace.mcp_server"},
		},
	}

	githubServer := ManagedServer{
		Type: "http",
		URL:  "https://api.githubcopilot.com/mcp/",
	}
	if profile.Kind == host.HostCodex {
		githubServer.BearerTokenEnvVar = "GITHUB_PAT_TOKEN"
	}
	servers["github"] = githubServer

	return servers
}

func writeJSONConfig(path string, key string, servers map[string]ManagedServer) (ConfigResult, error) {
	config := map[string]any{}
	if existing, err := os.ReadFile(path); err == nil {
		if unmarshalErr := json.Unmarshal(existing, &config); unmarshalErr != nil {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", path), unmarshalErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", path), err)
	}

	section := ensureMap(config, key)
	for name, server := range servers {
		section[name] = server
	}

	content, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("marshal %s", path), err)
	}

	action, err := writeConfigFile(path, content)
	if err != nil {
		return ConfigResult{}, err
	}

	return ConfigResult{Path: path, Action: action}, nil
}

func writeTOMLConfig(path string, servers map[string]ManagedServer) (ConfigResult, error) {
	config := map[string]any{}
	if existing, err := os.ReadFile(path); err == nil {
		if unmarshalErr := toml.Unmarshal(existing, &config); unmarshalErr != nil {
			return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", path), unmarshalErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", path), err)
	}

	section := ensureMap(config, "mcp_servers")
	for name, server := range servers {
		section[name] = server
	}

	content, err := toml.Marshal(config)
	if err != nil {
		return ConfigResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("marshal %s", path), err)
	}

	action, err := writeConfigFile(path, content)
	if err != nil {
		return ConfigResult{}, err
	}

	return ConfigResult{Path: path, Action: action}, nil
}

func ensureMap(root map[string]any, key string) map[string]any {
	if existing, ok := root[key].(map[string]any); ok {
		return existing
	}

	section := map[string]any{}
	root[key] = section
	return section
}

func writeConfigFile(path string, content []byte) (string, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("create directory for %s", path), err)
	}

	existing, err := os.ReadFile(path)
	if err == nil {
		if bytes.Equal(existing, content) {
			return "skipped", nil
		}
		if backupErr := os.WriteFile(path+".bak", existing, 0o644); backupErr != nil {
			return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("backup %s", path), backupErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", path), err)
	}

	if writeErr := os.WriteFile(path, content, 0o644); writeErr != nil {
		return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("write %s", path), writeErr)
	}
	if err == nil {
		return "updated", nil
	}

	return "created", nil
}