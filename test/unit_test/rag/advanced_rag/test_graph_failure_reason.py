from rag.advanced_rag.agentic_rag_graph import _graph_failure_reason


def test_reports_the_error_message():
    exc = RuntimeError("Embedding request failed for GeminiEmbed")

    assert _graph_failure_reason(exc) == "Embedding request failed for GeminiEmbed"


def test_unwraps_a_task_group_wrapper():
    # LangGraph surfaces a node failure either directly or wrapped in a task
    # group; the wrapper's own text ("unhandled errors in a TaskGroup") says
    # nothing about the cause.
    group = ExceptionGroup("unhandled errors in a TaskGroup", [ValueError("no rows")])

    assert _graph_failure_reason(group) == "no rows"


def test_collapses_whitespace_so_the_reason_fits_on_one_line():
    exc = RuntimeError("connection refused\n  while calling\tthe model")

    assert _graph_failure_reason(exc) == "connection refused while calling the model"


def test_falls_back_to_the_exception_type_and_truncates_long_messages():
    assert _graph_failure_reason(ValueError()) == "ValueError"

    reason = _graph_failure_reason(RuntimeError("x" * 400))

    assert len(reason) == 300
    assert reason.endswith("...")
