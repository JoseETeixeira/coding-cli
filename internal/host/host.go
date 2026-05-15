package host

import (
	"fmt"
	"strings"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/paths"
	"github.com/spf13/pflag"
)

type HostKind string

const (
	HostVSCode     HostKind = "vscode"
	HostBatman     HostKind = "batman"
	HostClaudeCode HostKind = "claude-code"
	HostCodex      HostKind = "codex"
)

type HostRoots struct {
	PromptDir       string
	InstructionDir  string
	AgentDir        string
	SkillDir        string
	InstructionFile string
	MCPConfigPath   string
	SettingsPath    string
}

type HostProfile struct {
	Kind            HostKind
	DisplayName     string
	Harness         string
	UsesVSCodeRoots bool
	MCPConfigFormat string
	Roots           HostRoots
}

type SelectionFlags struct {
	VSCode     bool
	Batman     bool
	ClaudeCode bool
	Codex      bool
}

func (flags *SelectionFlags) Bind(flagSet *pflag.FlagSet) {
	flagSet.BoolVar(&flags.VSCode, string(HostVSCode), false, "Target VS Code / Copilot user-level configuration")
	flagSet.BoolVar(&flags.Batman, string(HostBatman), false, "Target Batman user-level configuration")
	flagSet.BoolVar(&flags.ClaudeCode, string(HostClaudeCode), false, "Target Claude Code user-level configuration")
	flagSet.BoolVar(&flags.Codex, string(HostCodex), false, "Target Codex user-level configuration")
}

func (flags SelectionFlags) SelectedKinds() []HostKind {
	selected := make([]HostKind, 0, 4)
	if flags.VSCode {
		selected = append(selected, HostVSCode)
	}
	if flags.Batman {
		selected = append(selected, HostBatman)
	}
	if flags.ClaudeCode {
		selected = append(selected, HostClaudeCode)
	}
	if flags.Codex {
		selected = append(selected, HostCodex)
	}

	return selected
}

func (flags SelectionFlags) ExplicitKind() (HostKind, bool, error) {
	selected := flags.SelectedKinds()
	if len(selected) == 0 {
		return "", false, nil
	}
	if len(selected) > 1 {
		return "", false, clierrors.New(clierrors.KindValidation, fmt.Sprintf("select exactly one host: %s", ValidFlagList()))
	}

	return selected[0], true, nil
}

func ResolveProfile(kind HostKind, resolver paths.Resolver) (HostProfile, error) {
	switch kind {
	case HostVSCode:
		return HostProfile{
			Kind:            HostVSCode,
			DisplayName:     "VS Code / Copilot",
			Harness:         "codex",
			UsesVSCodeRoots: true,
			MCPConfigFormat: "vscode-json",
			Roots: HostRoots{
				PromptDir:      resolver.VSCodePromptDir(),
				InstructionDir: resolver.VSCodeInstructionDir(),
				AgentDir:       resolver.VSCodeAgentDir(),
				SkillDir:       resolver.GenericSkillDir(),
				MCPConfigPath:  resolver.VSCodeMCPConfigPath(),
				SettingsPath:   resolver.VSCodeSettingsPath(),
			},
		}, nil
	case HostBatman:
		return HostProfile{
			Kind:            HostBatman,
			DisplayName:     "Batman",
			Harness:         "codex",
			UsesVSCodeRoots: true,
			MCPConfigFormat: "vscode-json",
			Roots: HostRoots{
				PromptDir:      resolver.VSCodePromptDir(),
				InstructionDir: resolver.VSCodeInstructionDir(),
				AgentDir:       resolver.VSCodeAgentDir(),
				SkillDir:       resolver.GenericSkillDir(),
				MCPConfigPath:  resolver.VSCodeMCPConfigPath(),
				SettingsPath:   resolver.VSCodeSettingsPath(),
			},
		}, nil
	case HostClaudeCode:
		return HostProfile{
			Kind:            HostClaudeCode,
			DisplayName:     "Claude Code",
			Harness:         "claude-code",
			MCPConfigFormat: "claude-json",
			Roots: HostRoots{
				PromptDir:       resolver.ClaudeCommandDir(),
				AgentDir:        resolver.ClaudeAgentDir(),
				SkillDir:        resolver.ClaudeSkillDir(),
				InstructionDir:  resolver.ClaudeRoot(),
				InstructionFile: resolver.ClaudeInstructionFile(),
				MCPConfigPath:   resolver.ClaudeConfigPath(),
				SettingsPath:    resolver.ClaudeSettingsPath(),
			},
		}, nil
	case HostCodex:
		return HostProfile{
			Kind:            HostCodex,
			DisplayName:     "Codex",
			Harness:         "codex",
			MCPConfigFormat: "codex-toml",
			Roots: HostRoots{
				PromptDir:       resolver.CodexPromptDir(),
				SkillDir:        resolver.GenericSkillDir(),
				InstructionFile: resolver.CodexInstructionFile(),
				MCPConfigPath:   resolver.CodexConfigPath(),
			},
		}, nil
	default:
		return HostProfile{}, clierrors.New(clierrors.KindValidation, fmt.Sprintf("unsupported host %q; valid options: %s", kind, ValidFlagList()))
	}
}

func ValidFlagList() string {
	return strings.Join([]string{"--vscode", "--batman", "--claude-code", "--codex"}, ", ")
}
