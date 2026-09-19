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
retrieved nothing.

Direction when this is picked up: prefer "unopenable but honest" over "openable but
possibly wrong" — resolve through inheritance only when the answer's markers are a
subset of the previous answer's markers (a copy), and otherwise leave them as the
muted `[n]` markers the renderer already draws for an unresolvable citation.

## feat(web): give a direct answer the pool it quotes, server-side

Still open, and only this half: an answer composed without retrieval of its own
(`[Tool loop] Answering directly at step 1 — no tool needed`) persists the empty
placeholder `{"chunks": [], "doc_aggs": []}` while quoting the previous answer's
markers. The UI resolves those against the pool the answer quoted
(`resolveAnswerPools`, `4496afd8e`); anything reading the raw stream — the SDK, the
bot endpoints — still sees markers with no pool behind them, because the pool
never leaves the client.

Server-side direction: when an answer arrives with markers and no pool of its own,
attach the session's most recent non-empty reference, the way the UI already does.

The other half of this gap is closed: markers used to be numbered against the
compose-stage pool (`cite_chunks`) while the reference came from the chat-side
accumulator, so a valid marker could name a passage the client never received.
`_citation_pool` (`1c2de066f`) hands back the pool the model was numbered on.
Measured after that change the remaining failures are the two above, which no
server-side pool exists for.

## fix(rag): make the Go agentic-rag subtree build again

The Go half of the agentic pipeline does not compile in this checkout, so its
stage logs could only be parse-checked when they were made single-line:

- `internal/rag/agentic-rag/runtime/` holds two packages in one directory —
  `action_session.go` declares `package runtime`, `tool_search_test.go` declares
  `package harness`;
- `internal/rag/advanced_rag/agentic_rag_graph.go` imports
  `ragflow/internal/rag/advanced_rag/harness`, `…/harness/orchestrator` and
  `…/slots`, none of which exist in the tree.

Direction: decide whether the Go port is still carried — if it is, restore those
packages and the `package` clause; if it is not, delete the subtree rather than
leaving a directory that cannot be built or tested.

