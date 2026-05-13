package repos

import (
	"fmt"
	"os"
	"path/filepath"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
)

type Repository string

const (
	RepositoryCodingCLI Repository = "coding-cli"
)

type RepoLayout struct {
	Root            string
	CodingCLI       string
	QueryCodeMCP    string
	CodebaseIndex   string
	CocoIndexDBPath string
}

func GetRepoLayout(rootOverride string, currentWorkingDir string) (RepoLayout, error) {
	root, err := resolveRoot(rootOverride, currentWorkingDir)
	if err != nil {
		return RepoLayout{}, err
	}

	return buildLayout(root), nil
}

func ValidateLayout(layout RepoLayout, required ...Repository) error {
	for _, repository := range required {
		repositoryPath := layout.Path(repository)
		if repositoryPath == "" {
			return clierrors.New(clierrors.KindValidation, fmt.Sprintf("unsupported repository %q", repository))
		}
		if !directoryExists(repositoryPath) {
			return clierrors.New(clierrors.KindValidation, fmt.Sprintf("missing %s at %s; rerun from the workspace or pass --workspace-root", repository, repositoryPath))
		}
	}

	return nil
}

func (layout RepoLayout) Path(repository Repository) string {
	switch repository {
	case RepositoryCodingCLI:
		return layout.CodingCLI
	default:
		return ""
	}
}

func buildLayout(root string) RepoLayout {
	codingCLI := filepath.Join(root, string(RepositoryCodingCLI))
	queryCodeMCP := filepath.Join(codingCLI, "query-code-mcp")

	return RepoLayout{
		Root:            root,
		CodingCLI:       codingCLI,
		QueryCodeMCP:    queryCodeMCP,
		CodebaseIndex:   filepath.Join(queryCodeMCP, ".cocoindex", "codebase-index"),
		CocoIndexDBPath: filepath.Join(queryCodeMCP, ".cocoindex", "cocoindex.db"),
	}
}

func resolveRoot(rootOverride string, currentWorkingDir string) (string, error) {
	if rootOverride != "" {
		return normalizeRoot(rootOverride), nil
	}

	candidate := filepath.Clean(currentWorkingDir)
	for {
		if directoryExists(filepath.Join(candidate, string(RepositoryCodingCLI))) {
			return candidate, nil
		}

		parent := filepath.Dir(candidate)
		if parent == candidate {
			break
		}

		candidate = parent
	}

	return "", clierrors.New(clierrors.KindValidation, "could not resolve workspace root; rerun from a workspace containing a coding-cli/ directory or pass --workspace-root")
}

func normalizeRoot(root string) string {
	cleanRoot := filepath.Clean(root)
	if filepath.Base(cleanRoot) == string(RepositoryCodingCLI) {
		return filepath.Dir(cleanRoot)
	}

	return cleanRoot
}

func directoryExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}
