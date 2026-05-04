package repos

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/runner"
)

type CloneResult struct {
	Repository Repository
	Path       string
	Skipped    bool
}

func CloneRepositories(ctx context.Context, processRunner runner.ProcessRunner, root string, repositories []Repository) ([]CloneResult, error) {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return nil, clierrors.Wrap(clierrors.KindClone, fmt.Sprintf("create clone root %s", root), err)
	}

	results := make([]CloneResult, 0, len(repositories))
	for _, repository := range repositories {
		result, err := CloneRepository(ctx, processRunner, root, repository)
		if err != nil {
			return results, err
		}

		results = append(results, result)
	}

	return results, nil
}

func CloneRepository(ctx context.Context, processRunner runner.ProcessRunner, root string, repository Repository) (CloneResult, error) {
	destination := filepath.Join(root, string(repository))
	if info, err := os.Stat(destination); err == nil {
		if !info.IsDir() {
			return CloneResult{}, clierrors.New(clierrors.KindClone, fmt.Sprintf("cannot clone %s because %s exists and is not a directory", repository, destination))
		}

		return CloneResult{Repository: repository, Path: destination, Skipped: true}, nil
	}

	command := runner.Command{
		Name: "git",
		Args: []string{"clone", RepositoryURL(repository), string(repository)},
		Dir:  root,
	}
	if err := processRunner.Run(ctx, command); err != nil {
		return CloneResult{}, clierrors.Wrap(clierrors.KindClone, fmt.Sprintf("clone %s", repository), err)
	}

	return CloneResult{Repository: repository, Path: destination}, nil
}

func RepositoryURL(repository Repository) string {
	return fmt.Sprintf("https://github.com/Freight-Hero/%s", repository)
}