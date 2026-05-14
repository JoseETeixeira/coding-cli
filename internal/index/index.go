package index

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/pyexec"
	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type StepResult struct {
	Name   string
	Action string
	Detail string
}

type BootstrapResult struct {
	Build       []StepResult
	Environment []StepResult
	MemPalace   StepResult
	CocoIndex   StepResult
}

// ProjectPath names a project that lives outside the workspace tree. The
// CocoIndex pipeline reads these via CODEBASE_PROJECT_PATHS so we can index
// the cwd without symlinking it into the workspace.
type ProjectPath struct {
	Name string
	Path string
}

// IndexingTarget scopes a single run. Empty target = index every top-level
// project under the workspace (legacy behavior). Projects filters to a
// subset of in-workspace projects by name. ProjectPaths adds external
// absolute paths to the indexed set.
type IndexingTarget struct {
	Projects     []string
	ProjectPaths []ProjectPath
}

func BootstrapIndexing(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) (BootstrapResult, error) {
	return BootstrapIndexingWithTarget(ctx, processRunner, layout, IndexingTarget{})
}

// BootstrapIndexingWithTarget runs the full indexing flow scoped by ``target``.
// Use ``IndexingTarget{}`` (the zero value) for the historical "index
// everything" behavior.
func BootstrapIndexingWithTarget(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout, target IndexingTarget) (BootstrapResult, error) {
	if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI, repos.RepositoryFrontend, repos.RepositoryBackend, repos.RepositoryAIWatchtower); err != nil {
		return BootstrapResult{}, err
	}

	result := BootstrapResult{}

	buildResults, err := BuildMCP(ctx, processRunner, layout)
	if err != nil {
		return result, err
	}
	result.Build = buildResults

	environmentResults, err := EnsureIndexingEnvironment(ctx, processRunner, layout)
	if err != nil {
		return result, err
	}
	result.Environment = environmentResults

	mempalaceResult, err := RunMemPalace(ctx, processRunner)
	if err != nil {
		return result, err
	}
	result.MemPalace = mempalaceResult

	cocoindexResult, err := RunCocoIndexWithTarget(ctx, processRunner, layout, target)
	if err != nil {
		return result, err
	}
	result.CocoIndex = cocoindexResult

	return result, nil
}

func BuildMCP(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) ([]StepResult, error) {
	if !directoryExists(layout.FreightHeroMCP) {
		return nil, clierrors.New(clierrors.KindIndex, fmt.Sprintf("missing freighthero-mcp at %s", layout.FreightHeroMCP))
	}

	actions := make([]StepResult, 0, 2)
	if !directoryExists(filepath.Join(layout.FreightHeroMCP, "node_modules")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "npm", Args: []string{"install"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "npm install freighthero-mcp", err)
		}
		actions = append(actions, completedStep("freighthero-mcp npm dependencies", "installed node_modules"))
	} else {
		actions = append(actions, skippedStep("freighthero-mcp npm dependencies", "node_modules already present"))
	}
	if !fileExists(filepath.Join(layout.FreightHeroMCP, "dist", "index.js")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "npm", Args: []string{"run", "build"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "build freighthero-mcp", err)
		}
		actions = append(actions, completedStep("freighthero-mcp build", "generated dist/index.js"))
	} else {
		actions = append(actions, skippedStep("freighthero-mcp build", "dist/index.js already present"))
	}

	return actions, nil
}

func EnsureIndexingEnvironment(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) ([]StepResult, error) {
	actions := make([]StepResult, 0, 2)
	if !directoryExists(filepath.Join(layout.FreightHeroMCP, ".venv")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "python3", Args: []string{"-m", "venv", ".venv"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "create freighthero-mcp virtualenv", err)
		}
		actions = append(actions, completedStep("freighthero-mcp virtualenv", "created .venv"))
	} else {
		actions = append(actions, skippedStep("freighthero-mcp virtualenv", ".venv already present"))
	}
	if !fileExists(venvExecutable(layout.FreightHeroMCP, "cocoindex")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: venvExecutable(layout.FreightHeroMCP, "pip"), Args: []string{"install", "-r", "requirements.txt"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "install freighthero-mcp python requirements", err)
		}
		actions = append(actions, completedStep("freighthero-mcp python requirements", "installed requirements.txt"))
	} else {
		actions = append(actions, skippedStep("freighthero-mcp python requirements", "cocoindex executable already present"))
	}

	return actions, nil
}

func RunMemPalace(ctx context.Context, processRunner runner.ProcessRunner) (StepResult, error) {
	// pyexec picks the right Python invocation per OS so this works on Windows
	// where `python3` resolves to the Microsoft Store stub.
	pyCmd, pyArgs := pyexec.Command()
	args := append(append([]string{}, pyArgs...), "-m", "mempalace", "wake-up")
	if err := processRunner.RunStreaming(ctx, runner.Command{Name: pyCmd, Args: args}, os.Stdout, os.Stderr); err != nil {
		return StepResult{}, clierrors.Wrap(clierrors.KindIndex, "wake up mempalace", err)
	}

	return completedStep("mempalace wake-up", "refreshed mempalace context"), nil
}

// RunCocoIndex is the legacy entry point that indexes every top-level project
// under ``layout.Root``. Prefer :func:`RunCocoIndexWithTarget` when the caller
// has a concrete scope (a single project, or an external path).
func RunCocoIndex(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) (StepResult, error) {
	return RunCocoIndexWithTarget(ctx, processRunner, layout, IndexingTarget{})
}

// RunCocoIndexWithTarget invokes the cocoindex pipeline scoped by ``target``.
//
// Environment plumbing into the pipeline:
//
//   - ``CODEBASE_PROJECTS``       — comma-joined list of in-workspace projects
//     (e.g. ``"backend,frontend"``). When set, the pipeline indexes only
//     those.
//   - ``CODEBASE_PROJECT_PATHS``  — comma-joined ``name=/abs/path`` pairs for
//     projects living outside the workspace. The pipeline registers each as
//     a standalone project under the workspace host.
//
// Both variables are read by ``freighthero-mcp/codebase_index.py``.
func RunCocoIndexWithTarget(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout, target IndexingTarget) (StepResult, error) {
	if err := os.MkdirAll(filepath.Join(layout.FreightHeroMCP, ".cocoindex"), 0o755); err != nil {
		return StepResult{}, clierrors.Wrap(clierrors.KindIndex, "create .cocoindex directory", err)
	}

	env := []string{
		"FREIGHTHERO_REPO_ROOT=" + layout.Root,
		"CODEBASE_INDEX_DIR=" + layout.CodebaseIndex,
	}
	if len(target.Projects) > 0 {
		env = append(env, "CODEBASE_PROJECTS="+strings.Join(target.Projects, ","))
	}
	if len(target.ProjectPaths) > 0 {
		pairs := make([]string, 0, len(target.ProjectPaths))
		for _, pp := range target.ProjectPaths {
			pairs = append(pairs, pp.Name+"="+pp.Path)
		}
		env = append(env, "CODEBASE_PROJECT_PATHS="+strings.Join(pairs, ","))
	}

	command := runner.Command{
		Name: venvExecutable(layout.FreightHeroMCP, "cocoindex"),
		Args: []string{"update", "codebase_index.py"},
		Dir:  layout.FreightHeroMCP,
		Env:  env,
	}
	if err := processRunner.RunStreaming(ctx, command, os.Stdout, os.Stderr); err != nil {
		return StepResult{}, clierrors.Wrap(clierrors.KindIndex, "run cocoindex update", err)
	}

	detail := fmt.Sprintf("refreshed %s", layout.CodebaseIndex)
	switch {
	case len(target.ProjectPaths) > 0:
		names := make([]string, 0, len(target.ProjectPaths))
		for _, pp := range target.ProjectPaths {
			names = append(names, pp.Name)
		}
		detail = fmt.Sprintf("refreshed %s (external projects: %s)", layout.CodebaseIndex, strings.Join(names, ", "))
	case len(target.Projects) > 0:
		detail = fmt.Sprintf("refreshed %s (projects: %s)", layout.CodebaseIndex, strings.Join(target.Projects, ", "))
	}
	return completedStep("cocoindex update", detail), nil
}

func completedStep(name string, detail string) StepResult {
	return StepResult{Name: name, Action: "completed", Detail: detail}
}

func skippedStep(name string, detail string) StepResult {
	return StepResult{Name: name, Action: "skipped", Detail: detail}
}

func venvExecutable(root string, name string) string {
	if runtime.GOOS == "windows" {
		return filepath.Join(root, ".venv", "Scripts", name+".exe")
	}

	return filepath.Join(root, ".venv", "bin", name)
}

func directoryExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}
