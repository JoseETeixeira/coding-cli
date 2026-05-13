package runner

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"testing"
)

func TestExecRunnerRunCapturing(t *testing.T) {
	t.Parallel()

	runner := NewExecRunner()
	command := helperCommand("stdout=hello", "stderr=warning", "exit=0")

	result, err := runner.RunCapturing(context.Background(), command)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if strings.TrimSpace(result.Stdout) != "hello" {
		t.Fatalf("expected stdout to equal hello, got %q", result.Stdout)
	}
	if strings.TrimSpace(result.Stderr) != "warning" {
		t.Fatalf("expected stderr to equal warning, got %q", result.Stderr)
	}
	if result.ExitCode != 0 {
		t.Fatalf("expected exit code 0, got %d", result.ExitCode)
	}
}

func TestExecRunnerRunStreaming(t *testing.T) {
	t.Parallel()

	runner := NewExecRunner()
	command := helperCommand("stdout=streamed", "stderr=problem", "exit=0")

	var stdout bytes.Buffer
	var stderr bytes.Buffer

	err := runner.RunStreaming(context.Background(), command, &stdout, &stderr)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if strings.TrimSpace(stdout.String()) != "streamed" {
		t.Fatalf("expected stdout to equal streamed, got %q", stdout.String())
	}
	if strings.TrimSpace(stderr.String()) != "problem" {
		t.Fatalf("expected stderr to equal problem, got %q", stderr.String())
	}
}

func TestExecRunnerRunReturnsExitError(t *testing.T) {
	t.Parallel()

	runner := NewExecRunner()
	command := helperCommand("stdout=ignored", "stderr=failure", "exit=7")

	err := runner.Run(context.Background(), command)
	if err == nil {
		t.Fatal("expected exit error, got nil")
	}
	if code := ExitCode(err); code != 7 {
		t.Fatalf("expected exit code 7, got %d", code)
	}
}

func helperCommand(arguments ...string) Command {
	args := []string{"-test.run=TestHelperProcess", "--"}
	args = append(args, arguments...)

	return Command{
		Name: os.Args[0],
		Args: args,
		Env:  []string{"GO_WANT_HELPER_PROCESS=1"},
	}
}

func TestHelperProcess(t *testing.T) {
	if os.Getenv("GO_WANT_HELPER_PROCESS") != "1" {
		return
	}

	arguments := os.Args
	separator := -1
	for index, argument := range arguments {
		if argument == "--" {
			separator = index
			break
		}
	}
	if separator == -1 {
		fmt.Fprintln(os.Stderr, "missing separator")
		os.Exit(2)
	}

	stdout := ""
	stderr := ""
	exitCode := 0

	for _, argument := range arguments[separator+1:] {
		parts := strings.SplitN(argument, "=", 2)
		if len(parts) != 2 {
			continue
		}

		switch parts[0] {
		case "stdout":
			stdout = parts[1]
		case "stderr":
			stderr = parts[1]
		case "exit":
			parsed, err := strconv.Atoi(parts[1])
			if err != nil {
				fmt.Fprintln(os.Stderr, err.Error())
				os.Exit(2)
			}
			exitCode = parsed
		}
	}

	if stdout != "" {
		fmt.Fprintln(os.Stdout, stdout)
	}
	if stderr != "" {
		fmt.Fprintln(os.Stderr, stderr)
	}
	os.Exit(exitCode)
}