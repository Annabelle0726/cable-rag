#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Unit tests for rag.utils.file_utils.extract_embed_file.

Regression guard: the OLE branch used to report *every* internal stream of a
legacy .doc/.ppt/.xls container (WordDocument, 0Table, \\x05SummaryInformation,
WpsCustomData, ...) as an embedded file. naive.chunk then recursed into each
bogus "<sha10>.bin" entry and failed with "file type not supported yet",
flooding the task log on every legacy .doc upload.
"""

import io
import struct
import zipfile
from pathlib import Path

from rag.utils import file_utils
from rag.utils.file_utils import extract_embed_file

REPO_ROOT = Path(__file__).resolve().parents[4]
LEGACY_DOC = REPO_ROOT / "internal" / "parser" / "parser" / "testdata" / "table.doc"


def _docx_bytes(marker: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document>{marker}</w:document>")
    return buf.getvalue()


def _ole10native(payload: bytes, filename: bytes) -> bytes:
    """Build the payload layout _extract_ole10native_payload unwraps."""
    return struct.pack("<I", 2) + filename + b"C:\\tmp\\\x00" + b"C:\\tmp\\\x00" + b"\x00\x00\x00\x00" + struct.pack("<I", len(payload)) + payload


class _FakeOle:
    """Stand-in for olefile.OleFileIO exposing a fixed stream layout."""

    def __init__(self, streams):
        self._streams = streams

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def listdir(self):
        return list(self._streams)

    def openstream(self, entry):
        return io.BytesIO(self._streams[tuple(entry)])


def test_legacy_doc_internal_streams_are_not_embedded_files():
    """A real .doc stores WordDocument/0Table/WpsCustomData streams, not embeds."""
    assert extract_embed_file(LEGACY_DOC.read_bytes()) == []


def test_ole_keeps_real_embedded_objects_and_drops_structure(monkeypatch):
    embedded_a, embedded_b = _docx_bytes("A"), _docx_bytes("B")
    streams = {
        ("WordDocument",): b"\xec\xa5\xc1\x00" + b"body" * 20,
        ("1Table",): b"\x00\x01" * 400,
        ("Data",): b"",
        ("\x05SummaryInformation",): b"\xfe\xff" + b"META" * 20,
        ("WpsCustomData",): b"\x01\x02" * 14,
        ("ObjectPool", "_1", "\x01Ole10Native"): _ole10native(embedded_a, b"embedded.docx\x00"),
        ("ObjectPool", "_2", "raw.bin"): embedded_b,
    }
    monkeypatch.setattr(file_utils.olefile, "OleFileIO", lambda *_a, **_k: _FakeOle(streams))

    embeds = extract_embed_file(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"pad" * 10)

    assert len(embeds) == 2
    assert all(payload.startswith(b"PK\x03\x04") for _, payload in embeds)
    assert not any(b"body" in payload or b"META" in payload for _, payload in embeds)


def test_docx_embedded_objects_keep_their_names():
    inner = _docx_bytes("nested")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
        z.writestr("word/embeddings/oleObject1.bin", inner)

    embeds = extract_embed_file(buf.getvalue())

    assert [name for name, _ in embeds] == ["oleObject1.bin"]
    assert embeds[0][1] == inner


def test_docx_without_embeddings_yields_nothing():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")

    assert extract_embed_file(buf.getvalue()) == []


def test_unknown_container_yields_nothing():
    assert extract_embed_file(b"not a container at all") == []
