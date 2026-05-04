package freighthero

import (
	"fmt"

	"github.com/Freight-Hero/coding-cli/internal/assets"
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
			layout, err := resolveRepoLayout(options.FreightHeroRoot)
			if err != nil {
				return err
			}
			if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); err != nil {
				return err
			}

			profile, err := resolveHostProfile(*selection, false)
			if err != nil {
				return err
			}

			dependencies.Logger.Info(fmt.Sprintf("installing FreightHero assets for %s", profile.DisplayName))
			results, err := assets.SyncAssets(layout, profile, assets.SyncOptions{Force: options.Force})
			if err != nil {
				return err
			}
			for _, result := range results {
				switch result.Action {
				case "created", "updated":
					dependencies.Logger.Success(fmt.Sprintf("%s %s", result.Action, result.Destination))
				case "skipped-conflict":
					dependencies.Logger.Warn(fmt.Sprintf("skipped conflicting %s; rerun with --force to replace it", result.Destination))
				case "skipped-unsupported":
					dependencies.Logger.Warn(fmt.Sprintf("skipped unsupported %s asset %s", result.AssetType, result.Source))
				default:
					if result.Destination != "" {
						dependencies.Logger.Info(fmt.Sprintf("skipped unchanged %s", result.Destination))
					}
				}
			}

			dependencies.Logger.Success("agent asset setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}