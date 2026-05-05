package freighthero

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/Freight-Hero/coding-cli/internal/assets"
	"github.com/Freight-Hero/coding-cli/internal/config"
	"github.com/Freight-Hero/coding-cli/internal/deps"
	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/index"
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

func logStep(logger *output.Logger, message string) {
	logger.Info(fmt.Sprintf("step: %s", message))
}

func logDependencyResults(logger *output.Logger, results []deps.DependencyResult) {
	for _, result := range results {
		switch {
		case result.Reused:
			logger.Info(fmt.Sprintf("skipped installing %s; using %s", result.Name, result.Version))
		case result.Installed:
			logger.Success(fmt.Sprintf("installed %s %s", result.Name, result.Version))
		case !result.Required:
			logger.Warn(fmt.Sprintf("skipped optional dependency %s; unavailable after install attempt", result.Name))
		}
	}
}

func logCloneResults(logger *output.Logger, results []repos.CloneResult) {
	for _, result := range results {
		if result.Skipped {
			logger.Info(fmt.Sprintf("skipped cloning %s; using %s", result.Repository, result.Path))
			continue
		}
		logger.Success(fmt.Sprintf("cloned %s into %s", result.Repository, result.Path))
	}
}

func logAssetResults(logger *output.Logger, results []assets.AssetResult) {
	for _, result := range results {
		switch result.Action {
		case "created", "updated":
			logger.Success(fmt.Sprintf("%s %s", result.Action, result.Destination))
		case "skipped-conflict":
			logger.Warn(fmt.Sprintf("skipped conflicting %s; rerun with --force to replace it", result.Destination))
		case "skipped-unsupported":
			logger.Warn(fmt.Sprintf("skipped unsupported %s asset %s", result.AssetType, result.Source))
		default:
			if result.Destination != "" {
				logger.Info(fmt.Sprintf("skipped unchanged %s", result.Destination))
			}
		}
	}
}

func logBuildResults(logger *output.Logger, results []index.StepResult) {
	for _, result := range results {
		logIndexStepResult(logger, result)
	}
}

func logIndexingResults(logger *output.Logger, result index.BootstrapResult) {
	logBuildResults(logger, result.Build)
	logBuildResults(logger, result.Environment)
	logIndexStepResult(logger, result.MemPalace)
	logIndexStepResult(logger, result.CocoIndex)
}

func logIndexStepResult(logger *output.Logger, result index.StepResult) {
	switch result.Action {
	case "completed":
		if result.Detail == "" {
			logger.Success(result.Name)
			return
		}
		logger.Success(fmt.Sprintf("%s (%s)", result.Name, result.Detail))
	case "skipped":
		if result.Detail == "" {
			logger.Info(fmt.Sprintf("skipped %s", result.Name))
			return
		}
		logger.Info(fmt.Sprintf("skipped %s; %s", result.Name, result.Detail))
	}
}

func logConfigResult(logger *output.Logger, result config.ConfigResult) {
	switch result.Action {
	case "created", "updated":
		logger.Success(fmt.Sprintf("%s MCP config at %s", result.Action, result.Path))
	case "skipped":
		logger.Info(fmt.Sprintf("skipped updating MCP config at %s; already up to date", result.Path))
	}
}

func runIndexingFlow(ctx context.Context, dependencies Dependencies, layout repos.RepoLayout) error {
	logStep(dependencies.Logger, "run indexing")
	result, err := index.BootstrapIndexing(ctx, dependencies.Runner, layout)
	if err != nil {
		return err
	}
	logIndexingResults(dependencies.Logger, result)
	dependencies.Logger.Success("indexing bootstrap completed")
	return nil
}