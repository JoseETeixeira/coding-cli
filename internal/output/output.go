package output

import (
	"fmt"
	"io"
	"sync"
)

type Logger struct {
	stdout  io.Writer
	stderr  io.Writer
	verbose bool
	mu      sync.Mutex
}

func New(stdout, stderr io.Writer, verbose bool) *Logger {
	return &Logger{
		stdout:  stdout,
		stderr:  stderr,
		verbose: verbose,
	}
}

func (logger *Logger) SetVerbose(verbose bool) {
	logger.mu.Lock()
	defer logger.mu.Unlock()
	logger.verbose = verbose
}

func (logger *Logger) Info(message string) {
	logger.write(logger.stdout, message)
}

func (logger *Logger) Success(message string) {
	logger.write(logger.stdout, fmt.Sprintf("OK: %s", message))
}

func (logger *Logger) Warn(message string) {
	logger.write(logger.stderr, fmt.Sprintf("WARN: %s", message))
}

func (logger *Logger) Error(message string) {
	logger.write(logger.stderr, fmt.Sprintf("ERROR: %s", message))
}

func (logger *Logger) Verbose(message string) {
	logger.mu.Lock()
	verbose := logger.verbose
	logger.mu.Unlock()

	if !verbose {
		return
	}

	logger.write(logger.stdout, fmt.Sprintf("DEBUG: %s", message))
}

func (logger *Logger) write(writer io.Writer, message string) {
	logger.mu.Lock()
	defer logger.mu.Unlock()
	_, _ = fmt.Fprintln(writer, message)
}