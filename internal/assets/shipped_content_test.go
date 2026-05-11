package assets

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestShippedAssetsCoverRequiredPromptGuidance(t *testing.T) {
	t.Parallel()

	root := repoRoot(t)

	promptChecks := map[string][]string{
		filepath.Join(root, ".github", "PULL_REQUEST_TEMPLATE.md"): {
			"## Approved Understanding",
			"## Tests",
			"## Code Review",
			"## Documentation",
			"## Risks And Rollback",
		},
		filepath.Join(root, "prompts", "batman.agent.md"): {
			"python3 -m mempalace hook run --hook stop --harness {{MEMPALACE_HARNESS}}",
			"python3 -m mempalace hook run --hook precompact --harness {{MEMPALACE_HARNESS}}",
			"coding-cli/.github/PULL_REQUEST_TEMPLATE.md",
			"why each one would answer the user's question instead of merely naming it",
			"Distinguish similarly named or adjacent processes",
			"what each likely-to-change component is used for",
			"where processing/execution happens today",
		},
		filepath.Join(root, "prompts", "BASE_SYSTEM_PROMPT.instructions.md"): {
			"coding-cli/.github/PULL_REQUEST_TEMPLATE.md",
			"answer why the cited evidence matters",
			"how similar processes differ",
			"what changing components are used for",
			"where execution happens today",
		},
		filepath.Join(root, "skills", "freighthero-projects", "SKILL.md"): {
			"coding-cli/.github/PULL_REQUEST_TEMPLATE.md",
			"Preserve headings",
			"fill every section with concrete details",
		},
		filepath.Join(root, "skills", "batman-understanding", "SKILL.md"): {
			"## Current Behavior",
			"### Why This Evidence Answers The Question",
			"### Process Distinctions And Terminology",
			"### Components Likely To Change And Why They Exist",
			"### Execution Locations",
		},
	}

	for path, snippets := range promptChecks {
		content := readTextFile(t, path)
		for _, snippet := range snippets {
			if !strings.Contains(content, snippet) {
				t.Fatalf("%s missing snippet %q", path, snippet)
			}
		}
	}
}

func repoRoot(t *testing.T) string {
	t.Helper()

	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}

	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", ".."))
}

func readTextFile(t *testing.T, path string) string {
	t.Helper()

	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile %s returned error: %v", path, err)
	}

	return string(content)
}
