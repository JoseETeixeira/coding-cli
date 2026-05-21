package paths

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

type Resolver struct {
	HomeDir   string
	GOOS      string
	lookupEnv func(string) (string, bool)
}

func NewResolver() (Resolver, error) {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return Resolver{}, fmt.Errorf("resolve home directory: %w", err)
	}

	return NewResolverWith(homeDir, runtime.GOOS, os.LookupEnv), nil
}

func NewResolverWith(homeDir string, goos string, lookupEnv func(string) (string, bool)) Resolver {
	if lookupEnv == nil {
		lookupEnv = func(string) (string, bool) {
			return "", false
		}
	}

	return Resolver{
		HomeDir:   homeDir,
		GOOS:      goos,
		lookupEnv: lookupEnv,
	}
}

func (resolver Resolver) ExpandHome(path string) (string, error) {
	if path == "" {
		return "", nil
	}
	if path == "~" {
		return resolver.HomeDir, nil
	}
	if strings.HasPrefix(path, "~/") {
		return filepath.Join(resolver.HomeDir, path[2:]), nil
	}

	return path, nil
}

func (resolver Resolver) VSCodeUserDir() string {
	if path, ok := resolver.lookupExpanded("VSCODE_USER_DIR"); ok {
		return path
	}

	switch resolver.GOOS {
	case "darwin":
		return filepath.Join(resolver.HomeDir, "Library", "Application Support", "Code", "User")
	case "windows":
		if appData, ok := resolver.lookupExpanded("APPDATA"); ok {
			return filepath.Join(appData, "Code", "User")
		}
		return filepath.Join(resolver.HomeDir, "AppData", "Roaming", "Code", "User")
	default:
		return filepath.Join(resolver.HomeDir, ".config", "Code", "User")
	}
}

func (resolver Resolver) VSCodePromptDir() string {
	if path, ok := resolver.lookupExpanded("USER_PROMPTS_DIR", "VSCODE_USER_PROMPTS_FOLDER"); ok {
		return path
	}

	return filepath.Join(resolver.VSCodeUserDir(), "prompts")
}

func (resolver Resolver) VSCodeInstructionDir() string {
	if path, ok := resolver.lookupExpanded("USER_INSTRUCTIONS_DIR"); ok {
		return path
	}

	return resolver.VSCodePromptDir()
}

func (resolver Resolver) VSCodeAgentDir() string {
	if path, ok := resolver.lookupExpanded("USER_AGENTS_DIR"); ok {
		return path
	}

	return resolver.VSCodePromptDir()
}

func (resolver Resolver) GenericSkillDir() string {
	if path, ok := resolver.lookupExpanded("USER_SKILLS_DIR"); ok {
		return path
	}

	return filepath.Join(resolver.HomeDir, ".agents", "skills")
}

func (resolver Resolver) VSCodeMCPConfigPath() string {
	if path, ok := resolver.lookupExpanded("VSCODE_MCP_CONFIG_PATH"); ok {
		return path
	}

	return filepath.Join(resolver.VSCodeUserDir(), "mcp.json")
}

func (resolver Resolver) VSCodeSettingsPath() string {
	if path, ok := resolver.lookupExpanded("VSCODE_SETTINGS_PATH"); ok {
		return path
	}

	return filepath.Join(resolver.VSCodeUserDir(), "settings.json")
}

func (resolver Resolver) ClaudeRoot() string {
	if path, ok := resolver.lookupExpanded("CLAUDE_CONFIG_DIR"); ok {
		return path
	}

	return filepath.Join(resolver.HomeDir, ".claude")
}

func (resolver Resolver) ClaudeCommandDir() string {
	return filepath.Join(resolver.ClaudeRoot(), "commands")
}

func (resolver Resolver) ClaudeAgentDir() string {
	return filepath.Join(resolver.ClaudeRoot(), "agents")
}

func (resolver Resolver) ClaudeSkillDir() string {
	return filepath.Join(resolver.ClaudeRoot(), "skills")
}

func (resolver Resolver) ClaudeInstructionFile() string {
	if path, ok := resolver.lookupExpanded("CLAUDE_INSTRUCTION_FILE"); ok {
		return path
	}

	return filepath.Join(resolver.HomeDir, ".claude", "CLAUDE.md")
}

func (resolver Resolver) ClaudeConfigPath() string {
	if path, ok := resolver.lookupExpanded("CLAUDE_MCP_CONFIG_PATH"); ok {
		return path
	}

	return filepath.Join(resolver.HomeDir, ".claude.json")
}

func (resolver Resolver) ClaudeSettingsPath() string {
	return filepath.Join(resolver.ClaudeRoot(), "settings.json")
}

func (resolver Resolver) CodexRoot() string {
	if path, ok := resolver.lookupExpanded("CODEX_HOME"); ok {
		return path
	}

	return filepath.Join(resolver.HomeDir, ".codex")
}

func (resolver Resolver) CodexPromptDir() string {
	return filepath.Join(resolver.CodexRoot(), "prompts")
}

func (resolver Resolver) CodexInstructionFile() string {
	return filepath.Join(resolver.CodexRoot(), "AGENTS.md")
}

func (resolver Resolver) CodexConfigPath() string {
	return filepath.Join(resolver.CodexRoot(), "config.toml")
}

func (resolver Resolver) lookupExpanded(keys ...string) (string, bool) {
	for _, key := range keys {
		value, ok := resolver.lookupEnv(key)
		if !ok || strings.TrimSpace(value) == "" {
			continue
		}

		expanded, err := resolver.ExpandHome(value)
		if err != nil {
			continue
		}

		return expanded, true
	}

	return "", false
}