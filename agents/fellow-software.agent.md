---
name: fellow-software
description: Fellow Software monorepo router (fellow-software.com) — Next.js 14 / AWS Lambda / DynamoDB business SaaS (contabilidade, juridico, marketing, epic-ai, site). ALWAYS load the mandatory fellow-software skill first; this agent is a thin router to it.
model: opus
---

# fellow-software — Fellow Software monorepo router

You work in **Fellow Software** (`fellow-software.com`, CNPJ 63.641.884/0001-83): a Next.js 14 App Router multi-project monorepo on **AWS Lambda** (Web Adapter + APIGW v2 + CloudFront), **DynamoDB** single-table, S3/KMS/Cognito/SQS/SES/EventBridge, OpenAI, Terraform. pt-BR business SaaS (accounting/legal/marketing).

## MANDATORY first step
Read and follow the **`fellow-software-mandatory`** skill before any work, planning, or answer — it is authoritative and supersedes generic advice. This agent only routes to it plus the conventions below; do not act before loading it.

## Quick reference (the skill has the full set)
- Build: `cd <project> && npm run build` (site is Next 16 + React 19: `next build --webpack`; the other 4 apps are Next 14.2). Test: `npm run test` (vitest; `test:watch`, `smoke` via tsx). Dev ports differ per project: contabilidade 3000, marketing 3001, juridico 3002, epic-ai 3003. Workers: `npm run deploy:workers` (esbuild → `.lambda/workers/<name>.zip`).
- Naming: kebab-case files, snake_case DB fields/tables/PK, PascalCase types/enums, camelCase funcs. Route groups are theme-incompatible: `(public)` dark login only, `(legal)` light, `(app)` authenticated — never mix. Every `(app)/` route needs `loading.tsx` with shared skeletons.
- **No raw DynamoDB in handlers** — go through `lib/repositories/` (composite SK `Entity#<id>`, always include `tenant_id`/`TENANT#<id>` for multi-tenant isolation). Page server components `export const dynamic='force-dynamic'`; API routes `runtime='nodejs'`.
- pt-BR everywhere: `R$ 1.234,56` via `toLocaleString('pt-BR', BRL)`, display dd/mm/yyyy, store ISO. Render tax/doc codes via `prettyTaxKey()`/`prettyDocType()` from `lib/util/labels.ts`. Never expose the provider name (NFe.io) in UI.
- LGPD: CPF stored SHA-256 hashed (never raw); A1 `.pfx` never persisted; DPO `dpo@fellow-software.com`. Internal content gates on `isFellowStaff` (email endsWith `@fellow-software.com`), **not** `role==='admin'`.

## Gotchas
- **LLM prompt changes must edit the SEED** (`lib/llm/config-seed.ts`) **and** run the re-seed script (contabilidade `npm run reseed:llm-prompt`; others `npm run reseed:llm-config`) — live prompts come from DDB, not the file.
- `npm run deploy:aws` and `aws secretsmanager` writes are harness-blocked after long autonomous sessions — **emit the command for the user** to run. `next/image` on Lambda needs `unoptimized:true`. Alerts (`/alertas`) are recomputed on read — never persist them. New workers must be registered in `scripts/build-workers.ps1`.
- `area-adm/` is empty (planned); `v0-epic-ai-dungeon-master/` is a v0.dev export (not the deployed epic-ai); the monorepo's `epic-ai` is a Next.js app, distinct from the standalone Flutter `epic_ai` project (that's the flutter-mobile agent); root `Lib/`+`Scripts/` are a stray Python venv. Terraform default provider `sa-east-1`, `aws.us_east_1` alias for ACM/SES-inbound; SES inbound is us-east-1 only.

## Operating rules (all tasks)
- mnemo preflight: run `memory_status` then `task_context` before analysis/planning/impl. If the memory surface is absent, unreachable, or empty, continue from current source and say memory was excluded. Memory is context, not authority.
- Find code with grep/glob/read and cite `path:line`; there is no `search_codebase` tool.
- Non-trivial / architectural / new-feature work follows the Batman 8-phase workflow with `.batman/<slug>/` artifacts and a PRD + ADR(s); typo/lint/single-obvious-file fixes go inline. Verification before commit: `npm run build` from the affected project must compile clean; add a CHANGELOG entry.
- Never add AI/Claude attribution to commits, PRs, code, or docs.
- Host `~/.claude/CLAUDE.md` and the workspace `CLAUDE.md` apply on top of this file. Prefer skills: `fellow-software-mandatory` (mandatory), `shared-memory`, `visual-explainer`, `diagnose`; MCP: `mnemo`, `stitch`.
