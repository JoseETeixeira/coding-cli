package deps

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/coding-cli/coding-cli/internal/runner"
)

type pythonCandidate struct {
	CommandPath string
	Args        []string
	Version     string
}

const (
	pythonEnvironmentSystem    = "system"
	pythonEnvironmentVirtual   = "venv"
	pythonEnvironmentUVManaged = "uv-managed"
)

func installPython(minVersion string) func(context.Context, runner.ProcessRunner) error {
	installVersion := pythonInstallVersion(minVersion)

	return func(ctx context.Context, _ runner.ProcessRunner) error {
		candidate, ok, err := discoverPythonCandidate(ctx, minVersion)
		if err != nil {
			return err
		}
		if ok {
			return exposePython3(ctx, candidate)
		}

		if err := ensureUVInstalled(ctx); err != nil {
			return err
		}

		venvPython, err := ensureCodingCLIPythonVenv(ctx, installVersion)
		if err != nil {
			return err
		}

		return exposePython3(ctx, pythonCandidate{CommandPath: venvPython, Version: installVersion})
	}
}

func installPythonPackage(packageName string) func(context.Context, runner.ProcessRunner) error {
	return func(ctx context.Context, processRunner runner.ProcessRunner) error {
		environmentKind, err := pythonEnvironmentKind(ctx, processRunner)
		if err != nil {
			return err
		}

		if environmentKind == pythonEnvironmentUVManaged {
			version, err := checkVersion(ctx, processRunner, runner.Command{Name: "python3", Args: []string{"--version"}})
			if err != nil {
				return err
			}
			venvPython, err := ensureCodingCLIPythonVenv(ctx, pythonInstallVersion(version))
			if err != nil {
				return err
			}
			if err := exposePython3(ctx, pythonCandidate{CommandPath: venvPython, Version: version}); err != nil {
				return err
			}
			environmentKind = pythonEnvironmentVirtual
		}

		args := []string{"-m", "pip", "install"}
		if environmentKind != pythonEnvironmentVirtual {
			args = append(args, "--user")
		}
		args = append(args, packageName)

		return processRunner.Run(ctx, runner.Command{Name: "python3", Args: args})
	}
}

func discoverPythonCandidate(ctx context.Context, minVersion string) (pythonCandidate, bool, error) {
	for _, command := range pythonSearchCommands() {
		commandPath, err := exec.LookPath(command.Name)
		if err != nil {
			continue
		}

		version, err := pythonCommandVersion(ctx, commandPath, command.Args)
		if err != nil {
			continue
		}
		if !versionSatisfies(version, minVersion) {
			continue
		}

		return pythonCandidate{CommandPath: commandPath, Args: command.Args, Version: version}, true, nil
	}

	return pythonCandidate{}, false, nil
}

func pythonCommandVersion(ctx context.Context, commandPath string, args []string) (string, error) {
	command := exec.CommandContext(ctx, commandPath, append(args, "--version")...)
	output, err := command.CombinedOutput()
	version := ParseVersion(strings.TrimSpace(string(output)))
	if err != nil && version == "" {
		return "", err
	}
	if version == "" {
		return "", fmt.Errorf("could not parse python version from %q", strings.TrimSpace(string(output)))
	}

	return version, nil
}

func pythonSearchCommands() []runner.Command {
	commands := []runner.Command{
		{Name: "python3.13"},
		{Name: "python3.12"},
		{Name: "python3.11"},
		{Name: "python3.10"},
		{Name: "python"},
	}
	if runtime.GOOS == "windows" {
		commands = append([]runner.Command{
			{Name: "py", Args: []string{"-3.13"}},
			{Name: "py", Args: []string{"-3.12"}},
			{Name: "py", Args: []string{"-3.11"}},
			{Name: "py", Args: []string{"-3.10"}},
		}, commands...)
	}

	return commands
}

func exposePython3(ctx context.Context, candidate pythonCandidate) error {
	installDir, err := rtkInstallDir()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(installDir, 0o755); err != nil {
		return fmt.Errorf("create python3 install directory %s: %w", installDir, err)
	}

	if runtime.GOOS == "windows" {
		destination := filepath.Join(installDir, "python3.cmd")
		if err := removeIfExists(destination); err != nil {
			return err
		}
		wrapper := fmt.Sprintf("@echo off\r\n\"%s\"", candidate.CommandPath)
		for _, arg := range candidate.Args {
			wrapper += fmt.Sprintf(" %s", arg)
		}
		wrapper += " %*\r\n"
		if err := os.WriteFile(destination, []byte(wrapper), 0o755); err != nil {
			return fmt.Errorf("write python3 wrapper %s: %w", destination, err)
		}
	} else {
		destination := filepath.Join(installDir, "python3")
		if err := removeIfExists(destination); err != nil {
			return err
		}
		wrapper := fmt.Sprintf("#!/bin/sh\nexec %q", candidate.CommandPath)
		for _, arg := range candidate.Args {
			wrapper += fmt.Sprintf(" %q", arg)
		}
		wrapper += " \"$@\"\n"
		if err := os.WriteFile(destination, []byte(wrapper), 0o755); err != nil {
			return fmt.Errorf("write python3 wrapper %s: %w", destination, err)
		}
	}

	return ensureInstallDirOnPath(ctx, installDir)
}

func pythonEnvironmentKind(ctx context.Context, processRunner runner.ProcessRunner) (string, error) {
	command := runner.Command{
		Name: "python3",
		Args: []string{"-c", "import sys; prefix = sys.prefix.replace('\\\\', '/'); base = getattr(sys, 'base_prefix', sys.prefix).replace('\\\\', '/'); print('venv' if prefix != base else 'uv-managed' if '/uv/python/' in prefix else 'system')"},
	}
	result, err := processRunner.RunCapturing(ctx, command)
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(result.Stdout), nil
}

func ensureCodingCLIPythonVenv(ctx context.Context, pythonSpec string) (string, error) {
	if err := ensureUVInstalled(ctx); err != nil {
		return "", err
	}

	uvPath, err := exec.LookPath("uv")
	if err != nil {
		return "", fmt.Errorf("find uv after installation: %w", err)
	}

	venvRoot, err := codingCLIPythonVenvRoot(pythonSpec)
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(filepath.Dir(venvRoot), 0o755); err != nil {
		return "", fmt.Errorf("create coding-cli Python parent directory for %s: %w", venvRoot, err)
	}

	command := exec.CommandContext(ctx, uvPath, "venv", "--clear", "--seed", "--python", pythonSpec, venvRoot)
	output, err := command.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("uv venv --clear --seed --python %s %s: %w: %s", pythonSpec, venvRoot, err, strings.TrimSpace(string(output)))
	}

	return codingCLIVenvPython(venvRoot), nil
}

func codingCLIPythonVenvRoot(pythonSpec string) (string, error) {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve home directory for coding-cli Python venv: %w", err)
	}

	versionDir := strings.ReplaceAll(strings.TrimSpace(pythonSpec), ".", "-")
	if versionDir == "" {
		versionDir = "python3"
	}

	if runtime.GOOS == "windows" {
		root := os.Getenv("LOCALAPPDATA")
		if root == "" {
			root = filepath.Join(homeDir, "AppData", "Local")
		}
		return filepath.Join(root, "coding-cli", "python", versionDir), nil
	}

	return filepath.Join(homeDir, ".local", "share", "coding-cli", "python", versionDir), nil
}

func codingCLIVenvPython(venvRoot string) string {
	if runtime.GOOS == "windows" {
		return filepath.Join(venvRoot, "Scripts", "python.exe")
	}

	return filepath.Join(venvRoot, "bin", "python")
}

func ensureUVInstalled(ctx context.Context) error {
	if _, err := exec.LookPath("uv"); err == nil {
		return nil
	}

	assetName, err := uvAssetName(runtime.GOOS, runtime.GOARCH)
	if err != nil {
		return err
	}

	installDir, err := rtkInstallDir()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(installDir, 0o755); err != nil {
		return fmt.Errorf("create uv install directory %s: %w", installDir, err)
	}

	assetURL, err := latestGitHubAssetURL(ctx, "astral-sh", "uv", assetName)
	if err != nil {
		return err
	}

	payload, err := downloadReleaseAsset(ctx, assetURL)
	if err != nil {
		return err
	}

	binaryName := "uv"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}
	binary, err := extractReleaseBinary(payload, assetName, binaryName)
	if err != nil {
		return err
	}

	destination := filepath.Join(installDir, binaryName)
	if err := os.WriteFile(destination, binary, 0o755); err != nil {
		return fmt.Errorf("write uv binary to %s: %w", destination, err)
	}

	return ensureInstallDirOnPath(ctx, installDir)
}

func uvAssetName(goos string, goarch string) (string, error) {
	switch goos {
	case "darwin":
		switch goarch {
		case "arm64":
			return "uv-aarch64-apple-darwin.tar.gz", nil
		case "amd64":
			return "uv-x86_64-apple-darwin.tar.gz", nil
		}
	case "linux":
		switch goarch {
		case "arm64":
			return "uv-aarch64-unknown-linux-gnu.tar.gz", nil
		case "amd64":
			return "uv-x86_64-unknown-linux-gnu.tar.gz", nil
		}
	case "windows":
		switch goarch {
		case "arm64":
			return "uv-aarch64-pc-windows-msvc.zip", nil
		case "amd64":
			return "uv-x86_64-pc-windows-msvc.zip", nil
		}
	}

	return "", fmt.Errorf("unsupported uv platform %s/%s", goos, goarch)
}

func removeIfExists(path string) error {
	err := os.Remove(path)
	if err == nil || errors.Is(err, os.ErrNotExist) {
		return nil
	}

	return fmt.Errorf("remove %s: %w", path, err)
}

func pythonInstallVersion(minVersion string) string {
	if minVersion == "" || CompareVersions(minVersion, "3.11.0") < 0 {
		return "3.11"
	}

	parts := strings.Split(minVersion, ".")
	if len(parts) < 2 {
		return minVersion
	}

	return parts[0] + "." + parts[1]
}
