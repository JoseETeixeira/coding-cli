package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/repos"
)

func TestWriteVSCodeConfigPreservesUnrelatedFields(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "mcp.json")
	if err := os.WriteFile(path, []byte(`{"inputs":{"token":"keep"},"servers":{"existing":{"command":"keep"}}}`), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	result, err := writeJSONConfig(path, "servers", map[string]ManagedServer{"mempalace": {Command: "python3", Args: []string{"-m", "mempalace.mcp_server"}}})
	if err != nil {
		t.Fatalf("writeJSONConfig returned error: %v", err)
	}
	if result.Action != "updated" {
		t.Fatalf("result.Action = %q", result.Action)
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), "existing") || !strings.Contains(string(content), "mempalace") {
		t.Fatalf("content = %q", string(content))
	}
	if _, err := os.Stat(path + ".bak"); err != nil {
		t.Fatalf("expected backup file, got error: %v", err)
	}
}

func TestWriteCodexConfigPreservesOtherSections(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "config.toml")
	if err := os.WriteFile(path, []byte("[profile]\nname = \"dev\"\n"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	_, err := writeTOMLConfig(path, map[string]ManagedServer{"github": {Type: "http", URL: "https://api.githubcopilot.com/mcp/", BearerTokenEnvVar: "GITHUB_PAT_TOKEN"}})
	if err != nil {
		t.Fatalf("writeTOMLConfig returned error: %v", err)
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile returned error: %v", err)
	}
	if !strings.Contains(string(content), "[profile]") || !strings.Contains(string(content), "[mcp_servers.github]") {
		t.Fatalf("content = %q", string(content))
	}
}

func TestWriteConfigFailsOnInvalidJSON(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "broken.json")
	if err := os.WriteFile(path, []byte("{"), 0o644); err != nil {
		t.Fatalf("WriteFile returned error: %v", err)
	}

	_, err := writeJSONConfig(path, "servers", map[string]ManagedServer{})
	if err == nil {
		t.Fatal("expected parse error")
	}
}

func TestWriteJSONConfigFailsWhenPathIsUnreadable(t *testing.T) {
	t.Parallel()

	path := filepath.Join(t.TempDir(), "as-directory")
	if err := os.MkdirAll(path, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	_, err := writeJSONConfig(path, "servers", map[string]ManagedServer{})
	if err == nil {
		t.Fatal("expected read error")
	}
}

func TestManagedServersIncludeGitHubForVSCode(t *testing.T) {
	t.Parallel()

	layout := repos.RepoLayout{Root: "/tmp/root", FreightHeroMCP: "/tmp/root/coding-cli/freighthero-mcp", CodebaseIndex: "/tmp/root/coding-cli/freighthero-mcp/.cocoindex/codebase-index"}
	servers := ManagedServers(layout, host.HostProfile{Kind: host.HostVSCode})
	github, ok := servers["github"]
	if !ok {
		t.Fatal("expected github server for VS Code")
	}
	if github.Type != "http" {
		t.Fatalf("github.Type = %q", github.Type)
	}
	if github.URL != "https://api.githubcopilot.com/mcp/" {
		t.Fatalf("github.URL = %q", github.URL)
	}
	if github.BearerTokenEnvVar != "" {
		t.Fatalf("github.BearerTokenEnvVar = %q, want empty", github.BearerTokenEnvVar)
	}
}

func TestManagedServersIncludeCodexGithubTokenEnv(t *testing.T) {
	t.Parallel()

	layout := repos.RepoLayout{Root: "/tmp/root", FreightHeroMCP: "/tmp/root/coding-cli/freighthero-mcp", CodebaseIndex: "/tmp/root/coding-cli/freighthero-mcp/.cocoindex/codebase-index"}
	servers := ManagedServers(layout, host.HostProfile{Kind: host.HostCodex})
	github, ok := servers["github"]
	if !ok {
		t.Fatal("expected github server for codex")
	}
	if github.BearerTokenEnvVar != "GITHUB_PAT_TOKEN" {
		t.Fatalf("github.BearerTokenEnvVar = %q", github.BearerTokenEnvVar)
	}
}

func TestManagedServersIncludeRepowise(t *testing.T) {
	t.Parallel()

	layout := repos.RepoLayout{Root: "/tmp/root", FreightHeroMCP: "/tmp/root/coding-cli/freighthero-mcp", CodebaseIndex: "/tmp/root/coding-cli/freighthero-mcp/.cocoindex/codebase-index"}
	servers := ManagedServers(layout, host.HostProfile{Kind: host.HostClaudeCode})
	repowise, ok := servers["repowise"]
	if !ok {
		t.Fatal("expected repowise server")
	}
	if repowise.Command != "repowise" {
		t.Fatalf("repowise.Command = %q, want repowise", repowise.Command)
	}
	want := []string{"mcp", layout.Root}
	if len(repowise.Args) != len(want) || repowise.Args[0] != want[0] || repowise.Args[1] != want[1] {
		t.Fatalf("repowise.Args = %v, want %v", repowise.Args, want)
	}
}