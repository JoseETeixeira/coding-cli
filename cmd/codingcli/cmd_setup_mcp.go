package codingcli

import (
	"fmt"

	"github.com/coding-cli/coding-cli/internal/config"
	"github.com/coding-cli/coding-cli/internal/deps"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/index"
	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newSetupMCPcmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	selection := &host.SelectionFlags{}

	cmd := &cobra.Command{
		Use:     "mcp",
		Short:   "Configure MCP integrations for one host",
		Example: "coding-cli setup mcp --codex\ncoding-cli setup mcp --claude-code --verbose",
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

			logStep(dependencies.Logger, "prepare query-code-mcp")
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
