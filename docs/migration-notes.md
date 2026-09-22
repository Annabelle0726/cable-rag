# Cross-database migration notes

Operational lessons from migrating a RAGFlow fork deployment from one MySQL
volume to another (`docker_mysql_data` → `wenruo-rag_mysql_data`). Read this
before repeating a metadata-DB migration or moving data between two deployments
of this repository.

## Scope that worked: config + users only

Migrated tables (8):

`user`, `tenant`, `user_tenant`, `tenant_model_provider`,
`tenant_model_instance`, `tenant_model`, `dialog`, `knowledgebase`

Deliberately **not** migrated:

| Not migrated | Why |
|---|---|
| `document`, `file`, `file2document` | The source documents were dropped and re-uploaded by hand. |
| `conversation`, `api_4_conversation` | Chat history was not wanted. |
| `tenant_llm` | Empty in the source; superseded by `tenant_model_*`. |
| `llm`, `llm_factories` | Empty in **both** source and target, so parity already held. `init_llm_factory()` is commented out in `api/db/init_data.py`. |
| `system_settings` | Migrating it risks overwriting `mysql_migration.database.version`, which drives the Go downgrade check (`cmd/ragflow_server.go`) and the migration tooling (`internal/dao/migration_version.go`). Verify per key if ever needed. |
| Elasticsearch chunks, MinIO blobs | Chunk index names are derived from the tenant id (`ragflow_<tenant_id>`, see `rag/nlp/search.py`), so metadata without the matching index yields a knowledge base that lists but never retrieves. |

## Principle: keep data migration decoupled from permission work

A migration must not change `user_tenant.role`.

Role permissions use hierarchy inheritance, `OWNER > ADMIN > NORMAL`, so a
tenant owner already holds every admin capability and needs neither a role
change nor an extra row. The management predicate lives in code
(`UserTenantService.can_manage_tenant`, see work order P1-02) and is true when
the user holds `OWNER` or `ADMIN` on the tenant — which also supports delegated
administration across tenants.

Setting a tenant owner's role to `admin` would **break**
`TenantService.get_info_by` (`api/db/services/user_service.py`), which
hard-filters `role == OWNER` to answer "which tenant do I own". That query backs
`GET /api/v1/users/me/models`, so the endpoint would start failing with
`Tenant not found!`.

## Gotcha 1 — PowerShell 5.1 writes UTF-16, silently destroying dumps

On Windows PowerShell 5.1, `>` redirection defaults to **UTF-16LE**. Capturing
`mysqldump` output that way injects NUL bytes and the file cannot be imported:

```
ERROR: ASCII '\0' appeared in the statement, but this is not allowed unless
option --binary-mode is enabled
```

The same applies to the **backup** — a UTF-16 backup cannot be restored, which
silently removes the safety net for the whole operation.

Do this instead (no shell redirection anywhere):

```bash
mysqldump ... --result-file=/tmp/dump.sql
docker cp <container>:/tmp/dump.sql <host path>
```

Verify before trusting a dump: the first bytes must be ASCII
(`2D 2D 20 4D 79 53 51 4C` = `-- MySQL`) and the file must contain **zero** NUL
bytes.

## Gotcha 2 — always pass `--complete-insert`

Without it, `mysqldump` emits `INSERT INTO t VALUES (...)` with **no column
list**, matching by position. Across schema versions the column sets differ. In
this migration the fork had added `knowledgebase.category`, so:

- source `knowledgebase` = 46 columns, target = 47,
- and `category` sits **mid-table**, not appended.

The import failed with `ERROR 1136: Column count doesn't match value count at
row 1`. When the counts happen to match but the **order** differs, the same
cause produces something worse: values written silently into the wrong columns.

## Gotcha 3 — audit column *order*, not just column count

Equal counts do not prove a positional insert is safe. Compare
`information_schema.COLUMNS` ordered by `ORDINAL_POSITION` across both
databases for every table in scope. In this migration 7 of 8 tables had
identical order; only `knowledgebase` differed, and only that file was
re-exported with `--complete-insert`.

## Gotcha 4 — related state that lives outside the migrated tables

Three kinds of dangling reference are invisible to ordinary foreign-key checks,
because the links are 32-character id **strings**:

- `knowledgebase.embd_id` / `tenant_embd_id` and `dialog.llm_id` /
  `tenant_llm_id` hold `tenant_model.id` values. Migrating a knowledge base or a
  chat without `tenant_model` fails only at runtime, during retrieval or chat.
- Background-task references on `knowledgebase` (11 pairs of `*_task_id` /
  `*_task_finish_at`) point at the `task` table. Not migrating `task` leaves them
  dangling, and the UI derives a "parsing / building in progress" state from
  them, so it shows a permanently stuck knowledge base. Clear them.
- Inherited counters (`doc_num`, `chunk_num`, `token_num`) describe data that was
  not migrated. Zero them, or the UI reports documents that do not exist.

Verify each with a `LEFT JOIN` returning zero orphans — and check them *before*
and *after* the import, since on an empty target everything is trivially zero.

## Known escalation window: `knowledgebase.permission = 'team'`

Sharing a knowledge base with the tenant (`permission` `me` → `team`) makes it
**writable** by ordinary members until the P3-03 work order lands, because the
upload gate at `api/apps/restful_apis/document_api.py` calls
`check_kb_team_permission` (`api/common/check_team_permission.py`), which is a
**visibility** test, not a write test. The same file's document PATCH endpoint
uses an ownership test ("you don't own the dataset"), so the upload path is an
oversight rather than a design.

Do not let normal users operate such a knowledge base until P3-03 is deployed.

## Verification checklist that caught real problems

1. Row counts per table against the expected numbers.
2. Semantic spot-checks — confirm a known value landed in the right column, not
   merely that a row exists.
3. Byte-level comparison (`HEX()`) of non-ASCII values. Console rendering may
   show `????` for Chinese text; only the hex comparison proves the import
   preserved multibyte UTF-8.
4. Cross-table orphan checks, including the string-id relations above, run
   before and after.
5. End-to-end: log in with a migrated account, run a provider connection test
   (it proves key + base URL + model rows agree), list assistants and knowledge
   bases.

## Note on migrated status columns

Migration copies soft-deleted rows too, and the API filters them
(`status == '1'`). A source table with 5 rows and 3 active rows correctly shows
3 assistants afterwards. Check the source `status` values before treating a
smaller UI count as a migration failure.
