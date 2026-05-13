package codingcli

import (
	"fmt"

	"github.com/coding-cli/coding-cli/internal/deps"
	"github.com/spf13/cobra"
)

func newRunCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "run",
		Short: "Run coding-cli local maintenance tasks",
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}

	cmd.AddCommand(newRunIndexingCmd(options, dependencies))

	return cmd
}

func newRunIndexingCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:     "indexing",
		Short:   "Build local index prerequisites and refresh the codebase index",
		Example: "coding-cli run indexing\ncoding-cli run indexing --workspace-root /path/to/workspace",
		RunE: func(cmd *cobra.Command, _ []string) error {
			logStep(dependencies.Logger, "resolve workspace")
			layout, err := resolveRepoLayout(options.WorkspaceRoot)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using workspace %s", layout.Root))

			logStep(dependencies.Logger, "verify indexing dependencies")
			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.IndexingSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			return runIndexingFlow(cmd.Context(), dependencies, layout)
		},
	}

	return cmd
}
