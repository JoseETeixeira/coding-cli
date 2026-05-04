package freighthero

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/Freight-Hero/coding-cli/internal/deps"
	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/output"
	"github.com/Freight-Hero/coding-cli/internal/paths"
	"github.com/Freight-Hero/coding-cli/internal/repos"
	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type GlobalOptions struct {
	FreightHeroRoot string
	Force           bool
	Verbose         bool
}

type Dependencies struct {
	Logger *output.Logger
	Runner runner.ProcessRunner
}

func defaultDependencies() Dependencies {
	return Dependencies{
		Logger: output.New(os.Stdout, os.Stderr, false),
		Runner: runner.NewExecRunner(),
	}
}

func resolveHostProfile(selection host.SelectionFlags, allowAuto bool) (host.HostProfile, error) {
	resolver, err := paths.NewResolver()
	if err != nil {
		return host.HostProfile{}, clierrors.Wrap(clierrors.KindValidation, "resolve user home directory", err)
	}

	detector := host.NewDetector(resolver)
	return detector.ResolveSelected(selection, allowAuto)
}

func resolveRepoLayout(rootOverride string) (repos.RepoLayout, error) {
	currentWorkingDir, err := os.Getwd()
	if err != nil {
		return repos.RepoLayout{}, clierrors.Wrap(clierrors.KindValidation, "resolve current working directory", err)
	}

	return repos.GetRepoLayout(rootOverride, currentWorkingDir)
}

func resolveCloneRoot(rootOverride string) (string, error) {
	if rootOverride != "" {
		return filepath.Clean(rootOverride), nil
	}

	currentWorkingDir, err := os.Getwd()
	if err != nil {
		return "", clierrors.Wrap(clierrors.KindValidation, "resolve current working directory", err)
	}

	return repos.CloneRoot(currentWorkingDir), nil
}

func logDependencyResults(logger *output.Logger, results []deps.DependencyResult) {
	for _, result := range results {
		switch {
		case result.Reused:
			logger.Info(fmt.Sprintf("reused %s %s", result.Name, result.Version))
		case result.Installed:
			logger.Success(fmt.Sprintf("installed %s %s", result.Name, result.Version))
		case !result.Required:
			logger.Warn(fmt.Sprintf("optional dependency %s is unavailable", result.Name))
		}
	}
}