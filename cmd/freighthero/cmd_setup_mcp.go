package freighthero

import (
	"fmt"

	"github.com/Freight-Hero/coding-cli/internal/config"
	"github.com/Freight-Hero/coding-cli/internal/deps"
	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/index"
	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newSetupMCPcmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	selection := &host.SelectionFlags{}

	cmd := &cobra.Command{
		Use:     "mcp",
		Short:   "Configure FreightHero MCP integrations for one host",
		Example: "freighthero setup mcp --codex\nfreighthero setup mcp --claude-code --verbose",
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
			profile, err := resolveHostProfile(*selection, true)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using %s profile", profile.DisplayName))

			logStep(dependencies.Logger, fmt.Sprintf("verify dependencies for %s", profile.DisplayName))
			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.SetupMCPSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

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
			dependencies.Logger.Success("MCP setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}