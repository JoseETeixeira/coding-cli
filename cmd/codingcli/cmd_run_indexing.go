package codingcli

import (
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/coding-cli/coding-cli/internal/deps"
	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/index"
	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/coding-cli/coding-cli/internal/state"
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
		Use:   "indexing",
		Short: "Refresh the codebase index for the current working directory",
		Long: "Refresh the codebase index for the current working directory.\n\n" +
			"Workspace resolution (the workspace whose query-code-mcp install hosts the venv\n" +
			"and codebase index):\n" +
			"  1. --workspace-root flag\n" +
			"  2. Nearest ancestor of the cwd that contains a coding-cli/ child\n" +
			"  3. The default workspace persisted by the last `coding-cli setup ...` run\n\n" +
			"Indexing target:\n" +
			"  - cwd is the workspace root       -> every top-level project under it is indexed\n" +
			"  - cwd is under the workspace root -> just the top-level project containing the cwd\n" +
			"  - cwd is outside the workspace    -> the cwd itself is indexed as a standalone project",
		Example: "coding-cli run indexing\n" +
			"coding-cli run indexing --workspace-root /path/to/workspace",
		RunE: func(cmd *cobra.Command, _ []string) error {
			cwd, err := os.Getwd()
			if err != nil {
				return clierrors.Wrap(clierrors.KindValidation, "resolve current working directory", err)
			}
			cwd = filepath.Clean(cwd)

			logStep(dependencies.Logger, "resolve workspace")
			layout, source, err := resolveIndexingWorkspace(options.WorkspaceRoot, cwd)
			if err != nil {
				return err
			}
			dependencies.Logger.Success(fmt.Sprintf("using workspace %s (resolved via %s)", layout.Root, source))

			logStep(dependencies.Logger, "verify indexing dependencies")
			dependencyResults, err := deps.VerifyDependencies(cmd.Context(), dependencies.Runner, deps.IndexingSpecs())
			logDependencyResults(dependencies.Logger, dependencyResults)
			if err != nil {
				return err
			}

			target := buildIndexingTarget(layout.Root, cwd, dependencies)
			return runIndexingFlow(cmd.Context(), dependencies, layout, target)
		},
	}

	return cmd
}

// resolveIndexingWorkspace finds the workspace that hosts query-code-mcp:
//   - explicit --workspace-root wins
//   - else walk up from cwd looking for a coding-cli/ child
//   - else fall back to the persisted default workspace
//
// The returned string is a human-readable description of which path won, used
// purely for the success log line.
func resolveIndexingWorkspace(rootOverride string, cwd string) (repos.RepoLayout, string, error) {
	if rootOverride != "" {
		layout, err := repos.GetRepoLayout(rootOverride, cwd)
		if err != nil {
			return repos.RepoLayout{}, "", err
		}
		if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); err != nil {
			return repos.RepoLayout{}, "", err
		}
		return layout, "--workspace-root", nil
	}

	if layout, err := repos.GetRepoLayout("", cwd); err == nil {
		if validateErr := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); validateErr == nil {
			return layout, "cwd ancestry", nil
		}
	}

	persisted, ok, err := state.DefaultWorkspaceRoot()
	if err != nil {
		return repos.RepoLayout{}, "", clierrors.Wrap(clierrors.KindValidation, "load persisted workspace state", err)
	}
	if !ok {
		return repos.RepoLayout{}, "", clierrors.New(clierrors.KindValidation,
			"could not resolve workspace root: cwd is not inside a coding-cli workspace and no default workspace is persisted. "+
				"Run `coding-cli setup full --<host>` once from a workspace, or pass --workspace-root.")
	}
	layout, err := repos.GetRepoLayout(persisted, cwd)
	if err != nil {
		return repos.RepoLayout{}, "", err
	}
	if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); err != nil {
		return repos.RepoLayout{}, "", clierrors.Wrap(clierrors.KindValidation,
			fmt.Sprintf("persisted workspace %s is no longer valid; rerun `coding-cli setup full` from a workspace", persisted), err)
	}
	return layout, "persisted default", nil
}

// buildIndexingTarget decides which projects the cocoindex pipeline should
// index this run, based on where the cwd sits relative to the workspace.
func buildIndexingTarget(workspaceRoot string, cwd string, dependencies Dependencies) index.IndexingTarget {
	workspaceRoot = filepath.Clean(workspaceRoot)
	cwd = filepath.Clean(cwd)

	if pathsEqual(cwd, workspaceRoot) {
		dependencies.Logger.Info("cwd is the workspace root; indexing every top-level project")
		return index.IndexingTarget{}
	}

	if rel, ok := childPath(workspaceRoot, cwd); ok && rel != "" {
		project := topLevelProject(rel)
		dependencies.Logger.Info(fmt.Sprintf("cwd is under the workspace root; indexing project %q", project))
		return index.IndexingTarget{Projects: []string{project}}
	}

	displayName := externalProjectName(cwd)
	dependencies.Logger.Info(fmt.Sprintf("cwd is outside the workspace; indexing it as standalone project %q", displayName))
	return index.IndexingTarget{
		ProjectPaths: []index.ProjectPath{{Name: displayName, Path: cwd}},
	}
}

// pathsEqual compares two filesystem paths case-sensitively on Unix and
// case-insensitively on Windows (where filesystems are typically case-folding).
func pathsEqual(a, b string) bool {
	if a == b {
		return true
	}
	if filepath.Separator == '\\' {
		return strings.EqualFold(a, b)
	}
	return false
}

// childPath returns the path of child relative to parent if child is a
// descendant of (or equal to) parent. The boolean indicates whether the
// relationship holds.
func childPath(parent, child string) (string, bool) {
	rel, err := filepath.Rel(parent, child)
	if err != nil {
		return "", false
	}
	if rel == "." {
		return "", true
	}
	if strings.HasPrefix(rel, "..") {
		return "", false
	}
	return rel, true
}

// topLevelProject returns the first path component of a relative path, e.g.
// "project-a/src/handlers" → "project-a". Callers must ensure the input is a
// non-empty relative path.
func topLevelProject(rel string) string {
	rel = filepath.ToSlash(rel)
	if idx := strings.IndexByte(rel, '/'); idx >= 0 {
		return rel[:idx]
	}
	return rel
}

// externalProjectName builds a stable, unique display name for a cwd that
// lives outside the workspace. Basename alone risks colliding when two
// projects share a name, so we suffix with a 6-char hash of the absolute path.
func externalProjectName(abs string) string {
	base := filepath.Base(abs)
	if base == "" || base == "." || base == string(filepath.Separator) {
		base = "external"
	}
	sum := sha1.Sum([]byte(filepath.Clean(abs)))
	return fmt.Sprintf("%s-%s", base, hex.EncodeToString(sum[:3]))
}
