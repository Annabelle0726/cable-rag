# P5-00 departments and P3-03 dataset authorization

Design for the two work orders that follow P5-01. Nothing here is implemented
yet: this is the specification to agree on before code.

Both changes share one idea: **authorization is decided for a subject set, not
for a whole workspace.** P5-00 gives members an organisational attribute; P3-03
lets a dataset grant visibility to those attributes.

## Part 1 — P5-00: departments and titles

### Schema

| Change | Detail |
|---|---|
| New table `department` | `id`, `tenant_id`, `name`, `parent_id` (nullable), `status`, audit columns. Created by `init_database_tables` because it subclasses `DataBaseModel`; no ALTER needed. |
| `user_tenant.department_id` | Nullable 32-char id, indexed. Appended through `alter_db_add_column` in `migrate_db()` (append-only). |
| `user_tenant.title` | Nullable 64-char free text. Same mechanism. |

Both new columns are nullable and default to NULL, which is the safe direction:
an unassigned member belongs to no department, so a department grant can never
capture a member who was never placed in one. No backfill is needed.

`parent_id` is stored now and rendered as a flat list first; the hierarchy is a
display concern and can arrive later without a second migration.

### Endpoints

| Method | Path | Who | Notes |
|---|---|---|---|
| `GET` | `/tenants/<tenant_id>/departments` | any member | The member list and the dataset dialog both need the names. |
| `POST` | `/tenants/<tenant_id>/departments` | admin | `{ name, parent_id? }` |
| `PUT` | `/tenants/<tenant_id>/departments/<department_id>` | admin | rename / re-parent |
| `DELETE` | `/tenants/<tenant_id>/departments/<department_id>` | admin | Refused while members are assigned, rather than silently unassigning them. |
| `POST` | `/tenants/<tenant_id>/users` | admin | Gains optional `department_id` / `title` for the invited member. |
| `PUT` | `/tenants/<tenant_id>/users/<user_id>/profile` | admin | Sets `department_id` / `title` alone. |

`role` and `department_id` deliberately live on separate endpoints: role is
authorization, department is an attribute, and an owner needs to change one
without touching the other. Both go through the same
`UserTenantService.can_manage_tenant` gate as P5-01's team endpoints, and
denials keep the platform shape (HTTP 200, body `code=108`).

`GET /tenants/<tenant_id>/users` gains `department_id`, `department_name` and
`title` in each row.

### UI

- **Invite / edit member**: a department select (from the department list) and a
  free-text title. The admin chooses both; nothing is defaulted.
- **Member list**: department and title columns, plus a department filter, in
  addition to the existing role control.
- **Department management**: a compact admin-only list editor (add, rename,
  delete) on the same page.

## Part 2 — P3-03: the dataset authorization matrix

### The three modes

```
(private)  creator and the workspace's managers
(team)     every member of the workspace            <- today's "team"
(custom)   the departments and the individuals named on the dataset
```

`knowledgebase.permission` keeps its column and gains the value `custom`, so no
DDL: it stays the *mode*, and the subject sets live in their own table. Overloading
`permission` with a serialized list would make the existing `me`/`team` checks
unreadable and unqueryable.

### Schema

New table `knowledgebase_authorization`:

| Column | Notes |
|---|---|
| `id`, `kb_id`, `tenant_id` | `tenant_id` is the dataset's owner tenant, so a listing can be scoped without a join. |
| `subject_type` | `department` or `user` |
| `subject_id` | `department.id` or `user.id` |
| `granted_by` | the admin who granted it |
| `status`, audit columns | soft delete, consistent with the rest of the schema |

Unique index on `(kb_id, subject_type, subject_id)`.

### The predicate

One function decides visibility, and both the listing query and the retrieval
path call it — the current split between "list" and "retrieve" is how a hidden
dataset can still be searched:

```
can_read_dataset(user, kb):
    if kb.tenant_id == user's active workspace and user can_manage_tenant: True
    if kb.created_by == user:                                                True
    if kb.permission == 'team':   user holds any membership on kb.tenant_id
    if kb.permission == 'custom':
        user's department_id on kb.tenant_id is among the granted departments
        or user is explicitly granted
    else (private): False
```

Two consequences worth stating explicitly:

1. **Managers see everything in their workspace**, including private datasets.
   That is what "admin manages the workspace" means, and it is why the private
   option is labelled "creator and managers" rather than "creator only".
2. **Visibility is not write permission.** The existing
   `check_kb_team_permission` (`api/common/check_team_permission.py`) is a
   visibility test that the upload and parse paths currently reuse as an
   authorization test. P3-03 splits them: `can_read_dataset` for reads,
   `can_write_dataset` for upload, parse, delete and configuration, with the
   latter requiring the creator or a workspace manager. Without that split, a
   custom-authorized member could also delete the dataset.

### Enforcement points

| Layer | What changes |
|---|---|
| `KnowledgebaseService.accessible` | Applies `can_read_dataset` as SQL (join on the caller's `user_tenant` row plus an `EXISTS` on the authorization table) so the listing never returns a hidden dataset. Hiding in the frontend only would leak the names. |
| Retrieval / chat | Uses the same predicate when resolving a dataset id, so a guessed id is refused rather than answered. |
| Upload / parse / delete | Moves to `can_write_dataset`. |

### Endpoints

| Method | Path | Who |
|---|---|---|
| `GET` | `/datasets/<dataset_id>/authorization` | creator or manager |
| `PUT` | `/datasets/<dataset_id>/authorization` | creator or manager |

`PUT` takes `{ permission, department_ids: [], user_ids: [] }` and replaces the
subject set inside one transaction; `permission != 'custom'` clears it. The
dataset read endpoints expose the mode to everyone and the subject lists only to
a creator or manager.

### UI

The visibility selector moves into the dataset settings panel and the `...`
quick menu, with the custom branch showing two multi-selects: departments, and
individuals labelled with their department (`张三（财务部）`). A member who is not
authorized never receives the card, so there is nothing to hide client-side.

## Decisions to confirm before implementation

1. **Private now means "creator and managers".** Today `permission = 'me'` hides
   a dataset from everyone but its creator, including the workspace owner. The
   matrix above widens that. If the intent is to keep legacy `me` rows
   creator-only, `custom` can carry the new semantics and `me` stays as it is.
2. **Departments are flat or hierarchical?** `parent_id` is in the schema either
   way; the question is whether the UI renders a tree now or later.
3. **Should a department grant reach a member who joins later?** With the
   predicate above, yes — the grant is on the department, so a new member placed
   in it inherits access. That is the useful reading of "多选部门", but it is a
   standing grant and worth confirming.

## Test plan

- Unit: the predicate matrix — creator, manager, member inside a granted
  department, member outside it, explicitly granted individual, outsider tenant,
  and each mode against each role.
- Unit: `PUT authorization` is a replace, not an append; a non-custom mode clears
  the subjects.
- Integration: a dataset in `custom` mode is absent from an unauthorized
  member's list response and refused by id.
- Integration: a custom-authorized member can read but cannot upload, parse or
  delete.
- E2E: extend the existing account fixtures with a second department and a member
  outside it, then run the read/write matrix per role as the P5-01 E2E does.
