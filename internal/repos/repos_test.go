package repos

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"

	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type fakeRunner struct {
	commands []runner.Command
	failRepo string
}

func (fake *fakeRunner) Run(_ context.Context, command runner.Command) error {
	fake.commands = append(fake.commands, command)
	if len(command.Args) >= 3 && command.Args[2] == fake.failRepo {
		return errors.New("boom")
	}

	return nil
}

func (fake *fakeRunner) RunCapturing(context.Context, runner.Command) (runner.Result, error) {
	return runner.Result{}, nil
}

func (fake *fakeRunner) RunStreaming(context.Context, runner.Command, io.Writer, io.Writer) error {
	return nil
}

func TestGetRepoLayoutFindsWorkspaceRootFromCodingCLIDirectory(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	codingCLI := filepath.Join(root, string(RepositoryCodingCLI))
	if err := os.MkdirAll(filepath.Join(codingCLI, "freighthero-mcp"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	layout, err := GetRepoLayout("", codingCLI)
	if err != nil {
		t.Fatalf("GetRepoLayout returned error: %v", err)
	}
	if layout.Root != root {
		t.Fatalf("layout.Root = %q, want %q", layout.Root, root)
	}
	if layout.FreightHeroMCP != filepath.Join(codingCLI, "freighthero-mcp") {
		t.Fatalf("layout.FreightHeroMCP = %q", layout.FreightHeroMCP)
	}
}

func TestValidateLayoutReportsMissingRepositories(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, string(RepositoryCodingCLI), "freighthero-mcp"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	layout, err := GetRepoLayout(root, root)
	if err != nil {
		t.Fatalf("GetRepoLayout returned error: %v", err)
	}

	err = ValidateLayout(layout, RepositoryFrontend)
	if err == nil {
		t.Fatal("expected validation error for missing frontend")
	}
}

func TestCloneRepositoriesSkipsExistingTargets(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, string(RepositoryFrontend)), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	fake := &fakeRunner{}
	results, err := CloneRepositories(context.Background(), fake, root, []Repository{RepositoryFrontend, RepositoryBackend})
	if err != nil {
		t.Fatalf("CloneRepositories returned error: %v", err)
	}
	if len(results) != 2 {
		t.Fatalf("len(results) = %d, want 2", len(results))
	}
	if !results[0].Skipped {
		t.Fatal("expected existing frontend repository to be skipped")
	}
	if len(fake.commands) != 1 {
		t.Fatalf("len(fake.commands) = %d, want 1", len(fake.commands))
	}
	if fake.commands[0].Args[1] != RepositoryURL(RepositoryBackend) {
		t.Fatalf("clone URL = %q, want %q", fake.commands[0].Args[1], RepositoryURL(RepositoryBackend))
	}
}

func TestCloneRepositoriesStopsOnFailure(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	fake := &fakeRunner{failRepo: string(RepositoryBackend)}

	results, err := CloneRepositories(context.Background(), fake, root, CloneTargets)
	if err == nil {
		t.Fatal("expected clone failure")
	}
	if len(results) != 1 {
		t.Fatalf("len(results) = %d, want 1", len(results))
	}
	if results[0].Repository != RepositoryFrontend {
		t.Fatalf("results[0].Repository = %q, want %q", results[0].Repository, RepositoryFrontend)
	}
	if len(fake.commands) != 2 {
		t.Fatalf("len(fake.commands) = %d, want 2", len(fake.commands))
	}
}