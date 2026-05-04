package repos

import (
	"fmt"
	"os"
	"path/filepath"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
)

type Repository string

const (
	RepositoryCodingCLI    Repository = "coding-cli"
	RepositoryFrontend     Repository = "frontend"
	RepositoryBackend      Repository = "backend"
	RepositoryAIWatchtower Repository = "ai_watchtower"
)

var CloneTargets = []Repository{
	RepositoryFrontend,
	RepositoryBackend,
	RepositoryAIWatchtower,
}

type RepoLayout struct {
	Root            string
	CodingCLI       string
	Frontend        string
	Backend         string
	AIWatchtower    string
	FreightHeroMCP  string
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
			return clierrors.New(clierrors.KindValidation, fmt.Sprintf("missing %s at %s; rerun from the FreightHero workspace or pass --freighthero-root", repository, repositoryPath))
		}
	}

	return nil
}

func (layout RepoLayout) Path(repository Repository) string {
	switch repository {
	case RepositoryCodingCLI:
		return layout.CodingCLI
	case RepositoryFrontend:
		return layout.Frontend
	case RepositoryBackend:
		return layout.Backend
	case RepositoryAIWatchtower:
		return layout.AIWatchtower
	default:
		return ""
	}
}

func CloneRoot(currentWorkingDir string) string {
	return filepath.Join(currentWorkingDir, "freighthero")
}

func buildLayout(root string) RepoLayout {
	codingCLI := filepath.Join(root, string(RepositoryCodingCLI))
	freightHeroMCP := filepath.Join(codingCLI, "freighthero-mcp")

	return RepoLayout{
		Root:            root,
		CodingCLI:       codingCLI,
		Frontend:        filepath.Join(root, string(RepositoryFrontend)),
		Backend:         filepath.Join(root, string(RepositoryBackend)),
		AIWatchtower:    filepath.Join(root, string(RepositoryAIWatchtower)),
		FreightHeroMCP:  freightHeroMCP,
		CodebaseIndex:   filepath.Join(freightHeroMCP, ".cocoindex", "codebase-index"),
		CocoIndexDBPath: filepath.Join(freightHeroMCP, ".cocoindex", "cocoindex.db"),
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

	return "", clierrors.New(clierrors.KindValidation, "could not resolve FreightHero root; rerun from the FreightHero workspace or pass --freighthero-root")
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