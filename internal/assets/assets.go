package assets

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	clierrors "github.com/Freight-Hero/coding-cli/internal/errors"
	"github.com/Freight-Hero/coding-cli/internal/host"
	"github.com/Freight-Hero/coding-cli/internal/repos"
)

const (
	managedStart                = "<!-- freighthero:start -->"
	managedEnd                  = "<!-- freighthero:end -->"
	mempalaceHarnessPlaceholder = "{{MEMPALACE_HARNESS}}"

	// vscodeBatmanFrontmatterTools is the tools list in batman.agent.md as authored for the VS Code Batman extension.
	vscodeBatmanFrontmatterTools = "tools: [vscode, execute, read, agent, edit, search, web, 'github/*', 'mempalace/*', browser, 'pylance-mcp-server/*', 'freighthero-codebase/*', todo]"

	// claudeCodeFrontmatterTools is the Claude Code-compatible replacement installed to ~/.claude/agents/.
	claudeCodeFrontmatterTools = "tools: [Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion, WebFetch, WebSearch, TodoWrite, mcp__mempalace__mempalace_status, mcp__mempalace__mempalace_search, mcp__mempalace__mempalace_kg_add, mcp__mempalace__mempalace_kg_query, mcp__mempalace__mempalace_kg_invalidate, mcp__mempalace__mempalace_diary_write, mcp__freighthero-codebase__search_codebase, mcp__freighthero-codebase__explain_code, mcp__freighthero-codebase__analyze_error, mcp__freighthero-codebase__indexing_status, mcp__github__get_me, mcp__github__issue_read, mcp__github__issue_write, mcp__github__list_issues, mcp__github__search_issues, mcp__github__add_issue_comment, mcp__github__create_pull_request, mcp__github__pull_request_read, mcp__github__update_pull_request, mcp__github__merge_pull_request, mcp__github__pull_request_review_write, mcp__github__list_pull_requests, mcp__github__search_pull_requests, mcp__github__add_comment_to_pending_review, mcp__github__list_branches, mcp__github__create_branch, mcp__github__list_commits, mcp__github__get_commit, mcp__github__get_file_contents, mcp__github__search_repositories, mcp__github__search_code, mcp__github__create_or_update_file, mcp__github__push_files, mcp__github__list_notifications, mcp__github__get_notification_details]"
)

// frontmatterHooksRe matches the YAML hooks block in batman.agent.md frontmatter.
// Claude Code agent files do not support in-file hooks; hooks belong in settings.json.
var frontmatterHooksRe = regexp.MustCompile(`(?m)^hooks:\n(?:[ \t]+.*\n)+`)

type SyncOptions struct {
	Force bool
}

type AssetResult struct {
	AssetType   string
	Source      string
	Destination string
	Action      string
}

func SyncAssets(layout repos.RepoLayout, profile host.HostProfile, options SyncOptions) ([]AssetResult, error) {
	promptRoot := filepath.Join(layout.CodingCLI, "prompts")
	skillRoot := filepath.Join(layout.CodingCLI, "skills")

	entries, err := os.ReadDir(promptRoot)
	if err != nil {
		return nil, clierrors.Wrap(clierrors.KindConfig, "read prompt assets", err)
	}

	results := make([]AssetResult, 0, len(entries)+8)
	instructionSources := make([]string, 0)
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		sourcePath := filepath.Join(promptRoot, entry.Name())
		switch {
		case strings.HasSuffix(entry.Name(), ".prompt.md"):
			if profile.Roots.PromptDir == "" {
				results = append(results, AssetResult{AssetType: "prompt", Source: sourcePath, Action: "skipped-unsupported"})
				continue
			}
			result, copyErr := syncFile(sourcePath, filepath.Join(profile.Roots.PromptDir, entry.Name()), profile.Harness, options)
			if copyErr != nil {
				return results, copyErr
			}
			results = append(results, result)
		case strings.HasSuffix(entry.Name(), ".instructions.md"):
			instructionSources = append(instructionSources, sourcePath)
			if profile.Roots.InstructionDir != "" {
				result, copyErr := syncFile(sourcePath, filepath.Join(profile.Roots.InstructionDir, entry.Name()), profile.Harness, options)
				if copyErr != nil {
					return results, copyErr
				}
				results = append(results, result)
			}
		case strings.HasSuffix(entry.Name(), ".agent.md"):
			if profile.Roots.AgentDir == "" {
				results = append(results, AssetResult{AssetType: "agent", Source: sourcePath, Action: "skipped-unsupported"})
				continue
			}
			result, copyErr := syncFile(sourcePath, filepath.Join(profile.Roots.AgentDir, entry.Name()), profile.Harness, options)
			if copyErr != nil {
				return results, copyErr
			}
			results = append(results, result)
		}
	}

	if profile.Roots.InstructionFile != "" {
		result, mergeErr := mergeInstructionFile(instructionSources, profile.Roots.InstructionFile)
		if mergeErr != nil {
			return results, mergeErr
		}
		results = append(results, result)
	}

	skillEntries, err := os.ReadDir(skillRoot)
	if err != nil {
		return results, clierrors.Wrap(clierrors.KindConfig, "read skill assets", err)
	}
	for _, entry := range skillEntries {
		if !entry.IsDir() {
			continue
		}
		sourcePath := filepath.Join(skillRoot, entry.Name())
		if profile.Roots.SkillDir == "" {
			results = append(results, AssetResult{AssetType: "skill", Source: sourcePath, Action: "skipped-unsupported"})
			continue
		}

		result, copyErr := syncDirectory(sourcePath, filepath.Join(profile.Roots.SkillDir, entry.Name()), profile.Harness, options)
		if copyErr != nil {
			return results, copyErr
		}
		results = append(results, result)
	}

	if profile.Roots.SettingsPath != "" {
		result, hookErr := mergeClaudeHooks(profile.Roots.SettingsPath)
		if hookErr != nil {
			return results, hookErr
		}
		results = append(results, result)
	}

	return results, nil
}

// mergeClaudeHooks reads the Claude Code settings.json at path, injects the mempalace
// Stop and PreCompact hooks (preserving all other settings), and writes the result back.
// The file is created with an empty object if it does not yet exist.
func mergeClaudeHooks(path string) (AssetResult, error) {
	raw := []byte("{}")
	if existing, err := os.ReadFile(path); err == nil {
		raw = existing
	} else if !errors.Is(err, os.ErrNotExist) {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", path), err)
	}

	var settings map[string]json.RawMessage
	if err := json.Unmarshal(raw, &settings); err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse %s", path), err)
	}

	// Decode the existing hooks object (or start empty).
	hooks := map[string]json.RawMessage{}
	if existing, ok := settings["hooks"]; ok {
		if err := json.Unmarshal(existing, &hooks); err != nil {
			return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("parse hooks in %s", path), err)
		}
	}

	type hookEntry struct {
		Hooks []struct {
			Type    string `json:"type"`
			Command string `json:"command"`
			Timeout int    `json:"timeout"`
		} `json:"hooks"`
	}

	makeEntry := func(hook string) (json.RawMessage, error) {
		entry := []hookEntry{{
			Hooks: []struct {
				Type    string `json:"type"`
				Command string `json:"command"`
				Timeout int    `json:"timeout"`
			}{{
				Type:    "command",
				Command: "python3 -m mempalace hook run --hook " + hook + " --harness claude-code",
				Timeout: 30,
			}},
		}}
		return json.Marshal(entry)
	}

	stopRaw, err := makeEntry("stop")
	if err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, "marshal Stop hook", err)
	}
	precompactRaw, err := makeEntry("precompact")
	if err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, "marshal PreCompact hook", err)
	}

	hooks["Stop"] = stopRaw
	hooks["PreCompact"] = precompactRaw

	hooksRaw, err := json.Marshal(hooks)
	if err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, "marshal hooks", err)
	}
	settings["hooks"] = hooksRaw

	out, err := json.MarshalIndent(settings, "", "    ")
	if err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, "marshal settings", err)
	}
	out = append(out, '\n')

	action, err := writeFile(path, out, SyncOptions{Force: true})
	if err != nil {
		return AssetResult{}, err
	}

	return AssetResult{AssetType: "settings", Destination: path, Action: action}, nil
}

func InsertManagedBlock(existing string, managed string) string {
	block := managedStart + "\n" + strings.TrimSpace(managed) + "\n" + managedEnd
	if strings.Contains(existing, managedStart) && strings.Contains(existing, managedEnd) {
		start := strings.Index(existing, managedStart)
		end := strings.Index(existing, managedEnd) + len(managedEnd)
		return existing[:start] + block + existing[end:]
	}
	if strings.TrimSpace(existing) == "" {
		return block + "\n"
	}

	return strings.TrimRight(existing, "\n") + "\n\n" + block + "\n"
}

func RenderTemplate(content []byte, harness string, sourcePath string) []byte {
	if filepath.Base(sourcePath) != "batman.agent.md" {
		return content
	}

	rendered := string(content)
	if harness == string(host.HostClaudeCode) {
		rendered = applyClaudeCodeTransforms(rendered)
	}

	rendered = strings.ReplaceAll(rendered, mempalaceHarnessPlaceholder, harness)
	return []byte(strings.ReplaceAll(rendered, "--harness copilot", "--harness "+harness))
}

// applyClaudeCodeTransforms rewrites the batman.agent.md template for the Claude Code host.
// It replaces VS Code Batman tool references with Claude Code native equivalents, swaps the
// frontmatter tools list, strips the hooks block (not supported in Claude Code agent files),
// and injects the model field so Claude Code sessions use the appropriate model tier.
func applyClaudeCodeTransforms(content string) string {
	// Remove the frontmatter hooks block — Claude Code agent files don't support in-file hooks.
	content = frontmatterHooksRe.ReplaceAllString(content, "")

	// Replace VS Code Batman tool invocation syntax with Claude Code native tools.
	content = strings.ReplaceAll(content, "#tool:vscode/askQuestions", "AskUserQuestion")
	content = strings.ReplaceAll(content, "#tool:agent/runSubagent", "Agent")

	// Replace the frontmatter tools list with Claude Code-compatible tool names.
	content = strings.ReplaceAll(content, vscodeBatmanFrontmatterTools, claudeCodeFrontmatterTools)

	// Inject the model field after the name line — Claude Code only, not VS Code / Copilot.
	content = strings.ReplaceAll(content, "name: \"Batman Agent\"\n", "name: \"Batman Agent\"\nmodel: \"opus\"\n")

	return content
}

func syncDirectory(sourceDir string, destinationDir string, harness string, options SyncOptions) (AssetResult, error) {
	action := "skipped"
	err := filepath.Walk(sourceDir, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relativePath, err := filepath.Rel(sourceDir, path)
		if err != nil {
			return err
		}
		targetPath := filepath.Join(destinationDir, relativePath)
		if info.IsDir() {
			return os.MkdirAll(targetPath, 0o755)
		}

		result, err := syncFile(path, targetPath, harness, options)
		if err != nil {
			return err
		}
		switch result.Action {
		case "created", "updated":
			action = "updated"
		case "skipped-conflict":
			if action == "skipped" {
				action = result.Action
			}
		}
		return nil
	})
	if err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("sync skill directory %s", sourceDir), err)
	}

	return AssetResult{AssetType: "skill", Source: sourceDir, Destination: destinationDir, Action: action}, nil
}

func syncFile(sourcePath string, destinationPath string, harness string, options SyncOptions) (AssetResult, error) {
	content, err := os.ReadFile(sourcePath)
	if err != nil {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", sourcePath), err)
	}
	content = RenderTemplate(content, harness, sourcePath)

	action, err := writeFile(destinationPath, content, options)
	if err != nil {
		return AssetResult{}, err
	}

	assetType := "prompt"
	if strings.HasSuffix(sourcePath, ".instructions.md") {
		assetType = "instruction"
	}
	if strings.HasSuffix(sourcePath, ".agent.md") {
		assetType = "agent"
	}

	return AssetResult{AssetType: assetType, Source: sourcePath, Destination: destinationPath, Action: action}, nil
}

func mergeInstructionFile(sourcePaths []string, destinationPath string) (AssetResult, error) {
	managedContent, err := buildInstructionBundle(sourcePaths)
	if err != nil {
		return AssetResult{}, err
	}

	existing := []byte{}
	if current, readErr := os.ReadFile(destinationPath); readErr == nil {
		existing = current
	} else if !errors.Is(readErr, os.ErrNotExist) {
		return AssetResult{}, clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", destinationPath), readErr)
	}

	nextContent := []byte(InsertManagedBlock(string(existing), managedContent))
	action, err := writeFile(destinationPath, nextContent, SyncOptions{Force: true})
	if err != nil {
		return AssetResult{}, err
	}

	return AssetResult{AssetType: "instruction-file", Destination: destinationPath, Action: action}, nil
}

func buildInstructionBundle(sourcePaths []string) (string, error) {
	sorted := append([]string(nil), sourcePaths...)
	sort.Strings(sorted)
	sections := make([]string, 0, len(sorted))
	for _, sourcePath := range sorted {
		content, err := os.ReadFile(sourcePath)
		if err != nil {
			return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read instruction %s", sourcePath), err)
		}
		sections = append(sections, "## "+filepath.Base(sourcePath)+"\n\n"+strings.TrimSpace(string(content)))
	}

	return strings.Join(sections, "\n\n"), nil
}

func writeFile(path string, content []byte, options SyncOptions) (string, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("create directory for %s", path), err)
	}

	existing, err := os.ReadFile(path)
	if err == nil {
		if bytes.Equal(existing, content) {
			return "skipped", nil
		}
		if !options.Force {
			return "skipped-conflict", nil
		}
		if backupErr := os.WriteFile(path+".bak", existing, 0o644); backupErr != nil {
			return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("backup %s", path), backupErr)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("read %s", path), err)
	}

	if writeErr := os.WriteFile(path, content, 0o644); writeErr != nil {
		return "", clierrors.Wrap(clierrors.KindConfig, fmt.Sprintf("write %s", path), writeErr)
	}
	if err == nil {
		return "updated", nil
	}

	return "created", nil
}

func copyStream(dst io.Writer, src io.Reader) error {
	_, err := io.Copy(dst, src)
	return err
}
