package index

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/coding-cli/coding-cli/internal/runner"
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

func BootstrapIndexing(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) (BootstrapResult, error) {
	if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI); err != nil {
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

	cocoindexResult, err := RunCocoIndex(ctx, processRunner, layout)
	if err != nil {
		return result, err
	}
	result.CocoIndex = cocoindexResult

	return result, nil
}

func BuildMCP(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) ([]StepResult, error) {
	if !directoryExists(layout.QueryCodeMCP) {
		return nil, clierrors.New(clierrors.KindIndex, fmt.Sprintf("missing query-code-mcp at %s", layout.QueryCodeMCP))
	}

	actions := make([]StepResult, 0, 2)
	if !directoryExists(filepath.Join(layout.QueryCodeMCP, "node_modules")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "npm", Args: []string{"install"}, Dir: layout.QueryCodeMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "npm install query-code-mcp", err)
		}
		actions = append(actions, completedStep("query-code-mcp npm dependencies", "installed node_modules"))
	} else {
		actions = append(actions, skippedStep("query-code-mcp npm dependencies", "node_modules already present"))
	}
	if !fileExists(filepath.Join(layout.QueryCodeMCP, "dist", "index.js")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "npm", Args: []string{"run", "build"}, Dir: layout.QueryCodeMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "build query-code-mcp", err)
		}
		actions = append(actions, completedStep("query-code-mcp build", "generated dist/index.js"))
	} else {
		actions = append(actions, skippedStep("query-code-mcp build", "dist/index.js already present"))
	}

	return actions, nil
}

func EnsureIndexingEnvironment(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) ([]StepResult, error) {
	actions := make([]StepResult, 0, 2)
	if !directoryExists(filepath.Join(layout.QueryCodeMCP, ".venv")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "python3", Args: []string{"-m", "venv", ".venv"}, Dir: layout.QueryCodeMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "create query-code-mcp virtualenv", err)
		}
		actions = append(actions, completedStep("query-code-mcp virtualenv", "created .venv"))
	} else {
		actions = append(actions, skippedStep("query-code-mcp virtualenv", ".venv already present"))
	}
	if !fileExists(venvExecutable(layout.QueryCodeMCP, "cocoindex")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: venvExecutable(layout.QueryCodeMCP, "pip"), Args: []string{"install", "-r", "requirements.txt"}, Dir: layout.QueryCodeMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "install query-code-mcp python requirements", err)
		}
		actions = append(actions, completedStep("query-code-mcp python requirements", "installed requirements.txt"))
	} else {
		actions = append(actions, skippedStep("query-code-mcp python requirements", "cocoindex executable already present"))
	}

	return actions, nil
}

func RunMemPalace(ctx context.Context, processRunner runner.ProcessRunner) (StepResult, error) {
	if err := processRunner.RunStreaming(ctx, runner.Command{Name: "python3", Args: []string{"-m", "mempalace", "wake-up"}}, os.Stdout, os.Stderr); err != nil {
		return StepResult{}, clierrors.Wrap(clierrors.KindIndex, "wake up mempalace", err)
	}

	return completedStep("mempalace wake-up", "refreshed mempalace context"), nil
}

func RunCocoIndex(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) (StepResult, error) {
	if err := os.MkdirAll(filepath.Join(layout.QueryCodeMCP, ".cocoindex"), 0o755); err != nil {
		return StepResult{}, clierrors.Wrap(clierrors.KindIndex, "create .cocoindex directory", err)
	}

	command := runner.Command{
		Name: venvExecutable(layout.QueryCodeMCP, "cocoindex"),
		Args: []string{"update", "codebase_index.py"},
		Dir:  layout.QueryCodeMCP,
		Env: []string{
			"WORKSPACE_ROOT=" + layout.Root,
			"CODEBASE_INDEX_DIR=" + layout.CodebaseIndex,
		},
	}
	if err := processRunner.RunStreaming(ctx, command, os.Stdout, os.Stderr); err != nil {
		return StepResult{}, clierrors.Wrap(clierrors.KindIndex, "run cocoindex update", err)
	}

	return completedStep("cocoindex update", fmt.Sprintf("refreshed %s", layout.CodebaseIndex)), nil
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
