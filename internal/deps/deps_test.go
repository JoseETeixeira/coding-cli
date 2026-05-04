package deps

import (
	"context"
	"errors"
	"io"
	"strings"
	"testing"

	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type fakeRunner struct {
	runCapturing map[string]runner.Result
	runErrors    map[string]error
	runs         []runner.Command
}

func (fake *fakeRunner) Run(_ context.Context, command runner.Command) error {
	fake.runs = append(fake.runs, command)
	if fake.runErrors == nil {
		return nil
	}
	return fake.runErrors[commandKey(command)]
}

func (fake *fakeRunner) RunCapturing(_ context.Context, command runner.Command) (runner.Result, error) {
	result, ok := fake.runCapturing[commandKey(command)]
	if !ok {
		return runner.Result{}, errors.New("missing capture")
	}
	if fake.runErrors == nil {
		return result, nil
	}
	return result, fake.runErrors[commandKey(command)]
}

func (fake *fakeRunner) RunStreaming(context.Context, runner.Command, io.Writer, io.Writer) error {
	return nil
}

func TestParseVersion(t *testing.T) {
	t.Parallel()

	if got := ParseVersion("Version: 1.2.3"); got != "1.2.3" {
		t.Fatalf("ParseVersion() = %q", got)
	}
	if got := ParseVersion("node v22.4.1"); got != "22.4.1" {
		t.Fatalf("ParseVersion() = %q", got)
	}
}

func TestVerifyDependenciesReusesSatisfiedDependency(t *testing.T) {
	t.Parallel()

	fake := &fakeRunner{runCapturing: map[string]runner.Result{
		"git --version": {Stdout: "git version 2.44.0"},
	}}

	results, err := VerifyDependencies(context.Background(), fake, []DependencySpec{{
		Name:       "git",
		MinVersion: "2.0.0",
		Required:   true,
		Check:      runner.Command{Name: "git", Args: []string{"--version"}},
	}})
	if err != nil {
		t.Fatalf("VerifyDependencies returned error: %v", err)
	}
	if !results[0].Reused {
		t.Fatal("expected dependency to be reused")
	}
}

func TestVerifyDependenciesInstallsMissingDependency(t *testing.T) {
	t.Parallel()

	fake := &fakeRunner{
		runCapturing: map[string]runner.Result{
			"tool --version": {Stdout: "tool 1.0.0"},
		},
		runErrors: map[string]error{
			"tool --version": errors.New("missing"),
		},
	}

	_, err := VerifyDependencies(context.Background(), fake, []DependencySpec{{
		Name:       "tool",
		MinVersion: "1.0.0",
		Required:   true,
		Check:      runner.Command{Name: "tool", Args: []string{"--version"}},
		Install:    []runner.Command{{Name: "install-tool"}},
		Recovery:   "install tool",
	}})
	if err == nil {
		t.Fatal("expected install recheck to fail because fake runner keeps returning an error")
	}
	if len(fake.runs) != 1 {
		t.Fatalf("len(fake.runs) = %d, want 1", len(fake.runs))
	}
}

func TestVerifyDependenciesIgnoresOptionalInstallFailure(t *testing.T) {
	t.Parallel()

	fake := &fakeRunner{
		runCapturing: map[string]runner.Result{},
		runErrors: map[string]error{
			"optional --version": errors.New("missing"),
			"install-optional":  errors.New("install failed"),
		},
	}

	results, err := VerifyDependencies(context.Background(), fake, []DependencySpec{{
		Name:     "optional",
		Required: false,
		Check:    runner.Command{Name: "optional", Args: []string{"--version"}},
		Install:  []runner.Command{{Name: "install-optional"}},
	}})
	if err != nil {
		t.Fatalf("VerifyDependencies returned error: %v", err)
	}
	if results[0].Installed {
		t.Fatal("expected optional dependency to remain uninstalled")
	}
}

func commandKey(command runner.Command) string {
	if len(command.Args) == 0 {
		return command.Name
	}

	return command.Name + " " + strings.Join(command.Args, " ")
}