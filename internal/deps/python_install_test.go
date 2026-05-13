package deps

import (
	"os"
	"strings"
	"testing"
)

func TestUVAssetName(t *testing.T) {
	t.Parallel()

	tests := []struct {
		goos    string
		goarch  string
		want    string
		wantErr bool
	}{
		{goos: "darwin", goarch: "arm64", want: "uv-aarch64-apple-darwin.tar.gz"},
		{goos: "darwin", goarch: "amd64", want: "uv-x86_64-apple-darwin.tar.gz"},
		{goos: "linux", goarch: "arm64", want: "uv-aarch64-unknown-linux-gnu.tar.gz"},
		{goos: "linux", goarch: "amd64", want: "uv-x86_64-unknown-linux-gnu.tar.gz"},
		{goos: "windows", goarch: "amd64", want: "uv-x86_64-pc-windows-msvc.zip"},
		{goos: "windows", goarch: "386", wantErr: true},
	}

	for _, test := range tests {
		test := test
		t.Run(test.goos+"-"+test.goarch, func(t *testing.T) {
			t.Parallel()

			got, err := uvAssetName(test.goos, test.goarch)
			if test.wantErr {
				if err == nil {
					t.Fatal("expected error")
				}
				return
			}
			if err != nil {
				t.Fatalf("uvAssetName returned error: %v", err)
			}
			if got != test.want {
				t.Fatalf("uvAssetName() = %q, want %q", got, test.want)
			}
		})
	}
}

func TestPythonInstallVersion(t *testing.T) {
	t.Parallel()

	tests := []struct {
		minVersion string
		want       string
	}{
		{minVersion: "3.9.0", want: "3.11"},
		{minVersion: "3.11.0", want: "3.11"},
		{minVersion: "3.12.4", want: "3.12"},
	}

	for _, test := range tests {
		if got := pythonInstallVersion(test.minVersion); got != test.want {
			t.Fatalf("pythonInstallVersion(%q) = %q, want %q", test.minVersion, got, test.want)
		}
	}
}

func TestPrependPathPromotesInstallDir(t *testing.T) {
	original := os.Getenv("PATH")
	t.Setenv("PATH", strings.Join([]string{"/usr/bin", "/tmp/fh-bin", "/bin"}, string(os.PathListSeparator)))
	defer os.Setenv("PATH", original)

	prependPath("/tmp/fh-bin")
	parts := filepathSplitListForTest(os.Getenv("PATH"))
	if len(parts) == 0 || parts[0] != "/tmp/fh-bin" {
		t.Fatalf("PATH = %q", os.Getenv("PATH"))
	}
	count := 0
	for _, part := range parts {
		if part == "/tmp/fh-bin" {
			count++
		}
	}
	if count != 1 {
		t.Fatalf("expected promoted path once, got %q", os.Getenv("PATH"))
	}
}

func filepathSplitListForTest(path string) []string {
	if path == "" {
		return nil
	}
	return strings.Split(path, string(os.PathListSeparator))
}
