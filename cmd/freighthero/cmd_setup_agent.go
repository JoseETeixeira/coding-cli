package freighthero

import (
	"fmt"

	"github.com/Freight-Hero/coding-cli/internal/assets"
	"github.com/Freight-Hero/coding-cli/internal/config"
	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newSetupCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "setup",
		Short: "Install FreightHero configuration and local tooling",
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
		Short:   "Install FreightHero prompts, instructions, agents, and skills for one host",
		Example: "freighthero setup agent --batman\nfreighthero setup agent --vscode --freighthero-root /path/to/freighthero",
		RunE: func(cmd *cobra.Command, _ []string) error {
			logStep(dependencies.Logger, "resolve FreightHero workspace")
			layout, err := resolveRepoLayout(options.FreightHeroRoot)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using FreightHero workspace %s", layout.Root))

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

			logStep(dependencies.Logger, fmt.Sprintf("sync FreightHero assets for %s", profile.DisplayName))
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
			}

			logStep(dependencies.Logger, fmt.Sprintf("install git guardrails for %s", profile.DisplayName))
			guardrailResult, err := config.InstallGitGuardrails(profile, layout)
			if err != nil {
				return err
			}
			logHookResult(dependencies.Logger, guardrailResult)

			dependencies.Logger.Success("agent asset setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}