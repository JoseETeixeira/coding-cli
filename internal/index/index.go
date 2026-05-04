package index

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/Freight-Hero/coding-cli/internal/runner"
)

func BootstrapIndexing(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) error {
	if err := repos.ValidateLayout(layout, repos.RepositoryCodingCLI, repos.RepositoryFrontend, repos.RepositoryBackend, repos.RepositoryAIWatchtower); err != nil {
		return err
	}
	if _, err := BuildMCP(ctx, processRunner, layout); err != nil {
		return err
	}
	if err := RunMemPalace(ctx, processRunner); err != nil {
		return err
	}
	if err := RunCocoIndex(ctx, processRunner, layout); err != nil {
		return err
	}

	return nil
}

func BuildMCP(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) ([]string, error) {
	if !directoryExists(layout.FreightHeroMCP) {
		return nil, clierrors.New(clierrors.KindIndex, fmt.Sprintf("missing freighthero-mcp at %s", layout.FreightHeroMCP))
	}

	actions := make([]string, 0, 4)
	if !directoryExists(filepath.Join(layout.FreightHeroMCP, "node_modules")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "npm", Args: []string{"install"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "npm install freighthero-mcp", err)
		}
		actions = append(actions, "npm-install")
	}
	if !directoryExists(filepath.Join(layout.FreightHeroMCP, ".venv")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "python3", Args: []string{"-m", "venv", ".venv"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "create freighthero-mcp virtualenv", err)
		}
		actions = append(actions, "venv")
	}
	if !fileExists(venvExecutable(layout.FreightHeroMCP, "cocoindex")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: venvExecutable(layout.FreightHeroMCP, "pip"), Args: []string{"install", "-r", "requirements.txt"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "install freighthero-mcp python requirements", err)
		}
		actions = append(actions, "python-requirements")
	}
	if !fileExists(filepath.Join(layout.FreightHeroMCP, "dist", "index.js")) {
		if err := processRunner.RunStreaming(ctx, runner.Command{Name: "npm", Args: []string{"run", "build"}, Dir: layout.FreightHeroMCP}, os.Stdout, os.Stderr); err != nil {
			return actions, clierrors.Wrap(clierrors.KindIndex, "build freighthero-mcp", err)
		}
		actions = append(actions, "build")
	}

	return actions, nil
}

func RunMemPalace(ctx context.Context, processRunner runner.ProcessRunner) error {
	if err := processRunner.RunStreaming(ctx, runner.Command{Name: "mempalace", Args: []string{"wake-up"}}, os.Stdout, os.Stderr); err != nil {
		return clierrors.Wrap(clierrors.KindIndex, "wake up mempalace", err)
	}

	return nil
}

func RunCocoIndex(ctx context.Context, processRunner runner.ProcessRunner, layout repos.RepoLayout) error {
	if err := os.MkdirAll(filepath.Join(layout.FreightHeroMCP, ".cocoindex"), 0o755); err != nil {
		return clierrors.Wrap(clierrors.KindIndex, "create .cocoindex directory", err)
	}

	command := runner.Command{
		Name: venvExecutable(layout.FreightHeroMCP, "cocoindex"),
		Args: []string{"update", "codebase_index.py"},
		Dir:  layout.FreightHeroMCP,
		Env: []string{
			"FREIGHTHERO_REPO_ROOT=" + layout.Root,
			"CODEBASE_INDEX_DIR=" + layout.CodebaseIndex,
		},
	}
	if err := processRunner.RunStreaming(ctx, command, os.Stdout, os.Stderr); err != nil {
		return clierrors.Wrap(clierrors.KindIndex, "run cocoindex update", err)
	}

	return nil
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