package main

import (
	"fmt"
	"os"

	"github.com/coding-cli/coding-cli/cmd/codingcli"
	clierrors "github.com/coding-cli/coding-cli/internal/errors"
)

func main() {
	if err := codingcli.Execute(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(clierrors.ExitCode(err))
	}
}
