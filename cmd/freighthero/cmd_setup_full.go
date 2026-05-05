package freighthero

import (
	"fmt"

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

			logStep(dependencies.Logger, fmt.Sprintf("clone sibling repositories under %s", layout.Root))
			cloneResults, err := repos.CloneRepositories(cmd.Context(), dependencies.Runner, layout.Root, repos.CloneTargets)
			logCloneResults(dependencies.Logger, cloneResults)
			if err != nil {
				return err
			}

			logStep(dependencies.Logger, "resolve host profile")
			profile, err := resolveHostProfile(*selection, true)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using %s profile", profile.DisplayName))

			logStep(dependencies.Logger, "verify dependencies")
			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.SetupFullSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			logStep(dependencies.Logger, fmt.Sprintf("sync FreightHero assets for %s", profile.DisplayName))
			assetResults, err := assets.SyncAssets(layout, profile, assets.SyncOptions{Force: options.Force})
			if err != nil {
				return err
			}
			logAssetResults(dependencies.Logger, assetResults)

			logStep(dependencies.Logger, "prepare freighthero-mcp")
			buildResults, err := index.BuildMCP(cmd.Context(), dependencies.Runner, layout)
			if err != nil {
				return err
			}
			logBuildResults(dependencies.Logger, buildResults)

			logStep(dependencies.Logger, "write MCP config")
			configResult, err := config.WriteConfig(profile, layout)
			if err != nil {
				return err
			}
			logConfigResult(dependencies.Logger, configResult)

			logStep(dependencies.Logger, "verify indexing dependencies")
			indexDependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.IndexingSpecs())
			logDependencyResults(dependencies.Logger, indexDependencyResults)
			if err != nil {
				return err
			}

			if err := runIndexingFlow(cmd.Context(), dependencies, layout); err != nil {
				return err
			}

			dependencies.Logger.Success("full FreightHero setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}