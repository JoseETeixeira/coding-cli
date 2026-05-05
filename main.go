package main

import (
	"fmt"
	"os"

	"github.com/Freight-Hero/coding-cli/cmd/freighthero"
	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
)

func main() {
	if err := freighthero.Execute(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(clierrors.ExitCode(err))
	}
}