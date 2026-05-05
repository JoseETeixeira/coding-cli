package freighthero

import (
	"fmt"

	"github.com/Freight-Hero/coding-cli/internal/deps"
	"github.com/spf13/cobra"
)

func newRunCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "run",
		Short: "Run FreightHero local maintenance tasks",
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
		Example: "freighthero run indexing\nfreighthero run indexing --freighthero-root /path/to/freighthero",
		RunE: func(cmd *cobra.Command, _ []string) error {
			logStep(dependencies.Logger, "resolve FreightHero workspace")
			layout, err := resolveRepoLayout(options.FreightHeroRoot)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using FreightHero workspace %s", layout.Root))

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