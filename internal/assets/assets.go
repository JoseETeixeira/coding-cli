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
	vscodeBatmanFrontmatterTools = "tools: [vscode, execute, read, agent, edit, search, web, 'github/*', 'mempalace/*', browser, 'pylance-mcp-server/*', 'freighthero-codebase/*', 'repowise/*', todo]"

	// Note: Claude Code installs intentionally OMIT the frontmatter tools list. Per Claude Code agent
	// semantics, omitting `tools:` means the agent inherits every tool available to the session — including
	// any claude.ai cloud connectors (Notion, Gmail, Calendar, Drive) and any future MCP server the user
	// adds. Maintaining an explicit whitelist would silently shadow new servers and is the root cause of
	// the "MCP connected but tools not in inventory" symptom. See applyClaudeCodeTransforms below.

	// claudeCodeSpecSyncBlock is the Claude-Code-only section appended to batman.agent.md at install time.
	// It instructs the agent to keep the workspace-root CLAUDE.md synchronized with the active Batman spec
	// so future Claude Code sessions pick up the in-flight spec context automatically. It MUST NOT be
	// installed for other harnesses (VS Code, Codex, Batman) — those hosts use different session-bootstrap files.
	claudeCodeSpecSyncBlock = `
## CRITICAL: Spec-Driven CLAUDE.md Synchronization (Claude Code only)

When the user is working on a Batman spec under ` + "`" + `.batman/<task_slug>/` + "`" + `, you MUST keep the workspace-root ` + "`" + `CLAUDE.md` + "`" + ` in sync so future Claude Code sessions pick up the active spec context.

### Trigger points

Create or update the workspace ` + "`" + `CLAUDE.md` + "`" + ` at these moments:

1. Spec creation — immediately after writing the first draft of ` + "`" + `.batman/<task_slug>/steering/understanding.md` + "`" + ` in Phase 1.
2. After every planning-phase approval — Understanding, Requirements, Design, Task Planning.
3. On entering Phase 5 (Implementation).
4. On spec completion — clear the managed block after the spec PR is merged or the spec is abandoned.

### Target file

Detect the workspace root portably — do not hardcode an absolute path:

- Walk up from the active file until you reach a directory containing two or more of ` + "`" + `ai_watchtower/` + "`" + `, ` + "`" + `backend/` + "`" + `, ` + "`" + `frontend/` + "`" + `, ` + "`" + `robin-error-dashboard/` + "`" + `, ` + "`" + `coding-cli/` + "`" + `, ` + "`" + `freighthero-mcp/` + "`" + ` as direct children. Treat that directory as the workspace root.
- If the workspace root already contains a ` + "`" + `CLAUDE.md` + "`" + `, update it.
- Otherwise, create ` + "`" + `<workspace-root>/CLAUDE.md` + "`" + `.
- Never modify content outside the managed block.

### Managed block format

Wrap the spec snapshot in markers so updates are idempotent:

` + "```" + `markdown
<!-- batman:spec:start -->
## Active Batman Spec(s)

- **Task slug**: <task_slug>
- **Current phase**: <Understanding | Requirements | Design | Task Planning | Implementation | Tests | Code Review | Documentation>
- **Steering**: ` + "`" + `.batman/<task_slug>/steering/understanding.md` + "`" + ` (status: <draft | approved>)
- **Requirements**: ` + "`" + `.batman/<task_slug>/spec/requirements.md` + "`" + ` (status: <not started | draft | approved>)
- **Design**: ` + "`" + `.batman/<task_slug>/spec/design.md` + "`" + ` (status: <not started | draft | approved>)
- **Tasks**: ` + "`" + `.batman/<task_slug>/spec/tasks.md` + "`" + ` (status: <not started | draft | approved>)
- **Last updated**: <YYYY-MM-DD>

Read the steering ` + "`" + `understanding.md` + "`" + ` first on session start. Treat each artifact as the source of truth for its phase.
<!-- batman:spec:end -->
` + "```" + `

### Rules

- Idempotent: re-running the sync replaces the prior block in place; never append duplicate blocks.
- Never alter content outside the ` + "`" + `<!-- batman:spec:start -->` + "`" + ` / ` + "`" + `<!-- batman:spec:end -->` + "`" + ` markers.
- Multiple in-flight specs: list each as its own subsection inside the managed block, with its own phase and approval rows.
- Completion or abandonment: remove the entire managed block including markers.
- This sync is Claude-Code-specific. Do not run it for VS Code, Codex, or other hosts.
`
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
// It replaces VS Code Batman tool references with Claude Code native equivalents, removes the
// frontmatter tools list entirely (so the agent inherits every session-available tool, including
// claude.ai cloud connectors), strips the hooks block (not supported in Claude Code agent files),
// injects the model field so Claude Code sessions use the appropriate model tier, and appends
// the Claude-Code-only spec-sync instructions (workspace CLAUDE.md kept in sync with active
// Batman spec).
func applyClaudeCodeTransforms(content string) string {
	// Remove the frontmatter hooks block — Claude Code agent files don't support in-file hooks.
	content = frontmatterHooksRe.ReplaceAllString(content, "")

	// Replace VS Code Batman tool invocation syntax with Claude Code native tools.
	content = strings.ReplaceAll(content, "#tool:vscode/askQuestions", "AskUserQuestion")
	content = strings.ReplaceAll(content, "#tool:agent/runSubagent", "Agent")

	// Drop the frontmatter tools list entirely. Omitting `tools:` makes the Claude Code agent inherit
	// every tool available to the session — including any claude.ai cloud connectors (Notion, Gmail,
	// Calendar, Drive) and future MCP servers added by the user. Keeping an explicit whitelist would
	// silently shadow those tools.
	content = strings.Replace(content, vscodeBatmanFrontmatterTools+"\n", "", 1)

	// Inject the model field after the name line — Claude Code only, not VS Code / Copilot.
	content = strings.ReplaceAll(content, "name: \"Batman Agent\"\n", "name: \"Batman Agent\"\nmodel: \"opus\"\n")

	// Append the Claude-Code-only spec-sync section. Skip if it is already present so re-runs stay idempotent.
	if !strings.Contains(content, "## CRITICAL: Spec-Driven CLAUDE.md Synchronization") {
		content = strings.TrimRight(content, "\n") + "\n" + claudeCodeSpecSyncBlock
	}

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
