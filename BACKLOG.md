# Backlog

Deferred work for this fork. Not user documentation — `docs/` publishes the
Docusaurus site, so fork-internal follow-ups live here.

Each entry is written as the commit that would close it, so the intent survives
without a tracked issue.

## fix(rag): verify [ID:N] citation markers against actual evidence source

- Currently the LLM may cite [ID:5] when the fact is from [ID:2].
- Proposed: post-process the answer, check whether chunk[N] actually
  contains the cited fact; if not, either correct the ID or strip the marker.
- Rationale: deterministic, doesn't rely on the LLM's self-awareness.

Evidence on record (2026-09-17, `QA - GB` assistant, PVC/D question): the
answer's pool was the 5 chunks whose contents total 6191 chars (matching the
run log), with the PVC table at 1-based `ID:2`, but the answer cited `[ID:5]`
(the component-material/environment/editing-notes chunk) for the 10.0 N/mm² and
150% figures. The previous turn cited `[ID:4]` for table 3 and was correct, so
the numbering is rendered and followed correctly — the miss is attribution.
Aggravating factors: `pre_summary_len=0` (low mode skips the draft summary, so
the answer was composed straight from ~6.5 KB of raw evidence) and two similar
tables in the same pool.

## fix(citation): resolve reference chunks by id for the canvas object shape

`agent/canvas.py:1099` fills the reference as `r["chunks"][cid] = ck` — a map
keyed by **chunk id** — while `web/src/components/next-markdown-content` reads it
as `chunks[chunkIndex]` with a numeric citation index
(`IReferenceObject.chunks: Record<string, IReferenceChunk>`). Numeric keys never
match chunk-id keys, so on that wire shape every citation renders a "图 N" chip
whose popover is empty and whose image is missing, regardless of the 1-based /
0-based question fixed in `citedChunkIndex`.

Direction: either key the map by 0-based pool index at the producer, or resolve
`marker -> chunk id -> map entry` on the consumer. Needs a captured
object-shaped payload to pin the expected contract before changing either side.

## feat(web): bound how far a citation's pool inheritance may reach

CLOSED FOR NOW — review in ~6 months, with the numbers below.

An answer that arrives with no pool of its own resolves against the last pool seen
before it (`resolveAnswerPools`, `4496afd8e`). That is right for the shape it was
written for: the tool loop can answer straight from the conversation history
(`[Tool loop] Answering directly at step 1 — no tool needed`) and quote the previous
answer's markers verbatim, which index that previous pool. It is wrong for one
shape: if the model *invented* a marker rather than copying one, inheritance points
it at whatever chunk sits at that position in the previous pool, and the reader
opens an unrelated passage — a wrong attribution rather than a missing one.

Measured before the server-side fix (`1c2de066f`), which removes most of the
exposure by handing back the pool the model was numbered on: 12 of 49 cited answers
had no resolving pool of their own, 10 of those resolved through inheritance, 2
stayed unopenable. After the fix, inheritance only applies to turns that genuinely
retrieved nothing. The route guard (`88bc44336`) removes that shape on the dialog path,
so re-measure before acting on this entry as well.

Direction when this is picked up: prefer "unopenable but honest" over "openable but
possibly wrong" — resolve through inheritance only when the answer's markers are a
subset of the previous answer's markers (a copy), and otherwise leave them as the
muted `[n]` markers the renderer already draws for an unresolvable citation.

## feat(web): give a direct answer the pool it quotes, server-side

DEFERRED — evaluate after the route fix, which is what produced this shape.

An answer composed without retrieval of its own persists the empty placeholder
`{"chunks": [], "doc_aggs": []}` while quoting the previous answer's markers. The UI
resolves those against the pool the answer quoted (`resolveAnswerPools`, `4496afd8e`);
anything reading the raw stream — the SDK, the bot endpoints — still sees markers with
no pool behind them, because the pool never leaves the client.

Server-side direction: when an answer arrives with markers and no pool of its own,
attach the session's most recent non-empty reference, the way the UI already does.

Why it waits: the route guard (`88bc44336`) makes a knowledge-base-bound assistant
retrieve on every user turn, so `[Tool loop] Answering directly at step 1 — no tool
needed` no longer happens on the dialog path, and with it the answers that arrive
quoting a pool they never retrieved. Re-measure with
`tools/scripts/audit_answer_rendering.py --since <date>` before writing the patch: if
no answer arrives with markers and an empty pool, this entry has no subject left.

The other half of this gap is closed: markers used to be numbered against the
compose-stage pool (`cite_chunks`) while the reference came from the chat-side
accumulator, so a valid marker could name a passage the client never received.
`_citation_pool` (`1c2de066f`) hands back the pool the model was numbered on.
The failures measured after that change were two answers that arrived with markers and
no pool of their own — the shape the route guard removes.

## fix(go): rewire cmd off the deleted rag port

The ported subtrees are gone (`37337127b`): `internal/rag/advanced_rag` and
`internal/rag/agentic-rag` are deleted (81 files, the abandoned Go agentic loop), and
the one subpackage another tree used — `prompts` — moved to `internal/prompts`. Its
only real importer, `internal/agent/component/prompts/citation.go`, was repointed.
`go build ./internal/...` is clean and `go test ./internal/prompts/ ./internal/dao/`
passes.

What is still failing is the wiring: `cmd/ragflow_server.go` imports
`ragflow/internal/rag/agentic-rag` (line 42) and `…/agentic-rag/runtime` (line 43) and
makes 28 qualified calls into them across lines 108-2208. `go build ./...` reports
exactly those two errors and nothing else. Go is not a shipped path in this fork's
image (`/ragflow/bin` holds only `.gitkeep` and the Dockerfile never runs `go build`),
so production is unaffected.

Direction: delete the cmd wiring for the agentic-rag server surface — the Python
`rag_agent` is the shipped path — then confirm no reference to the deleted packages
survives anywhere in the tree.

