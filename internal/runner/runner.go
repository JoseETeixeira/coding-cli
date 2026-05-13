package runner

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"os/exec"
)

type Command struct {
	Name string
	Args []string
	Dir  string
	Env  []string
}

type Result struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

type ProcessRunner interface {
	Run(ctx context.Context, command Command) error
	RunCapturing(ctx context.Context, command Command) (Result, error)
	RunStreaming(ctx context.Context, command Command, stdout, stderr io.Writer) error
}

type ExecRunner struct{}

func NewExecRunner() *ExecRunner {
	return &ExecRunner{}
}

func (runner *ExecRunner) Run(ctx context.Context, command Command) error {
	cmd := buildCommand(ctx, command)
	return cmd.Run()
}

func (runner *ExecRunner) RunCapturing(ctx context.Context, command Command) (Result, error) {
	cmd := buildCommand(ctx, command)
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	result := Result{
		Stdout: stdout.String(),
		Stderr: stderr.String(),
	}

	if cmd.ProcessState != nil {
		result.ExitCode = cmd.ProcessState.ExitCode()
	}

	return result, err
}

func (runner *ExecRunner) RunStreaming(ctx context.Context, command Command, stdout io.Writer, stderr io.Writer) error {
	cmd := buildCommand(ctx, command)
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	return cmd.Run()
}

func buildCommand(ctx context.Context, command Command) *exec.Cmd {
	cmd := exec.CommandContext(ctx, command.Name, command.Args...)
	if command.Dir != "" {
		cmd.Dir = command.Dir
	}
	if len(command.Env) > 0 {
		cmd.Env = append(os.Environ(), command.Env...)
	}
	return cmd
}

func ExitCode(err error) int {
	if err == nil {
		return 0
	}

	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return exitErr.ExitCode()
	}

	return 1
}