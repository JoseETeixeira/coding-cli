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
			cloneRoot, err := resolveCloneRoot(options.FreightHeroRoot)
			if err != nil {
				return err
			}
			dependencies.Logger.Info(fmt.Sprintf("cloning FreightHero repositories into %s", cloneRoot))

			results, err := repos.CloneRepositories(cmd.Context(), dependencies.Runner, cloneRoot, repos.CloneTargets)
			for _, result := range results {
				if result.Skipped {
					dependencies.Logger.Warn(fmt.Sprintf("reused %s at %s", result.Repository, result.Path))
					continue
				}
				dependencies.Logger.Success(fmt.Sprintf("cloned %s into %s", result.Repository, result.Path))
			}
			if err != nil {
				return err
			}

			dependencies.Logger.Success("repository clone flow completed")
			return nil
		},
	}

	return cmd
}