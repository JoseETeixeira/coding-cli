package freighthero

import (
	"fmt"

	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/spf13/cobra"
)

func newRepositoriesCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "repositories",
		Short: "Manage FreightHero repository checkouts",
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}

	cmd.AddCommand(newRepositoriesCloneCmd(options, dependencies))

	return cmd
}

func newRepositoriesCloneCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	cmd := &cobra.Command{
		Use:     "clone",
		Short:   "Clone the core FreightHero repositories",
		Example: "freighthero repositories clone\nfreighthero repositories clone --freighthero-root /path/to/freighthero",
		RunE: func(cmd *cobra.Command, _ []string) error {
			logStep(dependencies.Logger, "resolve clone root")
			cloneRoot, err := resolveCloneRoot(options.FreightHeroRoot)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using clone root %s", cloneRoot))

			logStep(dependencies.Logger, "clone FreightHero repositories")
			results, err := repos.CloneRepositories(cmd.Context(), dependencies.Runner, cloneRoot, repos.CloneTargets)
			logCloneResults(dependencies.Logger, results)
			if err != nil {
				return err
			}

			dependencies.Logger.Success("repository clone flow completed")
			return nil
		},
	}

	return cmd
}