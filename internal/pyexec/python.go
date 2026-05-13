// Package pyexec resolves how to invoke Python on the current OS for commands
// the coding-cli writes into downstream tool configuration (Claude Code hooks,
// MCP server entries).
//
// On Windows the literal "python3" command often resolves to the Microsoft
// Store stub at %LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe, which exits
// non-zero with the "Python was not found" message instead of launching
// Python. The official `py` launcher at C:\Windows\py.exe sidesteps the stub
// and is on PATH whenever a Python install is present.
//
// On macOS and Linux the convention remains `python3`, which is installed by
// the system package manager or pyenv and lives on PATH directly.
package pyexec

import "runtime"

// Shell returns the Python invocation as a single shell-ready string. Use this
// when the downstream tool consumes the full command line as one field — for
// example Claude Code's `hooks[].command` entries in settings.json.
func Shell() string {
	return shellForOS(runtime.GOOS)
}

// Command returns the Python executable name and the argument prefix that must
// be passed alongside it (selecting the Python 3 launcher on Windows). Use this
// when the downstream tool stores the command and its args in separate fields
// — for example MCP server entries in mcp.json.
func Command() (string, []string) {
	return commandForOS(runtime.GOOS)
}

func shellForOS(goos string) string {
	if goos == "windows" {
		return "py -3"
	}
	return "python3"
}

func commandForOS(goos string) (string, []string) {
	if goos == "windows" {
		return "py", []string{"-3"}
	}
	return "python3", nil
}
