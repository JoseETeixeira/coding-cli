package host

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/coding-cli/coding-cli/internal/paths"
)

func TestResolveSelectedExplicitHost(t *testing.T) {
	t.Parallel()

	resolver := paths.NewResolverWith("/Users/tester", "darwin", nil)
	detector := NewDetectorWith(resolver, nil, nil)

	profile, err := detector.ResolveSelected(SelectionFlags{Batman: true}, false)
	if err != nil {
		t.Fatalf("ResolveSelected() error = %v", err)
	}
	if profile.Kind != HostBatman {
		t.Fatalf("profile.Kind = %q, want %q", profile.Kind, HostBatman)
	}
	if profile.Harness != "codex" {
		t.Fatalf("profile.Harness = %q, want %q", profile.Harness, "codex")
	}
	if profile.Roots.MCPConfigPath != filepath.Join("/Users/tester", "Library", "Application Support", "Code", "User", "mcp.json") {
		t.Fatalf("profile.Roots.MCPConfigPath = %q", profile.Roots.MCPConfigPath)
	}
}

func TestResolveSelectedExplicitClaudeHost(t *testing.T) {
	t.Parallel()

	resolver := paths.NewResolverWith("/Users/tester", "darwin", nil)
	detector := NewDetectorWith(resolver, nil, nil)

	profile, err := detector.ResolveSelected(SelectionFlags{ClaudeCode: true}, false)
	if err != nil {
		t.Fatalf("ResolveSelected() error = %v", err)
	}
	if profile.Kind != HostClaudeCode {
		t.Fatalf("profile.Kind = %q, want %q", profile.Kind, HostClaudeCode)
	}
	if profile.Harness != "claude-code" {
		t.Fatalf("profile.Harness = %q, want %q", profile.Harness, "claude-code")
	}
}

func TestResolveSelectedRequiresOneExplicitHost(t *testing.T) {
	t.Parallel()

	resolver := paths.NewResolverWith("/tmp/home", "linux", nil)
	detector := NewDetectorWith(resolver, nil, nil)

	_, err := detector.ResolveSelected(SelectionFlags{}, false)
	if err == nil {
		t.Fatal("expected validation error, got nil")
	}
	if !strings.Contains(err.Error(), "select exactly one host flag") {
		t.Fatalf("error = %q", err.Error())
	}
}

func TestResolveSelectedFailsWhenAutoDetectFindsNone(t *testing.T) {
	t.Parallel()

	resolver := paths.NewResolverWith("/tmp/home", "linux", nil)
	detector := NewDetectorWith(resolver, nil, nil)

	_, err := detector.ResolveSelected(SelectionFlags{}, true)
	if err == nil {
		t.Fatal("expected validation error, got nil")
	}
	if !strings.Contains(err.Error(), "no supported host detected") {
		t.Fatalf("error = %q", err.Error())
	}
}

func TestResolveSelectedFailsWhenAutoDetectFindsMany(t *testing.T) {
	t.Parallel()

	env := lookupMap(map[string]string{
		"CLAUDE_CONFIG_DIR": "/tmp/home/.claude",
		"CODEX_HOME":        "/tmp/home/.codex",
	})
	resolver := paths.NewResolverWith("/tmp/home", "linux", env)
	detector := NewDetectorWith(resolver, env, nil)

	_, err := detector.ResolveSelected(SelectionFlags{}, true)
	if err == nil {
		t.Fatal("expected validation error, got nil")
	}
	if !strings.Contains(err.Error(), "multiple supported hosts detected") {
		t.Fatalf("error = %q", err.Error())
	}
}

func TestResolveSelectedAutoDetectsSingleHost(t *testing.T) {
	t.Parallel()

	env := lookupMap(map[string]string{
		"CODEX_HOME": "/tmp/home/.codex",
	})
	resolver := paths.NewResolverWith("/tmp/home", "linux", env)
	detector := NewDetectorWith(resolver, env, nil)

	profile, err := detector.ResolveSelected(SelectionFlags{}, true)
	if err != nil {
		t.Fatalf("ResolveSelected() error = %v", err)
	}
	if profile.Kind != HostCodex {
		t.Fatalf("profile.Kind = %q, want %q", profile.Kind, HostCodex)
	}
	if profile.Roots.MCPConfigPath != filepath.Join("/tmp/home", ".codex", "config.toml") {
		t.Fatalf("profile.Roots.MCPConfigPath = %q", profile.Roots.MCPConfigPath)
	}
	if profile.Harness != "codex" {
		t.Fatalf("profile.Harness = %q", profile.Harness)
	}
}

func lookupMap(values map[string]string) func(string) (string, bool) {
	return func(key string) (string, bool) {
		value, ok := values[key]
		return value, ok
	}
}
