package codingcli

import (
	"fmt"
	"os"

	"github.com/coding-cli/coding-cli/internal/assets"
	"github.com/coding-cli/coding-cli/internal/config"
	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/update"
	"github.com/coding-cli/coding-cli/internal/version"
	"github.com/spf13/cobra"
)

func newUpdateCmd(options *GlobalOptions, dependencies Dependencies) *cobra.Command {
	selection := &host.SelectionFlags{}
	var owner, repo, tag string
	var skipBinary bool

	cmd := &cobra.Command{
		Use:   "update",
		Short: "Download the latest release and refresh prompts, skills, hooks, and the binary",
		Long: "Update resolves the latest coding-cli release (or --tag), downloads its source\n" +
			"archive, overlays the shipped prompts/skills/hooks onto the workspace source\n" +
			"tree, re-syncs them to the host, and self-replaces the binary.\n\n" +
			"Workspace resolution matches `run indexing`:\n" +
			"  1. --workspace-root flag\n" +
			"  2. Nearest ancestor of the cwd that contains a coding-cli/ child\n" +
			"  3. The default workspace persisted by the last `coding-cli setup ...` run",
		Example: "coding-cli update\n" +
			"coding-cli update --tag v0.3.0\n" +
			"coding-cli update --skip-binary",
		RunE: func(cmd *cobra.Command, _ []string) error {
			cwd, err := os.Getwd()
			if err != nil {
				return clierrors.Wrap(clierrors.KindValidation, "resolve current working directory", err)
			}

			logStep(dependencies.Logger, "resolve workspace")
			layout, source, err := resolveIndexingWorkspace(options.WorkspaceRoot, cwd)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using workspace %s (resolved via %s)", layout.Root, source))

			logStep(dependencies.Logger, "resolve host profile")
			profile, err := resolveHostProfile(*selection, true)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using %s profile", profile.DisplayName))

			client := update.NewClient()

			logStep(dependencies.Logger, "resolve release tag")
			resolvedTag := tag
			if resolvedTag == "" {
				resolvedTag, err = client.LatestTag(cmd.Context(), owner, repo)
				if err != nil {
					return err
				}
			}
			dependencies.Logger.Success(fmt.Sprintf("target release %s (installed %s)", resolvedTag, version.Version))

			if !options.Force && tag == "" && !update.IsNewer(resolvedTag, version.Version) {
				dependencies.Logger.Info(fmt.Sprintf("already up to date with %s; pass --force or --tag to reapply", resolvedTag))
				return nil
			}

			tmpDir, err := os.MkdirTemp("", "coding-cli-update-")
			if err != nil {
				return clierrors.Wrap(clierrors.KindConfig, "create temp directory", err)
			}
			defer func() { _ = os.RemoveAll(tmpDir) }()

			logStep(dependencies.Logger, fmt.Sprintf("download %s/%s source for %s", owner, repo, resolvedTag))
			extractedRoot, err := client.DownloadSource(cmd.Context(), owner, repo, resolvedTag, tmpDir)
			if err != nil {
				return err
			}
			dependencies.Logger.Success("downloaded release source")

			logStep(dependencies.Logger, "overlay shipped prompts/skills/hooks")
			applied, err := update.OverlayAssets(extractedRoot, layout.CodingCLI, update.AssetSubdirs)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("overlaid %v onto %s", applied, layout.CodingCLI))

			logStep(dependencies.Logger, fmt.Sprintf("sync coding-cli assets for %s", profile.DisplayName))
			assetResults, err := assets.SyncAssets(layout, profile, assets.SyncOptions{Force: true})
			if err != nil {
				return err
			}
			logAssetResults(dependencies.Logger, assetResults)

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

				logStep(dependencies.Logger, "set Claude Code default agent")
				agentResult, err := config.SetClaudeCodeDefaultAgent(profile)
				if err != nil {
					return err
				}
				logDefaultAgentResult(dependencies.Logger, agentResult)
			}

			if skipBinary {
				dependencies.Logger.Info("skipping binary replacement (--skip-binary)")
			} else {
				logStep(dependencies.Logger, "download and replace binary")
				binaryPath, err := client.DownloadBinary(cmd.Context(), owner, repo, resolvedTag, tmpDir)
				if err != nil {
					return err
				}
				if err := update.ReplaceExecutable(binaryPath); err != nil {
					return err
				}
				dependencies.Logger.Success(fmt.Sprintf("replaced binary with %s", resolvedTag))
			}

			dependencies.Logger.Success(fmt.Sprintf("coding-cli updated to %s", resolvedTag))
			return nil
		},
	}

	selection.Bind(cmd.Flags())
	cmd.Flags().StringVar(&owner, "owner", update.DefaultOwner, "GitHub owner/org that publishes coding-cli releases")
	cmd.Flags().StringVar(&repo, "repo", update.DefaultRepo, "GitHub repository name")
	cmd.Flags().StringVar(&tag, "tag", "", "Release tag to install (default: latest published release)")
	cmd.Flags().BoolVar(&skipBinary, "skip-binary", false, "Only refresh assets/hooks/config; do not replace the binary")

	return cmd
}
