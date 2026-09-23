# Wenruo-RAG (文若 RAG) Instructions

Use this file as the local operating guide for the current codebase.
Prefer the current code and explicit architecture decisions in this file
and the current CLAUDE.md over older conventions or remembered project shape.

## Core Stance
- Treat legacy code as liability, not as a compatibility target.
- Prefer deletion over shims, deprecated branches, wrapper APIs, and dual-track migration notes.
- If old and new implementations coexist, converge to one path unless an external contract forces compatibility.
- Remove dead tests, commented-out code, stale docs, and "move later" notes instead of preserving them.
- Reduce public surface area when a helper can be made private or internal.
- Keep refactors centered on the owning abstraction, not on adjacent compatibility layers.

## Current Architecture Decisions (CRITICAL)
- **Active Backend**: `API_PROXY_SCHEME=python` is frozen as the sole active and supported backend path.
- **Python Authoritative**: Python (`api/`) is the single source of truth for current permission, RBAC, and tenant refactoring.
- **Go Backend Deprecation**: Go (`internal/`) permission and authentication paths are INACTIVE for current features.
- **No Dual Sync**: Do NOT attempt to revive or edit Go backend code for symmetry.
- **Error Response Standard**: Permission denials MUST follow RAGFlow standard `HTTP 200` with `code=108` (`get_error_data_result`) for seamless frontend Toast and error handling.
- **Frontend HTTP Payload Contract**: `umi-request` calls MUST wrap payload bodies in `{ data: body }` (e.g., `request.put(url, { data: { role } })`), otherwise parameters fail validation with `code=101`.

## Tenant & RBAC Model (CRITICAL)

The tenant role hierarchy is strictly enforced as:

**OWNER > ADMIN > NORMAL**

### Role Definitions
- **OWNER**: Tenant creator/owner. Full tenant authority, manages administrators and overall tenant settings.
- **ADMIN**: Granted tenant-management permissions by RBAC layer. Manages members and assigned configurations; cannot override OWNER.
- **NORMAL**: Standard tenant user. Cannot manage members, tenant-level providers, or system settings.

### Tenant Context & Multi-Tenancy Architecture
- **Active Tenant Context**: NEVER assume `user.id == tenant_id` for non-owner users. All workspace operations MUST be scoped to the `active_tenant_id` resolved via `TenantService.resolve_config_tenant_id` or active session/request context.
- **Joined Tenant Access**: NORMAL members without personal tenants inherit read-only access to their joined tenant's shared model configurations and knowledge bases (`resolve_config_tenant_id`).
- **Backend Enforcement**: Frontend UI/component hiding is NEVER an authorization boundary. Sensitive endpoints MUST enforce `@require_tenant_admin`.
- **Visibility vs Ownership**: `visibility` (e.g. `me` vs `team`) DOES NOT equal ownership.
- **Access vs Management**: Read/query permission DOES NOT imply permission to modify, delete, transfer, or manage.
- **Decoupled Roles & Attributes**: Tenant roles (`role` -> authorization) and organizational attributes (`department_id`, `title` -> profile) MUST be handled via distinct endpoints (`PUT /role` vs `PUT /profile`).
- **Private Visibility Semantics**: `private` (`permission='me'`) knowledge bases are visible to the **Creator + Tenant Owner/Admin** for enterprise governance and auditing.

## Permission Refactor Progress Base (P1 ~ P5)

Preserve and build upon these established milestones:

### Completed Milestones
- **P1-01**: Disabled public registration (`REGISTER_ENABLED=0`).
- **P1-02**: Role hierarchy definition & `can_manage_tenant` helper.
- **P1-03**: Backend decorator `@require_tenant_admin`.
- **P1-04**: System account `admin@ragflow.io` hardened, `ADMIN_DEFAULT_PASSWORD` neutralized in `docker/.env`, and test Normal user `0realannabelle0@gmail.com` initialized for E2E validation.
- **P1-05**: User API `/users/me` returning active `role` and resolved tenant scope.
- **P3-02**: Tenant member role update API (`PUT /tenants/<id>/users/<user_id>/role`), umi-request `{ data }` payload wrapper bug fix, and transport-layer service unit tests.
- **P4-00a/b/c**: Markdown & LaTeX rendering pipeline overhaul (fixed `\[...\]` block math line breaks, fixed `\(a\)` letter-ending inline math, added real-pipeline Sanitizer & KaTeX tests, Jest ESM transformer fixes).
- **P4-01**: Provider API Key output masking.
- **P4-02**: Comprehensive RBAC endpoint guards (`@require_tenant_admin` on 15 sensitive write/execute provider, model, and langfuse APIs; 8 read endpoints remain open).
- **P4-03a**: Standardized frontend `RoleTag` component with semantic tokens (`src/tailwind.css`), i18n support, and UI mounting.
- **P4-03b**: Frontend Model Settings read-only mode for NORMAL users (disabled controls, hidden action buttons, admin managed notice banner).
- **P4-05**: Multi-tenant model config resolution (`TenantService.resolve_config_tenant_id`) enabling NORMAL users to seamlessly read joined tenant model configurations without 102 Tenant errors.
- **P5-00**: Department & Title architecture (`department` table + `user_tenant.department_id`/`title` append-only columns), department CRUD API with non-empty member guards (`code=102`), profile update API (`PUT /profile`), and flat UI department management.
- **P5-01**: Global Active Tenant Context Middleware & `/user-setting/team` workspace switcher refactor.
- **Data Source Module Cleanup**: Migrated shared data-source modules from deprecated `pages/user-setting/data-source/` to `src/components/data-source/`, fixing relative imports across 11 files and completely deleting the user-setting data-source page.

### Pending / Active Implementation
- **P3-03**: Knowledge-base 3-tier fine-grained authorization (`private`, `team`, `custom`), `knowledgebase_authorization` mapping table, `can_read_dataset` SQL list masking, strict `can_write_dataset` write/delete separation, and UI quick actions (pin/unpin, hide/show).
- **P2-01~07**: Tenant invitation & onboard workflow.
- **P3-01a/b**: Member removal and asset transfer/cleanup logic.
- **P4-04**: Owner-Tenant model configuration resolution for Assistant usage.

## Database Migration Rules (Peewee)
- **No Auto Schema Migration**: Peewee's `init_database_tables` skips existing tables without adding missing columns.
- **Adding Columns**: Any new model column MUST be appended via `alter_db_add_column(...)` at the end of `migrate_db()` in `api/db/db_models.py`.
- **Append-Only Migration**: Migration execution is strict append-only. NEVER delete, reorder, or modify existing `alter_db_*` calls.
- **Explicit Defaults & Nullability**: New columns MUST use explicit, conservative defaults or allow `NULL` (e.g. `department_id` nullable) so unassigned users/records are never incorrectly matched by authorization logic.

## Resource Ownership & Dataset Authorization (P3-03)
- **Decoupled Read vs Write Guards**: `can_read_dataset` (listing & vector retrieval) MUST be strictly decoupled from `can_write_dataset` (upload, parse, edit, delete). Users granted custom read/retrieval access MUST NOT inherit write or delete authority.
- **SQL-Level Dataset Masking**: Unpermitted datasets MUST be filtered out at the SQL query level in listing APIs. Never rely on frontend component hiding to conceal sensitive knowledge base metadata.
- **Dynamic Department Inheritance**: KB authorizations bound to `department_id` are dynamic—members joining or transferring into a department automatically inherit its assigned dataset retrieval access.

## Security & API Key Management
- **API Key Redaction**: API endpoints returning model instances MUST redact/mask `api_key` before output.
- **No Query Key Leaks**: Never pass or log raw credentials in GET query parameters.
- **Crypto Header Compatibility**: When encrypting stored credentials, preserve the `ENCRYPTED_MAGIC` (`b"RAGF"`) header bypass so unencrypted legacy database rows remain readable.
- **Registration Control**: Registration is strictly toggled via `REGISTER_ENABLED` in Python configuration.

## Resource Ownership & Assistant Scope
- **Asset Transfer Safety**: Member removal MUST explicitly transfer or reassign assets—never default private assets to shared visibility.
- **Assistant Model Resolution**: When a NORMAL user invokes a Tenant Assistant:
  1. Determine the effective tenant owning the Assistant.
  2. Resolve model/provider configuration using the **Owner Tenant** scope via `resolve_config_tenant_id`.
  3. Strict isolation: Normal users MUST NOT use this resolution path to access model configurations of unrelated tenants.

## Code Layout
- `api/`: Active Python API server, blueprints, services, and database layers.
- `rag/`: Core ingestion, retrieval, LLM integration, and graph RAG logic.
- `deepdoc/`: Document parsing and OCR pipeline.
- `agent/`: Workflow canvas, components, tools, and execution engine.
- `internal/`: Go application code (Legacy/Inactive for current tenant refactor).
- `web/`: React + TypeScript + Vite frontend. Follow `web/CLAUDE.md` for web-specific conventions.
- `docker/`: Compose files for dev and production deployments.

## Working Rules

Before editing:
1. Identify the owning code path in `api/` or `web/`.
2. Trace request flow: Route → Service → Database/Resource.
3. Verify **Active Tenant Context** (`active_tenant_id`) and **Resource Owner**.
4. Check explicit RBAC permission requirements (`OWNER`, `ADMIN`, or `NORMAL`).
5. Keep modifications local, surgical, and minimal. Do NOT modify Go files for symmetry.

After editing:
1. Inspect git diff for unintended changes.
2. Run targeted tests (Python `pytest` / `ruff`, Frontend `npm run lint` / `type-check`).
3. Verify both **ALLOWED** and **DENIED** authorization outcomes for permission edits.