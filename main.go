package main

import (
	"os"

	"github.com/Freight-Hero/coding-cli/cmd/freighthero"
	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
)

func main() {
	if err := freighthero.Execute(); err != nil {
		os.Exit(clierrors.ExitCode(err))
	}
}