package freighthero

import (
	"fmt"
	"strings"

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

			dependencies.Logger.Info(fmt.Sprintf("verifying MCP dependencies for %s", profile.DisplayName))
			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.DefaultSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			actions, err := index.BuildMCP(cmd.Context(), dependencies.Runner, layout)
			if err != nil {
				return err
			}
			if len(actions) == 0 {
				dependencies.Logger.Info("reused existing freighthero-mcp build artifacts")
			} else {
				dependencies.Logger.Success(fmt.Sprintf("prepared freighthero-mcp (%s)", strings.Join(actions, ", ")))
			}

			configResult, err := config.WriteConfig(profile, layout)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("%s MCP config at %s", configResult.Action, configResult.Path))
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}