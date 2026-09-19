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

## fix(chat): give repair_bad_citation_formats a marker numbering basis

`api/db/services/dialog_service.py:560` `repair_bad_citation_formats()` validates
markers with `0 <= i < len(chunks)` (`safe_add`, line 564), yet it is called from
two branches with different bases: `insert_citations` emits **0-based** markers
(no markers from the model, line 889), while the model's own markers are
**1-based** (line 903, and the agentic path at line 2153). Its digits are
preserved (only the marker syntax is normalized), so the answer text is
unaffected — but the citation index set is off by one in the 1-based branch.

Direction: pass the basis per call, or convert the model's markers to pool
indexes before validating. Not changed with `cited_chunk_indexes()` because
branch A is genuinely 0-based and needs a sample-driven decision.

## feat(web): give a direct answer the pool it quotes, server-side

`4496afd8e` resolves an answer's citations against the last pool it quoted, but
only in the UI: the tool loop can answer straight from the conversation history
(`[Tool loop] Answering directly at step 1 — no tool needed`), and the reference
entry the endpoints write for such a turn stays the empty placeholder
`{"chunks": [], "doc_aggs": []}`. Anything reading the raw stream — the SDK, the
share endpoints — therefore sees `[ID:1]` markers with no pool to resolve them.
Server-side direction: when an answer arrives with markers and no pool of its own,
attach the session's most recent non-empty reference, the way the UI already does.

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

