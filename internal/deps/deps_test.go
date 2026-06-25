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
	runCapturingFunc func(runner.Command) (runner.Result, error)
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
	if fake.runCapturingFunc != nil {
		return fake.runCapturingFunc(command)
	}

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

func TestVerifyDependenciesUsesInstallFunc(t *testing.T) {
	t.Parallel()

	installed := false
	fake := &fakeRunner{
		runCapturingFunc: func(command runner.Command) (runner.Result, error) {
			if commandKey(command) != "rtk --version" {
				return runner.Result{}, errors.New("unexpected command")
			}
			if !installed {
				return runner.Result{}, errors.New("missing")
			}
			return runner.Result{Stdout: "rtk 0.38.0"}, nil
		},
	}

	results, err := VerifyDependencies(context.Background(), fake, []DependencySpec{{
		Name:       "rtk",
		MinVersion: "0.0.0",
		Required:   true,
		Check:      runner.Command{Name: "rtk", Args: []string{"--version"}},
		InstallFunc: func(context.Context, runner.ProcessRunner) error {
			installed = true
			return nil
		},
	}})
	if err != nil {
		t.Fatalf("VerifyDependencies returned error: %v", err)
	}
	if !results[0].Installed {
		fatalf := t.Fatalf
		fatalf("expected dependency to be installed by InstallFunc")
	}
	if results[0].Version != "0.38.0" {
		t.Fatalf("results[0].Version = %q", results[0].Version)
	}
}

func TestSetupSpecsIncludeOptionalRepowise(t *testing.T) {
	t.Parallel()

	find := func(specs []DependencySpec, name string) (DependencySpec, bool) {
		for _, spec := range specs {
			if spec.Name == name {
				return spec, true
			}
		}
		return DependencySpec{}, false
	}

	for _, set := range []struct {
		name  string
		specs []DependencySpec
	}{
		{"SetupMCPSpecs", SetupMCPSpecs()},
		{"SetupFullSpecs", SetupFullSpecs()},
	} {
		spec, ok := find(set.specs, "repowise")
		if !ok {
			t.Fatalf("%s: expected a repowise spec", set.name)
		}
		if spec.Required {
			t.Fatalf("%s: repowise spec must be optional so missing uv/repowise does not break setup", set.name)
		}
		if spec.Check.Name != "repowise" {
			t.Fatalf("%s: repowise Check.Name = %q, want repowise", set.name, spec.Check.Name)
		}
		if len(spec.Install) == 0 || spec.Install[0].Name != "uv" {
			t.Fatalf("%s: repowise must install via uv, got %v", set.name, spec.Install)
		}
	}
}

func commandKey(command runner.Command) string {
	if len(command.Args) == 0 {
		return command.Name
	}

	return command.Name + " " + strings.Join(command.Args, " ")
}