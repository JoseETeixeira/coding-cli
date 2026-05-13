package codingcli

import "github.com/spf13/cobra"

func Execute() error {
	return NewRootCommand(defaultDependencies()).Execute()
}

func NewRootCommand(dependencies Dependencies) *cobra.Command {
	options := &GlobalOptions{}

	cmd := &cobra.Command{
		Use:           "coding-cli",
		Short:         "Coding workspace onboarding and setup CLI",
		Long:          "coding-cli bootstraps assistant assets, MCP config, and codebase indexing for a workspace.",
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
		&options.WorkspaceRoot,
		"workspace-root",
		"",
		"Absolute path to the workspace root containing the coding-cli/ directory",
	)
	cmd.PersistentFlags().BoolVar(
		&options.Force,
		"force",
		false,
		"Replace or rewrite coding-cli-managed files even when they differ",
	)
	cmd.PersistentFlags().BoolVar(
		&options.Verbose,
		"verbose",
		false,
		"Print verbose diagnostics for subprocess execution and config changes",
	)

	cmd.AddCommand(
		newSetupCmd(options, dependencies),
		newRunCmd(options, dependencies),
	)

	return cmd
}
