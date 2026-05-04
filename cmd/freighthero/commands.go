package freighthero

import "github.com/spf13/cobra"

func Execute() error {
	return NewRootCommand(defaultDependencies()).Execute()
}

func NewRootCommand(dependencies Dependencies) *cobra.Command {
	options := &GlobalOptions{}

	cmd := &cobra.Command{
		Use:           "freighthero",
		Short:         "FreightHero onboarding and setup CLI",
		Long:          "FreightHero CLI bootstraps local repositories, assistant assets, MCP config, and indexing.",
		SilenceUsage:  true,
		SilenceErrors: true,
		PersistentPreRun: func(_ *cobra.Command, _ []string) {
			dependencies.Logger.SetVerbose(options.Verbose)
		},
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}

	cmd.PersistentFlags().StringVar(
		&options.FreightHeroRoot,
		"freighthero-root",
		"",
		"Absolute path to the FreightHero workspace root",
	)
	cmd.PersistentFlags().BoolVar(
		&options.Force,
		"force",
		false,
		"Replace or rewrite FreightHero-managed files even when they differ",
	)
	cmd.PersistentFlags().BoolVar(
		&options.Verbose,
		"verbose",
		false,
		"Print verbose diagnostics for subprocess execution and config changes",
	)

	cmd.AddCommand(
		newRepositoriesCmd(options, dependencies),
		newSetupCmd(options, dependencies),
		newRunCmd(options, dependencies),
	)

	return cmd
}