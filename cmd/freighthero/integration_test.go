package freighthero

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Freight-Hero/coding-cli/internal/output"
	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type integrationRunner struct{}

func (fake *integrationRunner) Run(_ context.Context, command runner.Command) error {
	if command.Name == "git" && len(command.Args) >= 3 && command.Args[0] == "clone" {
		return os.MkdirAll(filepath.Join(command.Dir, command.Args[2]), 0o755)
	}

	return nil
}

func (fake *integrationRunner) RunCapturing(_ context.Context, command runner.Command) (runner.Result, error) {
	switch commandKey(command) {
	case "git --version":
		return runner.Result{Stdout: "git version 2.44.0"}, nil
	case "node --version":
		return runner.Result{Stdout: "v22.4.1"}, nil
	case "npm --version":
		return runner.Result{Stdout: "10.8.0"}, nil
	case "python3 --version":
		return runner.Result{Stdout: "Python 3.11.9"}, nil
	case "python3 -m pip --version":
		return runner.Result{Stdout: "pip 24.0"}, nil
	case "python3 -m pip show mempalace":
		return runner.Result{Stdout: "Version: 1.2.0"}, nil
	case "python3 -m pip show cocoindex":
		return runner.Result{Stdout: "Version: 1.0.0"}, nil
	case "rtk --version":
		return runner.Result{Stdout: "0.38.0"}, nil
	default:
		return runner.Result{}, fmt.Errorf("unexpected capture command %q", commandKey(command))
	}
}

func (fake *integrationRunner) RunStreaming(_ context.Context, command runner.Command, _ io.Writer, _ io.Writer) error {
	switch {
	case command.Name == "npm" && len(command.Args) == 1 && command.Args[0] == "install":
		return os.MkdirAll(filepath.Join(command.Dir, "node_modules"), 0o755)
	case command.Name == "python3" && len(command.Args) == 3 && command.Args[0] == "-m" && command.Args[1] == "venv":
		venvBin := filepath.Join(command.Dir, ".venv", "bin")
		if err := os.MkdirAll(venvBin, 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(venvBin, "pip"), []byte(""), 0o755); err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(venvBin, "cocoindex"), []byte(""), 0o755)
	case strings.HasSuffix(command.Name, filepath.Join(".venv", "bin", "pip")):
		venvBin := filepath.Join(command.Dir, ".venv", "bin")
		return os.WriteFile(filepath.Join(venvBin, "cocoindex"), []byte(""), 0o755)
	case command.Name == "npm" && len(command.Args) == 2 && command.Args[0] == "run" && command.Args[1] == "build":
		if err := os.MkdirAll(filepath.Join(command.Dir, "dist"), 0o755); err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(command.Dir, "dist", "index.js"), []byte("export {};"), 0o644)
	case command.Name == "mempalace":
		return nil
	case strings.HasSuffix(command.Name, filepath.Join(".venv", "bin", "cocoindex")):
		indexDir := filepath.Join(command.Dir, ".cocoindex", "codebase-index")
		if err := os.MkdirAll(indexDir, 0o755); err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(indexDir, "chunk.json"), []byte("{}"), 0o644)
	default:
		return nil
	}
}

func TestSetupAgentInstallsAssets(t *testing.T) {
	root, home := createWorkspaceFixture(t)
	setTestEnv(t, home)

	cmd := NewRootCommand(Dependencies{Logger: output.New(io.Discard, io.Discard, false), Runner: &integrationRunner{}})
	cmd.SetArgs([]string{"setup", "agent", "--vscode", "--freighthero-root", root})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(home, "prompts", "demo.prompt.md"))
	assertExists(t, filepath.Join(home, "prompts", "batman.agent.md"))
	assertExists(t, filepath.Join(home, "skills", "example-skill", "SKILL.md"))
}

func TestSetupMCPBuildsAndWritesConfig(t *testing.T) {
	root, home := createWorkspaceFixture(t)
	setTestEnv(t, home)

	cmd := NewRootCommand(Dependencies{Logger: output.New(io.Discard, io.Discard, false), Runner: &integrationRunner{}})
	cmd.SetArgs([]string{"setup", "mcp", "--vscode", "--freighthero-root", root})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(root, "coding-cli", "freighthero-mcp", "dist", "index.js"))
	content, err := os.ReadFile(filepath.Join(home, "mcp.json"))
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), "freighthero-codebase") {
		t.Fatalf("expected freighthero-codebase in mcp.json, got %q", string(content))
	}
	if !strings.Contains(string(content), "https://api.githubcopilot.com/mcp/") {
		t.Fatalf("expected remote github MCP in mcp.json, got %q", string(content))
	}
}

func TestSetupFullIsIdempotent(t *testing.T) {
	root, home := createWorkspaceFixture(t)
	setTestEnv(t, home)

	dependencies := Dependencies{Logger: output.New(io.Discard, io.Discard, false), Runner: &integrationRunner{}}
	first := NewRootCommand(dependencies)
	first.SetArgs([]string{"setup", "full", "--vscode", "--freighthero-root", root})
	if err := first.Execute(); err != nil {
		t.Fatalf("first Execute returned error: %v", err)
	}

	configBefore, err := os.ReadFile(filepath.Join(home, "mcp.json"))
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}

	second := NewRootCommand(dependencies)
	second.SetArgs([]string{"setup", "full", "--vscode", "--freighthero-root", root})
	if err := second.Execute(); err != nil {
		t.Fatalf("second Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(root, "frontend"))
	assertExists(t, filepath.Join(root, "backend"))
	assertExists(t, filepath.Join(root, "ai_watchtower"))
	assertExists(t, filepath.Join(root, "coding-cli", "freighthero-mcp", ".cocoindex", "codebase-index", "chunk.json"))

	configAfter, err := os.ReadFile(filepath.Join(home, "mcp.json"))
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if string(configBefore) != string(configAfter) {
		t.Fatal("expected setup full rerun to preserve the same MCP config content")
	}
}

func TestSetupMCPAutoDetectsSingleHost(t *testing.T) {
	root, home := createWorkspaceFixture(t)
	setTestEnv(t, home)

	cmd := NewRootCommand(Dependencies{Logger: output.New(io.Discard, io.Discard, false), Runner: &integrationRunner{}})
	cmd.SetArgs([]string{"setup", "mcp", "--freighthero-root", root})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(home, "mcp.json"))
}

func TestSetupFullLogsSkippedStepsAndIndexingProgress(t *testing.T) {
	root, home := createWorkspaceFixture(t)
	setTestEnv(t, home)

	dependencies := Dependencies{Logger: output.New(io.Discard, io.Discard, false), Runner: &integrationRunner{}}
	first := NewRootCommand(dependencies)
	first.SetArgs([]string{"setup", "full", "--vscode", "--freighthero-root", root})
	if err := first.Execute(); err != nil {
		t.Fatalf("first Execute returned error: %v", err)
	}

	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}
	second := NewRootCommand(Dependencies{Logger: output.New(stdout, stderr, false), Runner: &integrationRunner{}})
	second.SetArgs([]string{"setup", "full", "--vscode", "--freighthero-root", root})
	if err := second.Execute(); err != nil {
		t.Fatalf("second Execute returned error: %v", err)
	}

	combined := stdout.String() + "\n" + stderr.String()
	for _, expected := range []string{
		"step: run indexing",
		"skipped freighthero-mcp npm dependencies",
		"mempalace wake-up",
		"cocoindex update",
		"skipped updating MCP config",
	} {
		if !strings.Contains(combined, expected) {
			t.Fatalf("expected log output to contain %q, got %q", expected, combined)
		}
	}
}

func createWorkspaceFixture(t *testing.T) (string, string) {
	t.Helper()

	root := t.TempDir()
	home := filepath.Join(root, "home")
	paths := []string{
		filepath.Join(root, "coding-cli", "prompts"),
		filepath.Join(root, "coding-cli", "skills", "example-skill"),
		filepath.Join(root, "coding-cli", "freighthero-mcp"),
		home,
	}
	for _, path := range paths {
		if err := os.MkdirAll(path, 0o755); err != nil {
			t.Fatalf("MkdirAll %s returned error: %v", path, err)
		}
	}
	files := map[string]string{
		filepath.Join(root, "coding-cli", "prompts", "demo.prompt.md"):            "prompt",
		filepath.Join(root, "coding-cli", "prompts", "demo.instructions.md"):      "instruction",
		filepath.Join(root, "coding-cli", "prompts", "batman.agent.md"):          "python3 -m mempalace hook run --harness copilot",
		filepath.Join(root, "coding-cli", "skills", "example-skill", "SKILL.md"): "skill",
	}
	for path, content := range files {
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatalf("WriteFile %s returned error: %v", path, err)
		}
	}

	return root, home
}

func setTestEnv(t *testing.T, home string) {
	t.Helper()
	t.Setenv("HOME", home)
	t.Setenv("VSCODE_USER_PROMPTS_FOLDER", filepath.Join(home, "prompts"))
	t.Setenv("USER_AGENTS_DIR", filepath.Join(home, "prompts"))
	t.Setenv("USER_INSTRUCTIONS_DIR", filepath.Join(home, "prompts"))
	t.Setenv("USER_SKILLS_DIR", filepath.Join(home, "skills"))
	t.Setenv("VSCODE_MCP_CONFIG_PATH", filepath.Join(home, "mcp.json"))
}

func assertExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected %s to exist, got error: %v", path, err)
	}
}

func commandKey(command runner.Command) string {
	if len(command.Args) == 0 {
		return command.Name
	}

	return command.Name + " " + strings.Join(command.Args, " ")
}