package index

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"

	"github.com/coding-cli/coding-cli/internal/repos"
	"github.com/coding-cli/coding-cli/internal/runner"
)

type fakeRunner struct {
	commands []runner.Command
	failOn   string
}

func (fake *fakeRunner) Run(context.Context, runner.Command) error {
	return nil
}

func (fake *fakeRunner) RunCapturing(context.Context, runner.Command) (runner.Result, error) {
	return runner.Result{}, nil
}

func (fake *fakeRunner) RunStreaming(_ context.Context, command runner.Command, _ io.Writer, _ io.Writer) error {
	fake.commands = append(fake.commands, command)
	if command.Name == fake.failOn {
		return errors.New("boom")
	}
	return nil
}

func TestBootstrapIndexingValidatesMissingCodingCLI(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	layout := repos.RepoLayout{
		Root:          root,
		CodingCLI:     filepath.Join(root, "coding-cli"),
		QueryCodeMCP:  filepath.Join(root, "coding-cli", "query-code-mcp"),
		CodebaseIndex: filepath.Join(root, "coding-cli", "query-code-mcp", ".cocoindex", "codebase-index"),
	}

	_, err := BootstrapIndexing(context.Background(), &fakeRunner{}, layout)
	if err == nil {
		t.Fatal("expected validation error for missing coding-cli directory")
	}
}

func TestBuildMCPRunsExpectedCommands(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	queryCodeMCP := filepath.Join(root, "coding-cli", "query-code-mcp")
	if err := os.MkdirAll(queryCodeMCP, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	fake := &fakeRunner{}
	actions, err := BuildMCP(context.Background(), fake, repos.RepoLayout{QueryCodeMCP: queryCodeMCP})
	if err != nil {
		t.Fatalf("BuildMCP returned error: %v", err)
	}
	if len(actions) != 2 {
		t.Fatalf("len(actions) = %d, want 2", len(actions))
	}
	if len(fake.commands) != 2 {
		t.Fatalf("len(fake.commands) = %d, want 2", len(fake.commands))
	}
}

func TestEnsureIndexingEnvironmentRunsExpectedCommands(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	queryCodeMCP := filepath.Join(root, "coding-cli", "query-code-mcp")
	if err := os.MkdirAll(queryCodeMCP, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	fake := &fakeRunner{}
	actions, err := EnsureIndexingEnvironment(context.Background(), fake, repos.RepoLayout{QueryCodeMCP: queryCodeMCP})
	if err != nil {
		t.Fatalf("EnsureIndexingEnvironment returned error: %v", err)
	}
	if len(actions) != 2 {
		t.Fatalf("len(actions) = %d, want 2", len(actions))
	}
	if len(fake.commands) != 2 {
		t.Fatalf("len(fake.commands) = %d, want 2", len(fake.commands))
	}
}

func TestRunCocoIndexCreatesCocoIndexDirectory(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	queryCodeMCP := filepath.Join(root, "coding-cli", "query-code-mcp")
	if err := os.MkdirAll(queryCodeMCP, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	layout := repos.RepoLayout{
		Root:          root,
		QueryCodeMCP:  queryCodeMCP,
		CodebaseIndex: filepath.Join(queryCodeMCP, ".cocoindex", "codebase-index"),
	}

	if _, err := RunCocoIndex(context.Background(), &fakeRunner{}, layout); err != nil {
		t.Fatalf("RunCocoIndex returned error: %v", err)
	}
	if _, err := os.Stat(filepath.Join(queryCodeMCP, ".cocoindex")); err != nil {
		t.Fatalf("expected .cocoindex directory, got error: %v", err)
	}
}
