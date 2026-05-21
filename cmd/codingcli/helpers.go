package codingcli

import (
	"context"
	"fmt"
	"os"

	"github.com/coding-cli/coding-cli/internal/assets"
	"github.com/coding-cli/coding-cli/internal/config"
	"github.com/coding-cli/coding-cli/internal/deps"
	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/host"
	"github.com/coding-cli/coding-cli/internal/index"
	"github.com/coding-cli/coding-cli/internal/output"
	"github.com/coding-cli/coding-cli/internal/paths"
	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/coding-cli/coding-cli/internal/runner"
)

type GlobalOptions struct {
	WorkspaceRoot string
	Force         bool
	Verbose       bool
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

func logHookResult(logger *output.Logger, result config.ConfigResult) {
	switch result.Action {
	case "created", "updated":
		logger.Success(fmt.Sprintf("%s SessionStart hook in %s", result.Action, result.Path))
	case "skipped":
		if result.Path == "" {
			logger.Info("skipped installing SessionStart hook; not applicable for this host")
			return
		}
		logger.Info(fmt.Sprintf("skipped installing SessionStart hook in %s; already configured", result.Path))
	}
}

func logGuardrailResult(logger *output.Logger, result config.ConfigResult) {
	switch result.Action {
	case "created", "updated":
		logger.Success(fmt.Sprintf("%s git guardrails in %s", result.Action, result.Path))
	case "skipped":
		if result.Path == "" {
			logger.Info("skipped installing git guardrails; not applicable for this host")
			return
		}
		logger.Info(fmt.Sprintf("skipped installing git guardrails in %s; already configured", result.Path))
	}
}

func logDefaultAgentResult(logger *output.Logger, result config.ConfigResult) {
	switch result.Action {
	case "created", "updated":
		logger.Success(fmt.Sprintf("%s default agent %q in %s", result.Action, config.ClaudeCodeDefaultAgentName, result.Path))
	case "skipped":
		if result.Path == "" {
			logger.Info("skipped setting default agent; not applicable for this host")
			return
		}
		logger.Info(fmt.Sprintf("skipped setting default agent in %s; already set to %q", result.Path, config.ClaudeCodeDefaultAgentName))
	}
}

func runIndexingFlow(ctx context.Context, dependencies Dependencies, layout repos.RepoLayout, target index.IndexingTarget) error {
	logStep(dependencies.Logger, "run indexing")
	result, err := index.BootstrapIndexing(ctx, dependencies.Runner, layout, target)
	if err != nil {
		return err
	}
	logIndexingResults(dependencies.Logger, result)
	dependencies.Logger.Success("indexing bootstrap completed")
	return nil
}
