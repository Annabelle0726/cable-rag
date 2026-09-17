#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
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

import os
import subprocess

import pytest

from api.utils import office_conversion as module

OLE2_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
DOCX_HEADER = b"PK\x03\x04"
PDF_BODY = b"%PDF-1.4\nconverted\n%%EOF\n"


def _legacy_doc_payload() -> bytes:
    return OLE2_HEADER + b"\x00" * 512


@pytest.mark.p2
def test_is_legacy_office_document_accepts_ole2_containers():
    assert module.is_legacy_office_document(_legacy_doc_payload()) is True


@pytest.mark.p2
@pytest.mark.parametrize(
    "payload",
    [
        DOCX_HEADER + b"docx body",
        b"",
        b"{\\rtf1}",
        OLE2_HEADER[:4],
    ],
)
def test_is_legacy_office_document_rejects_everything_else(payload):
    assert module.is_legacy_office_document(payload) is False


@pytest.mark.p2
def test_soffice_binary_honours_the_override(monkeypatch, tmp_path):
    fake = tmp_path / "soffice"
    fake.write_bytes(b"")
    monkeypatch.setenv("SOFFICE_BIN", str(fake))

    assert module.soffice_binary() == str(fake)
    assert module.conversion_available() is True


@pytest.mark.p2
def test_soffice_binary_ignores_a_missing_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFFICE_BIN", str(tmp_path / "absent"))
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(module, "_SOFFICE_FALLBACK_PATHS", ())

    assert module.soffice_binary() is None
    assert module.conversion_available() is False


@pytest.mark.p2
def test_conversion_without_libreoffice_returns_none(monkeypatch):
    monkeypatch.delenv("SOFFICE_BIN", raising=False)
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(module, "_SOFFICE_FALLBACK_PATHS", ())
    monkeypatch.setattr(module, "_cache_directory", lambda: pytest.importorskip("tempfile").mkdtemp())

    assert module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc") is None


def _stub_soffice(monkeypatch, tmp_path, *, returncode=0, write_pdf=True, calls=None):
    """Stand in for LibreOffice: writes the PDF it would have exported."""
    binary = tmp_path / "soffice"
    binary.write_bytes(b"")
    monkeypatch.setenv("SOFFICE_BIN", str(binary))
    monkeypatch.setattr(module, "_cache_directory", lambda: str(tmp_path / "cache"))

    def fake_run(cmd, **kwargs):
        if calls is not None:
            calls.append(list(cmd))
        outdir = cmd[cmd.index("--outdir") + 1]
        source = cmd[-1]
        if write_pdf:
            with open(os.path.join(outdir, f"{os.path.splitext(os.path.basename(source))[0]}.pdf"), "wb") as f:
                f.write(PDF_BODY)
        return subprocess.CompletedProcess(cmd, returncode, b"", b"stub")

    monkeypatch.setattr(module.subprocess, "run", fake_run)


@pytest.mark.p2
def test_conversion_exports_a_pdf_and_reuses_the_cache(monkeypatch, tmp_path):
    calls = []
    _stub_soffice(monkeypatch, tmp_path, calls=calls)

    first = module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc")
    assert first == PDF_BODY
    assert len(calls) == 1

    # The headless run is asked for a private profile and an out-of-tree output
    # directory; without the profile a second conversion would fail.
    command = calls[0]
    assert "--headless" in command
    assert "--convert-to" in command
    assert command[command.index("--convert-to") + 1] == "pdf"
    assert any(arg.startswith("-env:UserInstallation=file://") for arg in command)

    second = module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc")
    assert second == PDF_BODY
    assert len(calls) == 1, "a converted document must not be converted twice"


@pytest.mark.p2
def test_cache_is_keyed_by_content(monkeypatch, tmp_path):
    calls = []
    _stub_soffice(monkeypatch, tmp_path, calls=calls)

    module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc")
    # Same document id, different bytes: the cached PDF belongs to the old
    # revision, so the new one has to be converted.
    module.convert_legacy_office_to_pdf(_legacy_doc_payload() + b"revision 2", "doc-1", "spec.doc")

    assert len(calls) == 2


@pytest.mark.p2
def test_failed_conversion_returns_none(monkeypatch, tmp_path):
    _stub_soffice(monkeypatch, tmp_path, returncode=1, write_pdf=False)

    assert module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc") is None


@pytest.mark.p2
def test_success_without_an_output_file_returns_none(monkeypatch, tmp_path):
    _stub_soffice(monkeypatch, tmp_path, returncode=0, write_pdf=False)

    assert module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc") is None


@pytest.mark.p2
def test_timeout_returns_none(monkeypatch, tmp_path):
    binary = tmp_path / "soffice"
    binary.write_bytes(b"")
    monkeypatch.setenv("SOFFICE_BIN", str(binary))
    monkeypatch.setattr(module, "_cache_directory", lambda: str(tmp_path / "cache"))

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, module.CONVERT_TIMEOUT_SECONDS)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.convert_legacy_office_to_pdf(_legacy_doc_payload(), "doc-1", "spec.doc") is None


@pytest.mark.p2
@pytest.mark.parametrize(
    "filename,expected_suffix",
    [
        ("spec.doc", ".doc"),
        ("SPEC.DOC", ".doc"),
        ("spec.xls", ".xls"),
        ("spec", ".doc"),
        ("spec.verylongextension", ".doc"),
        ("../../etc/passwd", ".doc"),
    ],
)
def test_only_a_safe_extension_reaches_the_temporary_file(filename, expected_suffix):
    assert module._suffix_for(filename) == expected_suffix
