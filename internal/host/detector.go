package host

import (
	"fmt"
	"os"
	"sort"
	"strings"

	clierrors "github.com/coding-cli/coding-cli/internal/errors"
	"github.com/coding-cli/coding-cli/internal/paths"
)

type Detector struct {
	Resolver  paths.Resolver
	lookupEnv func(string) (string, bool)
	exists    func(string) bool
}

func NewDetector(resolver paths.Resolver) Detector {
	return NewDetectorWith(resolver, os.LookupEnv, func(path string) bool {
		_, err := os.Stat(path)
		return err == nil
	})
}

func NewDetectorWith(resolver paths.Resolver, lookupEnv func(string) (string, bool), exists func(string) bool) Detector {
	if lookupEnv == nil {
		lookupEnv = func(string) (string, bool) {
			return "", false
		}
	}
	if exists == nil {
		exists = func(string) bool {
			return false
		}
	}

	return Detector{
		Resolver:  resolver,
		lookupEnv: lookupEnv,
		exists:    exists,
	}
}

func (detector Detector) DetectHosts() []HostKind {
	detected := make([]HostKind, 0, 4)
	if detector.detectVSCode() {
		detected = append(detected, HostVSCode)
	}
	if detector.detectBatman() {
		detected = append(detected, HostBatman)
	}
	if detector.detectClaude() {
		detected = append(detected, HostClaudeCode)
	}
	if detector.detectCodex() {
		detected = append(detected, HostCodex)
	}

	return detected
}

func (detector Detector) ResolveSelected(flags SelectionFlags, allowAuto bool) (HostProfile, error) {
	kind, explicit, err := flags.ExplicitKind()
	if err != nil {
		return HostProfile{}, err
	}
	if explicit {
		return ResolveProfile(kind, detector.Resolver)
	}
	if !allowAuto {
		return HostProfile{}, clierrors.New(clierrors.KindValidation, fmt.Sprintf("select exactly one host flag: %s", ValidFlagList()))
	}

	detected := detector.DetectHosts()
	switch len(detected) {
	case 0:
		return HostProfile{}, clierrors.New(clierrors.KindValidation, fmt.Sprintf("no supported host detected; choose one of %s", ValidFlagList()))
	case 1:
		return ResolveProfile(detected[0], detector.Resolver)
	default:
		names := make([]string, 0, len(detected))
		for _, detectedKind := range detected {
			names = append(names, string(detectedKind))
		}
		sort.Strings(names)
		return HostProfile{}, clierrors.New(clierrors.KindValidation, fmt.Sprintf("multiple supported hosts detected (%s); rerun with one of %s", strings.Join(names, ", "), ValidFlagList()))
	}
}

func (detector Detector) detectVSCode() bool {
	if detector.hasEnv("VSCODE_USER_PROMPTS_FOLDER", "VSCODE_USER_DIR") {
		return true
	}

	return detector.exists(detector.Resolver.VSCodePromptDir()) || detector.exists(detector.Resolver.VSCodeMCPConfigPath())
}

func (detector Detector) detectBatman() bool {
	return detector.hasEnv("BATMAN", "BATMAN_AGENT", "BATMAN_HARNESS", "BATMAN_CONFIG_DIR")
}

func (detector Detector) detectClaude() bool {
	if detector.hasEnv("CLAUDE_CONFIG_DIR") {
		return true
	}

	return detector.exists(detector.Resolver.ClaudeRoot()) || detector.exists(detector.Resolver.ClaudeConfigPath())
}

func (detector Detector) detectCodex() bool {
	if detector.hasEnv("CODEX_HOME") {
		return true
	}

	return detector.exists(detector.Resolver.CodexRoot()) || detector.exists(detector.Resolver.CodexConfigPath())
}

func (detector Detector) hasEnv(keys ...string) bool {
	for _, key := range keys {
		value, ok := detector.lookupEnv(key)
		if ok && strings.TrimSpace(value) != "" {
			return true
		}
	}

	return false
}