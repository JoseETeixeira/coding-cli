import { promises as fs } from "node:fs";
import path from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const INDEX_DIR = path.resolve(
  process.env.CODEBASE_INDEX_DIR || ".cocoindex/codebase-index",
);
const INDEX_CACHE_TTL_MS = Number(process.env.CODEBASE_INDEX_CACHE_TTL_MS || 60000);

type SearchIndexEntry = {
  id: string;
  project: string;
  filePath: string;
  lineStart: number;
  lineEnd: number;
  chunkStart: number;
  chunkEnd: number;
  content: string;
};

type SearchResult = SearchIndexEntry & {
  score: number;
};

let cachedIndex: SearchIndexEntry[] | undefined;
let cachedIndexLoadedAt = 0;

async function listJsonFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        return listJsonFiles(entryPath);
      }
      if (entry.isFile() && entry.name.endsWith(".json")) {
        return [entryPath];
      }
      return [];
    }),
  );
  return files.flat();
}

function isSearchIndexEntry(value: unknown): value is SearchIndexEntry {
  if (!value || typeof value !== "object") {
    return false;
  }
  const entry = value as Record<string, unknown>;
  return (
    typeof entry.id === "string" &&
    typeof entry.project === "string" &&
    typeof entry.filePath === "string" &&
    typeof entry.lineStart === "number" &&
    typeof entry.lineEnd === "number" &&
    typeof entry.chunkStart === "number" &&
    typeof entry.chunkEnd === "number" &&
    typeof entry.content === "string"
  );
}

async function loadIndex(): Promise<SearchIndexEntry[]> {
  const now = Date.now();
  if (cachedIndex && now - cachedIndexLoadedAt < INDEX_CACHE_TTL_MS) {
    return cachedIndex;
  }

  const files = await listJsonFiles(INDEX_DIR);
  const entries = await Promise.all(
    files.map(async (file) => {
      const raw = await fs.readFile(file, "utf8");
      const parsed: unknown = JSON.parse(raw);
      return isSearchIndexEntry(parsed) ? parsed : undefined;
    }),
  );

  cachedIndex = entries.filter((entry): entry is SearchIndexEntry => Boolean(entry));
  cachedIndexLoadedAt = now;
  return cachedIndex;
}

function tokenize(value: string): string[] {
  return Array.from(
    new Set(value.toLowerCase().match(/[a-z0-9_.$/-]+/g) ?? []),
  ).filter((token) => token.length > 1);
}

function countOccurrences(haystack: string, needle: string): number {
  let count = 0;
  let offset = haystack.indexOf(needle);
  while (offset !== -1) {
    count += 1;
    offset = haystack.indexOf(needle, offset + needle.length);
  }
  return count;
}

function scoreEntry(entry: SearchIndexEntry, query: string, tokens: string[]): number {
  const normalizedQuery = query.toLowerCase().trim();
  const normalizedPath = entry.filePath.toLowerCase();
  const normalizedContent = entry.content.toLowerCase();
  let score = 0;

  if (normalizedPath.includes(normalizedQuery)) {
    score += 40;
  }
  if (normalizedContent.includes(normalizedQuery)) {
    score += 30;
  }

  for (const token of tokens) {
    if (normalizedPath.includes(token)) {
      score += 8;
    }
    score += Math.min(countOccurrences(normalizedContent, token), 8);
  }

  return score;
}

async function searchIndex(
  query: string,
  limit: number,
  fileFilter?: string,
): Promise<SearchResult[]> {
  const index = await loadIndex();
  const tokens = tokenize(query);
  const normalizedFilter = fileFilter?.toLowerCase();

  return index
    .filter((entry) =>
      normalizedFilter ? entry.filePath.toLowerCase().includes(normalizedFilter) : true,
    )
    .map((entry) => ({ ...entry, score: scoreEntry(entry, query, tokens) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.filePath.localeCompare(right.filePath))
    .slice(0, limit);
}

function formatResults(results: SearchResult[]): string {
  return results
    .map(
      (result, index) =>
        `--- Result ${index + 1} (score: ${result.score.toFixed(1)}) ---\nFile: ${result.filePath} (lines ${result.lineStart}-${result.lineEnd})\n\n${result.content}`,
    )
    .join("\n\n");
}

function formatContext(results: SearchResult[]): string {
  return results
    .map(
      (result, index) =>
        `--- File ${index + 1}: ${result.filePath} (lines ${result.lineStart}-${result.lineEnd}) ---\n${result.content}`,
    )
    .join("\n\n");
}

type ReconstructedFile = {
  filePath: string;
  project: string;
  lineStart: number;
  lineEnd: number;
  content: string;
  topScore: number;
  chunkCount: number;
};

async function reconstructTopFiles(
  query: string,
  fileCount: number,
): Promise<ReconstructedFile[]> {
  const index = await loadIndex();
  const tokens = tokenize(query);

  const fileBestScore = new Map<string, number>();
  for (const entry of index) {
    const score = scoreEntry(entry, query, tokens);
    if (score <= 0) {
      continue;
    }
    const prev = fileBestScore.get(entry.filePath) ?? 0;
    if (score > prev) {
      fileBestScore.set(entry.filePath, score);
    }
  }

  const topFiles = [...fileBestScore.entries()]
    .sort(
      ([leftPath, leftScore], [rightPath, rightScore]) =>
        rightScore - leftScore || leftPath.localeCompare(rightPath),
    )
    .slice(0, fileCount);

  return topFiles.map(([filePath, topScore]) => {
    const fileChunks = index
      .filter((entry) => entry.filePath === filePath)
      .sort((left, right) => left.chunkStart - right.chunkStart);

    let merged = "";
    let lastEnd = -1;
    let project = "";
    let lineStart = Number.POSITIVE_INFINITY;
    let lineEnd = 0;

    for (const chunk of fileChunks) {
      project = chunk.project;
      lineStart = Math.min(lineStart, chunk.lineStart);
      lineEnd = Math.max(lineEnd, chunk.lineEnd);

      if (lastEnd < 0) {
        merged = chunk.content;
        lastEnd = chunk.chunkEnd;
        continue;
      }

      if (chunk.chunkStart >= lastEnd) {
        if (chunk.chunkStart > lastEnd) {
          merged += `\n... [${chunk.chunkStart - lastEnd} chars elided] ...\n`;
        }
        merged += chunk.content;
        lastEnd = chunk.chunkEnd;
        continue;
      }

      const overlapChars = lastEnd - chunk.chunkStart;
      if (overlapChars < chunk.content.length) {
        merged += chunk.content.slice(overlapChars);
      }
      lastEnd = chunk.chunkEnd;
    }

    return {
      filePath,
      project,
      lineStart: lineStart === Number.POSITIVE_INFINITY ? 0 : lineStart,
      lineEnd,
      content: merged,
      topScore,
      chunkCount: fileChunks.length,
    };
  });
}

function formatReconstructedFiles(files: ReconstructedFile[]): string {
  return files
    .map(
      (file, index) =>
        `--- File ${index + 1}: ${file.filePath} (project ${file.project}, lines ${file.lineStart}-${file.lineEnd}, ${file.chunkCount} chunk(s) merged, top score ${file.topScore.toFixed(1)}) ---\n${file.content}`,
    )
    .join("\n\n");
}

const server = new McpServer({
  name: "freighthero-codebase",
  version: "1.0.0",
});

server.tool(
  "search_codebase",
  "Search the local CocoIndex codebase index. Returns relevant code snippets with file paths and line numbers.",
  {
    query: z.string().describe("Natural language search query, symbol, error text, or code snippet"),
    limit: z.number().min(1).max(20).default(10).describe("Max results to return"),
    file_filter: z
      .string()
      .optional()
      .describe("Optional path substring filter, such as 'backend' or 'frontend'"),
  },
  async ({ query, limit, file_filter }) => {
    try {
      const results = await searchIndex(query, limit ?? 10, file_filter);
      return {
        content: [
          {
            type: "text" as const,
            text:
              results.length > 0
                ? `Found ${results.length} results from ${INDEX_DIR}:\n\n${formatResults(results)}`
                : `No results found in ${INDEX_DIR} for this query.`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error searching codebase: ${error}` }],
        isError: true,
      };
    }
  },
);

server.tool(
  "analyze_error",
  "Retrieve local code context for an error message or stack trace so the calling agent can analyze it.",
  {
    error_message: z.string().describe("The error message or description"),
    traceback: z.string().optional().describe("Optional stack trace or traceback"),
    context: z.string().optional().describe("Optional additional context"),
  },
  async ({ error_message, traceback, context }) => {
    try {
      const queryText = [error_message, traceback, context].filter(Boolean).join("\n\n");
      const results = await searchIndex(queryText, 10);
      return {
        content: [
          {
            type: "text" as const,
            text:
              results.length > 0
                ? `Relevant code context for agent-side error analysis:\n\n${formatContext(results)}`
                : "No matching code context found for this error.",
          },
        ],
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error retrieving context: ${error}` }],
        isError: true,
      };
    }
  },
);

server.tool(
  "indexing_status",
  "Get the current status of the local CocoIndex chunk index.",
  {},
  async () => {
    try {
      const index = await loadIndex();
      const projectCounts = index.reduce<Record<string, number>>((counts, entry) => {
        counts[entry.project] = (counts[entry.project] ?? 0) + 1;
        return counts;
      }, {});
      const projectSummary = Object.entries(projectCounts)
        .sort(([leftProject], [rightProject]) => leftProject.localeCompare(rightProject))
        .map(([project, count]) => `${project}: ${count}`)
        .join("\n");

      return {
        content: [
          {
            type: "text" as const,
            text: `Index directory: ${INDEX_DIR}\nChunks: ${index.length}\nProjects:\n${projectSummary || "none"}`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error getting index status: ${error}` }],
        isError: true,
      };
    }
  },
);

server.tool(
  "explain_code",
  "Reconstruct the FULL top-matching file(s) from the local CocoIndex index for a symbol, function, class, or pattern. Returns each top file as a single merged blob (all chunks reassembled in order with overlaps deduped), so the calling agent can read the complete implementation in context. Use this when you want to UNDERSTAND a symbol end-to-end; use search_codebase when you just want to LOCATE matches across the codebase.",
  {
    query: z.string().describe("Function name, class name, or description of the code to find"),
    detail_level: z
      .enum(["brief", "detailed"])
      .default("detailed")
      .describe("brief = top 1 file reconstructed; detailed = top 3 files reconstructed"),
  },
  async ({ query, detail_level }) => {
    try {
      const fileCount = detail_level === "brief" ? 1 : 3;
      const files = await reconstructTopFiles(query, fileCount);
      return {
        content: [
          {
            type: "text" as const,
            text:
              files.length > 0
                ? `Top-matching ${files.length === 1 ? "file" : "files"} reconstructed in full from the local CocoIndex index. Use to explain the queried symbol/pattern in context:\n\n${formatReconstructedFiles(files)}`
                : "No matching code found in the local CocoIndex index.",
          },
        ],
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error retrieving code context: ${error}` }],
        isError: true,
      };
    }
  },
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("FreightHero MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
