package pyexec

import (
	"reflect"
	"runtime"
	"testing"
)

func TestShellForOS(t *testing.T) {
	t.Parallel()

	cases := []struct {
		goos string
		want string
	}{
		{goos: "windows", want: "py -3"},
		{goos: "darwin", want: "python3"},
		{goos: "linux", want: "python3"},
	}

	for _, tc := range cases {
		t.Run(tc.goos, func(t *testing.T) {
			t.Parallel()
			if got := shellForOS(tc.goos); got != tc.want {
				t.Fatalf("shellForOS(%q) = %q, want %q", tc.goos, got, tc.want)
			}
		})
	}
}

func TestCommandForOS(t *testing.T) {
	t.Parallel()

	cases := []struct {
		goos     string
		wantCmd  string
		wantArgs []string
	}{
		{goos: "windows", wantCmd: "py", wantArgs: []string{"-3"}},
		{goos: "darwin", wantCmd: "python3", wantArgs: nil},
		{goos: "linux", wantCmd: "python3", wantArgs: nil},
	}

	for _, tc := range cases {
		t.Run(tc.goos, func(t *testing.T) {
			t.Parallel()
			cmd, args := commandForOS(tc.goos)
			if cmd != tc.wantCmd {
				t.Fatalf("commandForOS(%q) cmd = %q, want %q", tc.goos, cmd, tc.wantCmd)
			}
			if !reflect.DeepEqual(args, tc.wantArgs) {
				t.Fatalf("commandForOS(%q) args = %v, want %v", tc.goos, args, tc.wantArgs)
			}
		})
	}
}

func TestPublicAPIMatchesCurrentOS(t *testing.T) {
	t.Parallel()

	if got, want := Shell(), shellForOS(runtime.GOOS); got != want {
		t.Fatalf("Shell() = %q, want %q for GOOS=%q", got, want, runtime.GOOS)
	}

	gotCmd, gotArgs := Command()
	wantCmd, wantArgs := commandForOS(runtime.GOOS)
	if gotCmd != wantCmd || !reflect.DeepEqual(gotArgs, wantArgs) {
		t.Fatalf("Command() = (%q, %v), want (%q, %v) for GOOS=%q", gotCmd, gotArgs, wantCmd, wantArgs, runtime.GOOS)
	}
}
