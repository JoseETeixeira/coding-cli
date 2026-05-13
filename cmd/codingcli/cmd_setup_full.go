package codingcli

import (
	"fmt"

	"github.com/coding-cli/coding-cli/internal/assets"
	"github.com/coding-cli/coding-cli/internal/config"
	"github.com/coding-cli/coding-cli/internal/deps"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/index"
	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newSetupFullCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	selection := &host.SelectionFlags{}

	cmd := &cobra.Command{
		Use:     "full",
		Short:   "Run the full onboarding flow (assets + MCP + indexing)",
		Example: "coding-cli setup full --batman\ncoding-cli setup full",
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

			logStep(dependencies.Logger, "verify dependencies")
			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.SetupFullSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			logStep(dependencies.Logger, fmt.Sprintf("sync coding-cli assets for %s", profile.DisplayName))
			assetResults, err := assets.SyncAssets(layout, profile, assets.SyncOptions{Force: options.Force})
			if err != nil {
				return err
			}
			logAssetResults(dependencies.Logger, assetResults)

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

			if profile.Kind == host.HostClaudeCode {
				logStep(dependencies.Logger, "install Claude Code SessionStart hook")
				hookResult, err := config.InstallClaudeCodeHooks(profile, layout)
				if err != nil {
					return err
				}
				logHookResult(dependencies.Logger, hookResult)
			}

			logStep(dependencies.Logger, "verify indexing dependencies")
			indexDependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.IndexingSpecs())
			logDependencyResults(dependencies.Logger, indexDependencyResults)
			if err != nil {
				return err
			}

			if err := runIndexingFlow(cmd.Context(), dependencies, layout); err != nil {
				return err
			}

			dependencies.Logger.Success("full coding-cli setup completed")
			return nil
		},
	}

	selection.Bind(cmd.Flags())

	return cmd
}
