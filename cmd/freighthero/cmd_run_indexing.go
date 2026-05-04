package freighthero

import (
	"github.com/Freight-Hero/coding-cli/internal/deps"
	"github.com/Freight-Hero/coding-cli/internal/index"
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
			layout, err := resolveRepoLayout(options.FreightHeroRoot)
			if err != nil {
				return err
			}

			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.DefaultSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			if err := index.BootstrapIndexing(cmd.Context(), dependencies.Runner, layout); err != nil {
				return err
			}

			dependencies.Logger.Success("indexing bootstrap completed")
			return nil
		},
	}

	return cmd
}