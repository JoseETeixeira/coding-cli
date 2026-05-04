package freighthero

import (
	"fmt"
	"strings"

	"github.com/Freight-Hero/coding-cli/internal/assets"
	"github.com/Freight-Hero/coding-cli/internal/config"
	"github.com/Freight-Hero/coding-cli/internal/deps"
	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/index"
	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newSetupFullCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	selection := &host.SelectionFlags{}

	cmd := &cobra.Command{
		Use:     "full",
		Short:   "Run the full FreightHero onboarding flow",
		Example: "freighthero setup full --batman\nfreighthero setup full",
		RunE: func(cmd *cobra.Command, _ []string) error {
			layout, err := resolveRepoLayout(options.FreightHeroRoot)
			if err != nil {
				return err
			}
			if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); err != nil {
				return err
			}

			dependencies.Logger.Info(fmt.Sprintf("ensuring sibling repositories under %s", layout.Root))
			cloneResults, err := repos.CloneRepositories(cmd.Context(), dependencies.Runner, layout.Root, repos.CloneTargets)
			for _, result := range cloneResults {
				if result.Skipped {
					dependencies.Logger.Warn(fmt.Sprintf("reused %s at %s", result.Repository, result.Path))
					continue
				}
				dependencies.Logger.Success(fmt.Sprintf("cloned %s into %s", result.Repository, result.Path))
			}
			if err != nil {
				return err
			}

			profile, err := resolveHostProfile(*selection, true)
			if err != nil {
				return err
			}

			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.DefaultSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			assetResults, err := assets.SyncAssets(layout, profile, assets.SyncOptions{Force: options.Force})
			if err != nil {
				return err
			}
			for _, result := range assetResults {
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

			actions, err := index.BuildMCP(cmd.Context(), dependencies.Runner, layout)
			if err != nil {
				return err
			}
			if len(actions) > 0 {
				dependencies.Logger.Success(fmt.Sprintf("prepared freighthero-mcp (%s)", strings.Join(actions, ", ")))
			}

			configResult, err := config.WriteConfig(profile, layout)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("%s MCP config at %s", configResult.Action, configResult.Path))

			if err := index.BootstrapIndexing(cmd.Context(), dependencies.Runner, layout); err != nil {
				return err
			}

			dependencies.Logger.Success("full FreightHero setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}