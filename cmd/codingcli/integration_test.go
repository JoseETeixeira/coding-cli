package codingcli

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/coding-cli/coding-cli/internal/output"
	"github.com/coding-cli/coding-cli/internal/runner"
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
		if command.Name == "python3" && len(command.Args) >= 2 && command.Args[0] == "-c" && strings.Contains(command.Args[1], "sys.prefix") {
			return runner.Result{Stdout: "system"}, nil
		}
		return runner.Result{}, fmt.Errorf("unexpected capture command %q", commandKey(command))
	}
}

func venvSubdir() string {
	if runtime.GOOS == "windows" {
		return "Scripts"
	}
	return "bin"
}

func venvBinName(name string) string {
	if runtime.GOOS == "windows" {
		return name + ".exe"
	}
	return name
}

func (fake *integrationRunner) RunStreaming(_ context.Context, command runner.Command, _ io.Writer, _ io.Writer) error {
	switch {
	case command.Name == "npm" && len(command.Args) == 1 && command.Args[0] == "install":
		return os.MkdirAll(filepath.Join(command.Dir, "node_modules"), 0o755)
	case command.Name == "python3" && len(command.Args) == 3 && command.Args[0] == "-m" && command.Args[1] == "venv":
		venvBin := filepath.Join(command.Dir, ".venv", venvSubdir())
		if err := os.MkdirAll(venvBin, 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(venvBin, venvBinName("pip")), []byte(""), 0o755); err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(venvBin, venvBinName("cocoindex")), []byte(""), 0o755)
	case strings.HasSuffix(command.Name, filepath.Join(".venv", venvSubdir(), venvBinName("pip"))):
		venvBin := filepath.Join(command.Dir, ".venv", venvSubdir())
		return os.WriteFile(filepath.Join(venvBin, venvBinName("cocoindex")), []byte(""), 0o755)
	case command.Name == "npm" && len(command.Args) == 2 && command.Args[0] == "run" && command.Args[1] == "build":
		if err := os.MkdirAll(filepath.Join(command.Dir, "dist"), 0o755); err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(command.Dir, "dist", "index.js"), []byte("export {};"), 0o644)
	case command.Name == "mempalace":
		return nil
	case strings.HasSuffix(command.Name, filepath.Join(".venv", venvSubdir(), venvBinName("cocoindex"))):
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
	cmd.SetArgs([]string{"setup", "agent", "--vscode", "--workspace-root", root})
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
	cmd.SetArgs([]string{"setup", "mcp", "--vscode", "--workspace-root", root})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(root, "coding-cli", "query-code-mcp", "dist", "index.js"))
	content, err := os.ReadFile(filepath.Join(home, "mcp.json"))
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), "query-code") {
		t.Fatalf("expected query-code in mcp.json, got %q", string(content))
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
	first.SetArgs([]string{"setup", "full", "--vscode", "--workspace-root", root})
	if err := first.Execute(); err != nil {
		t.Fatalf("first Execute returned error: %v", err)
	}

	configBefore, err := os.ReadFile(filepath.Join(home, "mcp.json"))
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}

	second := NewRootCommand(dependencies)
	second.SetArgs([]string{"setup", "full", "--vscode", "--workspace-root", root})
	if err := second.Execute(); err != nil {
		t.Fatalf("second Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(root, "coding-cli", "query-code-mcp", ".cocoindex", "codebase-index", "chunk.json"))

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
	cmd.SetArgs([]string{"setup", "mcp", "--workspace-root", root})
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
	first.SetArgs([]string{"setup", "full", "--vscode", "--workspace-root", root})
	if err := first.Execute(); err != nil {
		t.Fatalf("first Execute returned error: %v", err)
	}

	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}
	second := NewRootCommand(Dependencies{Logger: output.New(stdout, stderr, false), Runner: &integrationRunner{}})
	second.SetArgs([]string{"setup", "full", "--vscode", "--workspace-root", root})
	if err := second.Execute(); err != nil {
		t.Fatalf("second Execute returned error: %v", err)
	}

	combined := stdout.String() + "\n" + stderr.String()
	for _, expected := range []string{
		"step: verify indexing dependencies",
		"step: run indexing",
		"skipped query-code-mcp npm dependencies",
		"skipped query-code-mcp virtualenv",
		"mempalace wake-up",
		"cocoindex update",
		"skipped updating MCP config",
	} {
		if !strings.Contains(combined, expected) {
			t.Fatalf("expected log output to contain %q, got %q", expected, combined)
		}
	}
}

func TestSetupMCPSucceedsWithoutCocoIndexDependency(t *testing.T) {
	root, home := createWorkspaceFixture(t)
	setTestEnv(t, home)

	runner := &integrationRunner{}
	cmd := NewRootCommand(Dependencies{Logger: output.New(io.Discard, io.Discard, false), Runner: runner})
	cmd.SetArgs([]string{"setup", "mcp", "--batman", "--workspace-root", root})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute returned error: %v", err)
	}

	assertExists(t, filepath.Join(root, "coding-cli", "query-code-mcp", "dist", "index.js"))
	content, err := os.ReadFile(filepath.Join(home, "mcp.json"))
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), "https://api.githubcopilot.com/mcp/") {
		t.Fatalf("expected remote github MCP in mcp.json, got %q", string(content))
	}
}

func createWorkspaceFixture(t *testing.T) (string, string) {
	t.Helper()

	root := t.TempDir()
	home := filepath.Join(root, "home")
	paths := []string{
		filepath.Join(root, "coding-cli", "prompts"),
		filepath.Join(root, "coding-cli", "skills", "example-skill"),
		filepath.Join(root, "coding-cli", "query-code-mcp"),
		home,
	}
	for _, path := range paths {
		if err := os.MkdirAll(path, 0o755); err != nil {
			t.Fatalf("MkdirAll %s returned error: %v", path, err)
		}
	}
	files := map[string]string{
		filepath.Join(root, "coding-cli", "prompts", "demo.prompt.md"):           "prompt",
		filepath.Join(root, "coding-cli", "prompts", "demo.instructions.md"):     "instruction",
		filepath.Join(root, "coding-cli", "prompts", "batman.agent.md"):          "python3 -m mempalace hook run --harness {{MEMPALACE_HARNESS}}",
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
	// Override every home/config root the host detectors look at so the test
	// fixture wins on every platform — without these, Windows still falls
	// back to USERPROFILE/APPDATA/LOCALAPPDATA and finds the developer's real
	// Claude/Codex/VS Code installs during auto-detection.
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("APPDATA", filepath.Join(home, "AppData", "Roaming"))
	t.Setenv("LOCALAPPDATA", filepath.Join(home, "AppData", "Local"))
	// Clear claude/codex detection signals; the test only opts vscode in.
	t.Setenv("CLAUDE_CONFIG_DIR", "")
	t.Setenv("CODEX_HOME", "")
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
