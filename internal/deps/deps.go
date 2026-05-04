package deps

import (
	"context"
	"fmt"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type DependencySpec struct {
	Name       string
	MinVersion string
	Required   bool
	Check      runner.Command
	Install    []runner.Command
	Recovery   string
}

type DependencyResult struct {
	Name      string
	Version   string
	Installed bool
	Reused    bool
	Required  bool
}

func DefaultSpecs() []DependencySpec {
	basicInstall := func(packageName string) []runner.Command {
		if runtime.GOOS != "darwin" {
			return nil
		}

		return []runner.Command{{Name: "brew", Args: []string{"install", packageName}}}
	}

	return []DependencySpec{
		{
			Name:       "git",
			MinVersion: "2.0.0",
			Required:   true,
			Check:      runner.Command{Name: "git", Args: []string{"--version"}},
			Install:    basicInstall("git"),
			Recovery:   "install Git and rerun the command",
		},
		{
			Name:       "node",
			MinVersion: "22.0.0",
			Required:   true,
			Check:      runner.Command{Name: "node", Args: []string{"--version"}},
			Install:    basicInstall("node"),
			Recovery:   "install Node.js 22 or newer and rerun the command",
		},
		{
			Name:       "npm",
			MinVersion: "10.0.0",
			Required:   true,
			Check:      runner.Command{Name: "npm", Args: []string{"--version"}},
			Install:    basicInstall("node"),
			Recovery:   "install npm 10 or newer and rerun the command",
		},
		{
			Name:       "python3",
			MinVersion: "3.11.0",
			Required:   true,
			Check:      runner.Command{Name: "python3", Args: []string{"--version"}},
			Install:    basicInstall("python"),
			Recovery:   "install Python 3.11 or newer and rerun the command",
		},
		{
			Name:       "pip",
			MinVersion: "23.0.0",
			Required:   true,
			Check:      runner.Command{Name: "python3", Args: []string{"-m", "pip", "--version"}},
			Install:    []runner.Command{{Name: "python3", Args: []string{"-m", "ensurepip", "--upgrade"}}},
			Recovery:   "ensure pip is available for python3 and rerun the command",
		},
		{
			Name:       "mempalace",
			MinVersion: "0.0.0",
			Required:   true,
			Check:      runner.Command{Name: "python3", Args: []string{"-m", "pip", "show", "mempalace"}},
			Install:    []runner.Command{{Name: "python3", Args: []string{"-m", "pip", "install", "--user", "mempalace"}}},
			Recovery:   "install mempalace with python3 -m pip install --user mempalace",
		},
		{
			Name:       "cocoindex",
			MinVersion: "1.0.0",
			Required:   true,
			Check:      runner.Command{Name: "python3", Args: []string{"-m", "pip", "show", "cocoindex"}},
			Install:    []runner.Command{{Name: "python3", Args: []string{"-m", "pip", "install", "--user", "cocoindex"}}},
			Recovery:   "install cocoindex with python3 -m pip install --user cocoindex",
		},
		{
			Name:       "rtk",
			MinVersion: "0.0.0",
			Required:   false,
			Check:      runner.Command{Name: "rtk", Args: []string{"--version"}},
			Install:    basicInstall("rtk"),
			Recovery:   "install rtk from https://github.com/rtk-ai/rtk for token-optimized terminal output",
		},
	}
}

func VerifyDependencies(ctx context.Context, processRunner runner.ProcessRunner, specs []DependencySpec) ([]DependencyResult, error) {
	results := make([]DependencyResult, 0, len(specs))
	for _, spec := range specs {
		result, err := verifyDependency(ctx, processRunner, spec)
		results = append(results, result)
		if err != nil {
			return results, err
		}
	}

	return results, nil
}

func ParseVersion(text string) string {
	matcher := regexp.MustCompile(`\d+(?:\.\d+){0,2}`)
	return matcher.FindString(text)
}

func CompareVersions(left string, right string) int {
	leftParts := versionParts(left)
	rightParts := versionParts(right)
	for index := 0; index < 3; index++ {
		if leftParts[index] < rightParts[index] {
			return -1
		}
		if leftParts[index] > rightParts[index] {
			return 1
		}
	}

	return 0
}

func verifyDependency(ctx context.Context, processRunner runner.ProcessRunner, spec DependencySpec) (DependencyResult, error) {
	result := DependencyResult{Name: spec.Name, Required: spec.Required}
	version, err := checkVersion(ctx, processRunner, spec.Check)
	if err == nil && versionSatisfies(version, spec.MinVersion) {
		result.Version = version
		result.Reused = true
		return result, nil
	}

	if len(spec.Install) == 0 {
		if spec.Required {
			return result, clierrors.New(clierrors.KindDependency, fmt.Sprintf("%s is missing or below %s; %s", spec.Name, spec.MinVersion, spec.Recovery))
		}
		return result, nil
	}

	for _, installCommand := range spec.Install {
		if installErr := processRunner.Run(ctx, installCommand); installErr != nil {
			if spec.Required {
				return result, clierrors.Wrap(clierrors.KindDependency, fmt.Sprintf("install %s", spec.Name), installErr)
			}
			return result, nil
		}
	}

	version, err = checkVersion(ctx, processRunner, spec.Check)
	if err != nil || !versionSatisfies(version, spec.MinVersion) {
		if spec.Required {
			return result, clierrors.New(clierrors.KindDependency, fmt.Sprintf("%s is still unavailable after installation; %s", spec.Name, spec.Recovery))
		}
		return result, nil
	}

	result.Version = version
	result.Installed = true
	return result, nil
}

func checkVersion(ctx context.Context, processRunner runner.ProcessRunner, command runner.Command) (string, error) {
	result, err := processRunner.RunCapturing(ctx, command)
	output := strings.TrimSpace(result.Stdout + "\n" + result.Stderr)
	version := ParseVersion(output)
	if err != nil {
		if version != "" {
			return version, err
		}
		return "", err
	}
	if version == "" {
		return "", fmt.Errorf("could not parse version from %q", output)
	}

	return version, nil
}

func versionSatisfies(version string, minVersion string) bool {
	if minVersion == "" || minVersion == "0.0.0" {
		return version != ""
	}

	return CompareVersions(version, minVersion) >= 0
}

func versionParts(version string) [3]int {
	parts := strings.Split(version, ".")
	parsed := [3]int{}
	for index := 0; index < len(parts) && index < 3; index++ {
		value, err := strconv.Atoi(parts[index])
		if err == nil {
			parsed[index] = value
		}
	}

	return parsed
}