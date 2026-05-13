package repos

import (
	"os"
	"path/filepath"
	"testing"
)

func TestGetRepoLayoutFindsWorkspaceRootFromCodingCLIDirectory(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	codingCLI := filepath.Join(root, string(RepositoryCodingCLI))
	if err := os.MkdirAll(filepath.Join(codingCLI, "query-code-mcp"), 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	layout, err := GetRepoLayout("", codingCLI)
	if err != nil {
		t.Fatalf("GetRepoLayout returned error: %v", err)
	}
	if layout.Root != root {
		t.Fatalf("layout.Root = %q, want %q", layout.Root, root)
	}
	if layout.QueryCodeMCP != filepath.Join(codingCLI, "query-code-mcp") {
		t.Fatalf("layout.QueryCodeMCP = %q", layout.QueryCodeMCP)
	}
}

func TestValidateLayoutReportsMissingCodingCLI(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	layout, err := GetRepoLayout(root, root)
	if err != nil {
		t.Fatalf("GetRepoLayout returned error: %v", err)
	}

	if err := ValidateLayout(layout, RepositoryCodingCLI); err == nil {
		t.Fatal("expected validation error for missing coding-cli")
	}
}

func TestNormalizeRootStripsCodingCLISuffix(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	codingCLI := filepath.Join(root, string(RepositoryCodingCLI))
	if err := os.MkdirAll(codingCLI, 0o755); err != nil {
		t.Fatalf("MkdirAll returned error: %v", err)
	}

	layout, err := GetRepoLayout(codingCLI, codingCLI)
	if err != nil {
		t.Fatalf("GetRepoLayout returned error: %v", err)
	}
	if layout.Root != root {
		t.Fatalf("layout.Root = %q, want %q", layout.Root, root)
	}
}
