package codingcli

import (
	"fmt"

	"github.com/coding-cli/coding-cli/internal/assets"
	"github.com/coding-cli/coding-cli/internal/config"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newSetupCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "setup",
		Short: "Install configuration and local tooling",
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}

	cmd.AddCommand(
		newSetupAgentCmd(options, dependencies),
		newSetupMCPcmd(options, dependencies),
		newSetupFullCmd(options, dependencies),
	)

	return cmd
}

func newSetupAgentCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	selection := &host.SelectionFlags{}

	cmd := &cobra.Command{
		Use:     "agent",
		Short:   "Install prompts, instructions, agents, and skills for one host",
		Example: "coding-cli setup agent --batman\ncoding-cli setup agent --vscode --workspace-root /path/to/workspace",
		RunE: func(cmd *cobra.Command, _ []string) error {
			logStep(dependencies.Logger, "resolve workspace")
			layout, err := resolveRepoLayout(options.WorkspaceRoot)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using workspace %s", layout.Root))

			logStep(dependencies.Logger, "validate coding-cli workspace")
			if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); err != nil {
				return err
			}
			dependencies.Logger.Success("validated coding-cli workspace")

			logStep(dependencies.Logger, "resolve host profile")
			profile, err := resolveHostProfile(*selection, false)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using %s profile", profile.DisplayName))

			logStep(dependencies.Logger, fmt.Sprintf("sync coding-cli assets for %s", profile.DisplayName))
			results, err := assets.SyncAssets(layout, profile, assets.SyncOptions{Force: options.Force})
			if err != nil {
				return err
			}
			logAssetResults(dependencies.Logger, results)

			if profile.Kind == host.HostClaudeCode {
				logStep(dependencies.Logger, "install Claude Code SessionStart hook")
				hookResult, err := config.InstallClaudeCodeHooks(profile, layout)
				if err != nil {
					return err
				}
				logHookResult(dependencies.Logger, hookResult)

				logStep(dependencies.Logger, "set Claude Code default agent")
				agentResult, err := config.SetClaudeCodeDefaultAgent(profile)
				if err != nil {
					return err
				}
				logDefaultAgentResult(dependencies.Logger, agentResult)
			}

			logStep(dependencies.Logger, "install git guardrails")
			guardrailResult, err := config.InstallGitGuardrails(profile, layout)
			if err != nil {
				return err
			}
			logGuardrailResult(dependencies.Logger, guardrailResult)

			dependencies.Logger.Success("agent asset setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}
