package output

import (
	"bytes"
	"strings"
	"testing"
)

func TestLoggerWritesByLevel(t *testing.T) {
	t.Parallel()

	var stdout bytes.Buffer
	var stderr bytes.Buffer

	logger := New(&stdout, &stderr, false)
	logger.Info("hello")
	logger.Success("done")
	logger.Warn("careful")
	logger.Error("broken")
	logger.Verbose("hidden")

	stdoutText := stdout.String()
	stderrText := stderr.String()

	if !strings.Contains(stdoutText, "hello") {
		t.Fatalf("expected info output, got %q", stdoutText)
	}
	if !strings.Contains(stdoutText, "OK: done") {
		t.Fatalf("expected success output, got %q", stdoutText)
	}
	if strings.Contains(stdoutText, "hidden") {
		t.Fatalf("did not expect verbose output when disabled, got %q", stdoutText)
	}
	if !strings.Contains(stderrText, "WARN: careful") {
		t.Fatalf("expected warning output, got %q", stderrText)
	}
	if !strings.Contains(stderrText, "ERROR: broken") {
		t.Fatalf("expected error output, got %q", stderrText)
	}
}

func TestLoggerVerboseOutput(t *testing.T) {
	t.Parallel()

	var stdout bytes.Buffer
	var stderr bytes.Buffer

	logger := New(&stdout, &stderr, false)
	logger.Verbose("hidden")
	logger.SetVerbose(true)
	logger.Verbose("visible")

	stdoutText := stdout.String()
	if strings.Contains(stdoutText, "hidden") {
		t.Fatalf("did not expect first verbose message, got %q", stdoutText)
	}
	if !strings.Contains(stdoutText, "DEBUG: visible") {
		t.Fatalf("expected verbose output after enabling verbose mode, got %q", stdoutText)
	}
}