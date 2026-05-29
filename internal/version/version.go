// Package version exposes the coding-cli build version. The value is "dev" for
// local builds and is overridden at release time via -ldflags
// "-X github.com/coding-cli/coding-cli/internal/version.Version=v0.3.0".
package version

// Version is the current coding-cli version. Overridden at build time.
var Version = "dev"

// IsDev reports whether this is an unversioned local build.
func IsDev() bool {
	return Version == "" || Version == "dev"
}
