#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
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

import json
import os
from types import SimpleNamespace

import pytest

from api.db import cable_templates


@pytest.mark.p2
@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        (" TRUE ", True),
        ("yes", True),
        ("on", True),
        ("1", True),
        ("false", False),
        ("0", False),
        ("", False),
        (1, True),
        (0, False),
        (None, False),
    ],
)
def test_flag_enabled_parses_yaml_and_env_forms(value, expected):
    assert cable_templates._flag_enabled(value) is expected


@pytest.mark.p2
def test_cable_only_enabled_reads_the_show_cable_only_config_key(monkeypatch):
    seen = []

    def fake_get_base_config(key, default=None):
        seen.append(key)
        return True

    monkeypatch.setattr(cable_templates, "get_base_config", fake_get_base_config)

    assert cable_templates.cable_only_enabled() is True
    assert seen == [cable_templates.CABLE_ONLY_CONFIG_KEY]


@pytest.mark.p2
def test_scope_directories_narrows_to_cable_directory_when_enabled(monkeypatch):
    monkeypatch.setattr(cable_templates, "cable_only_enabled", lambda: True)

    assert cable_templates.template_scope_directories() == [cable_templates.cable_templates_directory()]
    assert cable_templates.cable_templates_directory().endswith(os.path.join("agent", "templates", "cable_templates"))


@pytest.mark.p2
def test_scope_directories_keeps_official_templates_when_disabled(monkeypatch):
    monkeypatch.setattr(cable_templates, "cable_only_enabled", lambda: False)

    assert cable_templates.template_scope_directories() == [cable_templates.agent_templates_directory()]


@pytest.mark.p2
def test_cable_template_ids_covers_every_shipped_cable_template():
    ids = cable_templates.cable_template_ids()

    assert ids == {"cable_bidding", "cable_standards", "cable_qc_troubleshoot"}


@pytest.mark.p2
def test_shipped_cable_templates_are_recommended_agent_canvases():
    directory = cable_templates.cable_templates_directory()

    for name in sorted(os.listdir(directory)):
        with open(os.path.join(directory, name), encoding="utf-8") as f:
            template = json.load(f)
        assert template["id"] == name[: -len(".json")]
        assert template["canvas_type"] == "Cable Industry"
        assert "Recommended" in template["canvas_types"]
        assert template["title"]["zh"]
        assert template["description"]["zh"]
        assert template["dsl"]["components"]["begin"]["obj"]["component_name"] == "Begin"


@pytest.mark.p2
def test_filter_scoped_templates_drops_official_rows_when_enabled(monkeypatch):
    monkeypatch.setattr(cable_templates, "cable_only_enabled", lambda: True)
    rows = [
        SimpleNamespace(id="9"),
        SimpleNamespace(id="cable_bidding"),
        SimpleNamespace(id="cable_standards"),
        SimpleNamespace(id="cable_qc_troubleshoot"),
    ]

    kept = cable_templates.filter_scoped_templates(rows)

    assert [row.id for row in kept] == ["cable_bidding", "cable_standards", "cable_qc_troubleshoot"]


@pytest.mark.p2
def test_filter_scoped_templates_keeps_every_row_when_disabled(monkeypatch):
    monkeypatch.setattr(cable_templates, "cable_only_enabled", lambda: False)
    rows = [SimpleNamespace(id="9"), SimpleNamespace(id="cable_bidding")]

    kept = cable_templates.filter_scoped_templates(rows)

    assert [row.id for row in kept] == ["9", "cable_bidding"]
