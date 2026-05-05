package deps

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"io"
	"testing"
)

func TestRTKAssetName(t *testing.T) {
	t.Parallel()

	tests := []struct {
		goos    string
		goarch  string
		want    string
		wantErr bool
	}{
		{goos: "darwin", goarch: "arm64", want: "rtk-aarch64-apple-darwin.tar.gz"},
		{goos: "darwin", goarch: "amd64", want: "rtk-x86_64-apple-darwin.tar.gz"},
		{goos: "linux", goarch: "arm64", want: "rtk-aarch64-unknown-linux-gnu.tar.gz"},
		{goos: "linux", goarch: "amd64", want: "rtk-x86_64-unknown-linux-musl.tar.gz"},
		{goos: "windows", goarch: "amd64", want: "rtk-x86_64-pc-windows-msvc.zip"},
		{goos: "windows", goarch: "arm64", wantErr: true},
	}

	for _, test := range tests {
		test := test
		t.Run(test.goos+"-"+test.goarch, func(t *testing.T) {
			t.Parallel()

			got, err := rtkAssetName(test.goos, test.goarch)
			if test.wantErr {
				if err == nil {
					t.Fatal("expected error")
				}
				return
			}
			if err != nil {
				t.Fatalf("rtkAssetName returned error: %v", err)
			}
			if got != test.want {
				t.Fatalf("rtkAssetName() = %q, want %q", got, test.want)
			}
		})
	}
}

func TestExtractBinaryFromTarGz(t *testing.T) {
	t.Parallel()

	payload := bytes.Buffer{}
	gzipWriter := gzip.NewWriter(&payload)
	tarWriter := tar.NewWriter(gzipWriter)
	content := []byte("rtk-binary")
	if err := tarWriter.WriteHeader(&tar.Header{Name: "rtk", Mode: 0o755, Size: int64(len(content)), Typeflag: tar.TypeReg}); err != nil {
		t.Fatalf("WriteHeader returned error: %v", err)
	}
	if _, err := tarWriter.Write(content); err != nil {
		t.Fatalf("Write returned error: %v", err)
	}
	if err := tarWriter.Close(); err != nil {
		t.Fatalf("Close tar writer returned error: %v", err)
	}
	if err := gzipWriter.Close(); err != nil {
		t.Fatalf("Close gzip writer returned error: %v", err)
	}

	binary, err := extractBinaryFromTarGz(payload.Bytes(), "rtk")
	if err != nil {
		t.Fatalf("extractBinaryFromTarGz returned error: %v", err)
	}
	if string(binary) != string(content) {
		t.Fatalf("binary = %q, want %q", string(binary), string(content))
	}
}

func TestExtractBinaryFromZip(t *testing.T) {
	t.Parallel()

	payload := bytes.Buffer{}
	zipWriter := zip.NewWriter(&payload)
	entry, err := zipWriter.Create("rtk.exe")
	if err != nil {
		t.Fatalf("Create returned error: %v", err)
	}
	content := []byte("rtk-exe")
	if _, err := io.Copy(entry, bytes.NewReader(content)); err != nil {
		t.Fatalf("Copy returned error: %v", err)
	}
	if err := zipWriter.Close(); err != nil {
		t.Fatalf("Close zip writer returned error: %v", err)
	}

	binary, err := extractBinaryFromZip(payload.Bytes(), "rtk.exe")
	if err != nil {
		t.Fatalf("extractBinaryFromZip returned error: %v", err)
	}
	if string(binary) != string(content) {
		t.Fatalf("binary = %q, want %q", string(binary), string(content))
	}
}