"""
Tests for src/deploy_dashboard.py
Cornflower Health project

All Notion API calls are mocked — no live API access required.
Tests verify correct block structures, page creation payloads,
view configurations, dry-run behavior, and config file output.
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import deploy_dashboard as dd


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Override CONFIG_DIR and CONFIG_FILE to use a temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "dashboard_ids.json"
    monkeypatch.setattr(dd, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(dd, "CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def mock_client():
    """Create a mock httpx.Client that returns realistic Notion API responses."""
    client = mock.MagicMock()

    page_counter = [0]
    block_counter = [0]
    view_counter = [0]

    def mock_post(url, headers=None, json=None):
        resp = mock.MagicMock()
        resp.status_code = 200

        if "/pages" in url and "/children" not in url:
            page_counter[0] += 1
            resp.json.return_value = {
                "id": f"page-{page_counter[0]:04d}",
                "object": "page",
            }
        elif "/children" in url:
            children = json.get("children", []) if json else []
            results = []
            for child in children:
                block_counter[0] += 1
                child_type = child.get("type", "unknown")
                result = {
                    "id": f"block-{block_counter[0]:04d}",
                    "type": child_type,
                }
                results.append(result)
            resp.json.return_value = {"results": results}
        elif "/views" in url:
            view_counter[0] += 1
            resp.json.return_value = {
                "id": f"view-{view_counter[0]:04d}",
                "object": "view",
            }
        else:
            resp.json.return_value = {}

        resp.raise_for_status = mock.MagicMock()
        return resp

    def mock_get(url, headers=None):
        resp = mock.MagicMock()
        resp.status_code = 200
        # Return child blocks for tab block children queries
        resp.json.return_value = {
            "results": [
                {"id": f"tab-child-{i}", "type": "tab"} for i in range(4)
            ]
        }
        resp.raise_for_status = mock.MagicMock()
        return resp

    client.post = mock.MagicMock(side_effect=mock_post)
    client.get = mock.MagicMock(side_effect=mock_get)
    client.close = mock.MagicMock()
    return client


# ============================================================
# Block builder tests
# ============================================================

class TestBlockBuilders:
    """Test individual block builder functions."""

    def test_rich_text_plain(self):
        rt = dd._rich_text("hello")
        assert rt["type"] == "text"
        assert rt["text"]["content"] == "hello"
        assert "annotations" not in rt

    def test_rich_text_bold(self):
        rt = dd._rich_text("hello", bold=True)
        assert rt["annotations"]["bold"] is True

    def test_rich_text_color(self):
        rt = dd._rich_text("hello", color="green")
        assert rt["annotations"]["color"] == "green"

    def test_heading_2(self):
        h = dd.heading_2("Test Heading")
        assert h["type"] == "heading_2"
        assert h["heading_2"]["rich_text"][0]["text"]["content"] == "Test Heading"

    def test_heading_3(self):
        h = dd.heading_3("Sub Heading")
        assert h["type"] == "heading_3"
        assert h["heading_3"]["rich_text"][0]["text"]["content"] == "Sub Heading"

    def test_divider(self):
        d = dd.divider()
        assert d["type"] == "divider"

    def test_paragraph(self):
        p = dd.paragraph("Some text")
        assert p["type"] == "paragraph"
        assert p["paragraph"]["rich_text"][0]["text"]["content"] == "Some text"

    def test_paragraph_bold(self):
        p = dd.paragraph("Bold text", bold=True)
        assert p["paragraph"]["rich_text"][0]["annotations"]["bold"] is True

    def test_paragraph_color(self):
        p = dd.paragraph("Gray text", color="gray")
        assert p["paragraph"]["rich_text"][0]["annotations"]["color"] == "gray"

    def test_paragraph_rich(self):
        rt_list = [dd._rich_text("a"), dd._rich_text("b", bold=True)]
        p = dd.paragraph_rich(rt_list)
        assert len(p["paragraph"]["rich_text"]) == 2

    def test_callout(self):
        c = dd.callout("Alert!", "🟢", "green_background")
        assert c["type"] == "callout"
        assert c["callout"]["icon"]["emoji"] == "🟢"
        assert c["callout"]["color"] == "green_background"
        assert c["callout"]["rich_text"][0]["text"]["content"] == "Alert!"

    def test_callout_with_children(self):
        child = dd.paragraph("child")
        c = dd.callout("Parent", "📊", children=[child])
        assert len(c["callout"]["children"]) == 1
        assert c["callout"]["children"][0]["type"] == "paragraph"

    def test_callout_rich(self):
        rt = [dd._rich_text("Test", bold=True)]
        c = dd.callout_rich(rt, "🔴", "red_background")
        assert c["callout"]["rich_text"][0]["annotations"]["bold"] is True

    def test_toggle(self):
        t = dd.toggle("Click me")
        assert t["type"] == "toggle"
        assert t["toggle"]["rich_text"][0]["text"]["content"] == "Click me"
        assert "children" not in t["toggle"]

    def test_toggle_with_children(self):
        child = dd.paragraph("Inside toggle")
        t = dd.toggle("Click me", children=[child])
        assert len(t["toggle"]["children"]) == 1

    def test_table_of_contents(self):
        toc = dd.table_of_contents()
        assert toc["type"] == "table_of_contents"

    def test_bookmark(self):
        b = dd.bookmark("https://example.com")
        assert b["bookmark"]["url"] == "https://example.com"


# ============================================================
# Page content builder tests
# ============================================================

class TestPageContentBuilders:
    """Test that page content builders produce correct block structures."""

    def test_daily_dashboard_block_count(self):
        blocks = dd.build_daily_dashboard_blocks()
        # Should have: 2 callouts + heading+divider+2para (exertion) +
        # heading+divider+6para (metrics) + heading+divider+5para (sleep) +
        # 3 toggles + heading+divider+2para+callout (notes) + toggle (workout)
        assert len(blocks) >= 20

    def test_daily_dashboard_starts_with_recovery_callout(self):
        blocks = dd.build_daily_dashboard_blocks()
        assert blocks[0]["type"] == "callout"
        assert blocks[0]["callout"]["color"] == "green_background"
        assert blocks[0]["callout"]["icon"]["emoji"] == "🟢"

    def test_daily_dashboard_has_recovery_breakdown(self):
        blocks = dd.build_daily_dashboard_blocks()
        assert blocks[1]["type"] == "callout"
        assert blocks[1]["callout"]["color"] == "gray_background"
        assert "Recovery Breakdown" in blocks[1]["callout"]["rich_text"][0]["text"]["content"]

    def test_daily_dashboard_has_key_metrics_section(self):
        blocks = dd.build_daily_dashboard_blocks()
        headings = [b for b in blocks if b["type"] == "heading_2"]
        heading_texts = [
            b["heading_2"]["rich_text"][0]["text"]["content"] for b in headings
        ]
        assert "Key Metrics" in heading_texts

    def test_daily_dashboard_has_sleep_section(self):
        blocks = dd.build_daily_dashboard_blocks()
        headings = [b for b in blocks if b["type"] == "heading_2"]
        heading_texts = [
            b["heading_2"]["rich_text"][0]["text"]["content"] for b in headings
        ]
        assert "Sleep" in heading_texts

    def test_daily_dashboard_has_exertion_section(self):
        blocks = dd.build_daily_dashboard_blocks()
        headings = [b for b in blocks if b["type"] == "heading_2"]
        heading_texts = [
            b["heading_2"]["rich_text"][0]["text"]["content"] for b in headings
        ]
        assert "Exertion & Stress" in heading_texts

    def test_daily_dashboard_has_notes_section(self):
        blocks = dd.build_daily_dashboard_blocks()
        headings = [b for b in blocks if b["type"] == "heading_2"]
        heading_texts = [
            b["heading_2"]["rich_text"][0]["text"]["content"] for b in headings
        ]
        assert "Notes & Log" in heading_texts

    def test_daily_dashboard_has_toggles(self):
        blocks = dd.build_daily_dashboard_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        toggle_texts = [
            b["toggle"]["rich_text"][0]["text"]["content"] for b in toggles
        ]
        assert any("Flags" in t for t in toggle_texts)
        assert any("Booster" in t for t in toggle_texts)
        assert any("Rolling Averages" in t for t in toggle_texts)
        assert any("Workout" in t for t in toggle_texts)

    def test_daily_dashboard_has_button_placeholder(self):
        blocks = dd.build_daily_dashboard_blocks()
        callouts = [b for b in blocks if b["type"] == "callout"]
        button_callouts = [
            c for c in callouts
            if "MANUAL STEP" in c["callout"]["rich_text"][0]["text"]["content"]
        ]
        assert len(button_callouts) == 1
        assert "button" in button_callouts[0]["callout"]["rich_text"][0]["text"]["content"].lower()

    def test_trends_has_tab_block(self):
        blocks = dd.build_trends_blocks()
        assert len(blocks) == 1
        assert blocks[0]["type"] == "tab_block"

    def test_trends_has_4_tabs(self):
        blocks = dd.build_trends_blocks()
        tabs = blocks[0]["tab_block"]["children"]
        assert len(tabs) == 4
        titles = [t["tab"]["title"] for t in tabs]
        assert titles == ["5 Days", "10 Days", "20 Days", "40 Days"]

    def test_trends_tabs_have_children(self):
        blocks = dd.build_trends_blocks()
        for tab in blocks[0]["tab_block"]["children"]:
            assert len(tab["tab"]["children"]) >= 1

    def test_flags_has_flag_definitions(self):
        blocks = dd.build_flags_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        assert len(toggles) == 1
        assert "Flag Definitions" in toggles[0]["toggle"]["rich_text"][0]["text"]["content"]
        # Should have 9 flag definitions as children
        children = toggles[0]["toggle"]["children"]
        assert len(children) == 9

    def test_flags_has_heading(self):
        blocks = dd.build_flags_blocks()
        assert blocks[0]["type"] == "heading_2"
        assert "Flagged Days" in blocks[0]["heading_2"]["rich_text"][0]["text"]["content"]

    def test_full_table_has_manual_steps(self):
        blocks = dd.build_full_table_blocks()
        callouts = [b for b in blocks if b["type"] == "callout"]
        assert len(callouts) == 1
        text = callouts[0]["callout"]["rich_text"][0]["text"]["content"]
        assert "Show as Bar" in text

    def test_settings_has_baselines(self):
        blocks = dd.build_settings_blocks()
        assert blocks[0]["type"] == "heading_2"
        assert "Baselines" in blocks[0]["heading_2"]["rich_text"][0]["text"]["content"]
        # Check baseline values are present
        all_text = " ".join(
            b.get(b["type"], {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
            for b in blocks if b["type"] == "paragraph"
        )
        assert "53.2" in all_text
        assert "61" in all_text
        assert "50 min" in all_text

    def test_settings_has_4_toggles(self):
        blocks = dd.build_settings_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        assert len(toggles) == 4
        toggle_texts = [
            t["toggle"]["rich_text"][0]["text"]["content"] for t in toggles
        ]
        assert "Recovery Scoring Algorithm" in toggle_texts
        assert "Stimulant Protocol & Decision Tree" in toggle_texts
        assert "Flag Thresholds" in toggle_texts
        assert "Zone Mapping" in toggle_texts

    def test_settings_zone_mapping(self):
        blocks = dd.build_settings_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        zone_toggle = [
            t for t in toggles
            if "Zone" in t["toggle"]["rich_text"][0]["text"]["content"]
        ][0]
        children = zone_toggle["toggle"]["children"]
        assert len(children) == 4
        all_text = " ".join(
            c["paragraph"]["rich_text"][0]["text"]["content"] for c in children
        )
        assert "GREEN" in all_text
        assert "YELLOW" in all_text
        assert "ORANGE" in all_text
        assert "RED" in all_text


# ============================================================
# View payload builder tests
# ============================================================

class TestViewPayloads:
    """Test view payload construction."""

    def test_linked_view_payload(self):
        payload = dd._linked_view_payload(
            parent_block_id="block-123",
            title="Test View",
            visible_properties=["date", "hrv_sdnn_ms"],
            sorts=[{"property": "date", "direction": "descending"}],
            view_type="table",
        )
        assert payload["parent"] == {"block_id": "block-123"}
        assert payload["title"] == "Test View"
        assert payload["create_database"] == dd.NOTION_DATABASE_ID
        assert payload["type"] == "table"
        assert len(payload["visible_properties"]) == 2
        assert len(payload["sorts"]) == 1

    def test_linked_view_with_filter(self):
        f = {"property": "date", "date": {"equals": "2026-04-06"}}
        payload = dd._linked_view_payload(
            parent_block_id="block-123",
            title="Filtered",
            visible_properties=["date"],
            filter_obj=f,
        )
        assert payload["filter"] == f

    def test_chart_view_payload_line(self):
        payload = dd._chart_view_payload(
            parent_block_id="block-123",
            title="HRV Trend",
            chart_type="line",
            x_axis="date",
            y_axis="hrv_sdnn_ms",
        )
        assert payload["type"] == "chart"
        assert payload["chart"]["chart_type"] == "line"
        assert payload["chart"]["x_axis"] == {"property": "date"}
        assert payload["chart"]["y_axis"] == {"property": "hrv_sdnn_ms"}
        assert payload["chart"]["gradient_fill"] is True
        assert payload["chart"]["smooth_line"] is True

    def test_chart_view_payload_bar(self):
        payload = dd._chart_view_payload(
            parent_block_id="block-123",
            title="Deep Sleep",
            chart_type="bar",
            x_axis="date",
            y_axis="sleep_deep_min",
        )
        assert payload["chart"]["chart_type"] == "bar"
        assert "gradient_fill" not in payload["chart"]
        assert "smooth_line" not in payload["chart"]

    def test_chart_view_with_filter(self):
        f = dd._date_relative_filter(10)
        payload = dd._chart_view_payload(
            parent_block_id="block-123",
            title="Test",
            chart_type="line",
            x_axis="date",
            y_axis="hrv_sdnn_ms",
            filter_obj=f,
        )
        assert "filter" in payload


# ============================================================
# API helper tests (mocked)
# ============================================================

class TestApiHelpers:
    """Test API helper functions with mocked HTTP client."""

    def test_create_page(self, mock_client):
        page_id = dd.api_create_page(
            dd.PARENT_PAGE_ID, "Test Page", "📊", mock_client
        )
        assert page_id is not None
        assert page_id.startswith("page-")
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/pages" in call_args[0][0]

    def test_create_page_dry_run(self):
        page_id = dd.api_create_page(
            dd.PARENT_PAGE_ID, "Test Page", "📊", None, dry_run=True
        )
        assert page_id is not None
        assert "dry-run" in page_id

    def test_append_children(self, mock_client):
        children = [dd.paragraph("test")]
        results = dd.api_append_children("block-123", children, mock_client)
        assert results is not None
        assert len(results) == 1
        mock_client.post.assert_called_once()

    def test_append_children_dry_run(self):
        children = [dd.paragraph("test"), dd.divider()]
        results = dd.api_append_children("block-123", children, None, dry_run=True)
        assert results is not None
        assert len(results) == 2

    def test_create_view(self, mock_client):
        payload = dd._linked_view_payload(
            "block-123", "Test", ["date"], view_type="table"
        )
        view_id = dd.api_create_view(payload, mock_client, label="test view")
        assert view_id is not None
        assert view_id.startswith("view-")

    def test_create_view_dry_run(self):
        view_id = dd.api_create_view({}, None, dry_run=True, label="test view")
        assert "dry-run" in view_id

    def test_create_page_rate_limit(self):
        """Test 429 retry logic."""
        client = mock.MagicMock()
        call_count = [0]

        def mock_post(url, headers=None, json=None):
            call_count[0] += 1
            resp = mock.MagicMock()
            if call_count[0] == 1:
                resp.status_code = 429
                resp.headers = {"Retry-After": "0"}
            else:
                resp.status_code = 200
                resp.json.return_value = {"id": "page-retry-ok"}
                resp.raise_for_status = mock.MagicMock()
            return resp

        client.post = mock.MagicMock(side_effect=mock_post)

        page_id = dd.api_create_page(
            dd.PARENT_PAGE_ID, "Retry Test", "📊", client
        )
        assert page_id == "page-retry-ok"
        assert call_count[0] == 2

    def test_create_page_http_error(self):
        """Test HTTP error handling."""
        client = mock.MagicMock()
        resp = mock.MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"
        resp.raise_for_status.side_effect = (
            __import__("httpx").HTTPStatusError("err", request=mock.MagicMock(), response=resp)
        )
        client.post = mock.MagicMock(return_value=resp)

        page_id = dd.api_create_page(
            dd.PARENT_PAGE_ID, "Error Test", "📊", client
        )
        assert page_id is None


# ============================================================
# Nesting handler tests
# ============================================================

class TestNestingHandler:
    """Test the recursive block append logic for Notion's 2-level nesting limit."""

    def test_flat_blocks(self, mock_client):
        blocks = [dd.paragraph("a"), dd.paragraph("b")]
        results = dd.append_blocks_recursive("parent-1", blocks, mock_client, dry_run=False)
        assert len(results) == 2

    def test_one_level_nesting(self, mock_client):
        blocks = [dd.toggle("t", children=[dd.paragraph("child")])]
        results = dd.append_blocks_recursive("parent-1", blocks, mock_client, dry_run=False)
        assert len(results) == 1

    def test_dry_run_nesting(self):
        blocks = [dd.paragraph("a"), dd.toggle("t", children=[dd.paragraph("c")])]
        results = dd.append_blocks_recursive("parent-1", blocks, None, dry_run=True)
        assert len(results) == 2


# ============================================================
# Deploy page tests (mocked)
# ============================================================

class TestDeployPage:
    """Test deploying individual pages."""

    def test_deploy_daily_dashboard(self, mock_client):
        ids = dd.deploy_page("Daily Dashboard", mock_client, dry_run=False)
        assert ids is not None
        assert "page_id" in ids
        assert ids["page_id"].startswith("page-")
        assert "blocks" in ids
        assert "views" in ids
        assert len(ids["views"]) > 0

    def test_deploy_trends(self, mock_client):
        ids = dd.deploy_page("Trends", mock_client, dry_run=False)
        assert ids is not None
        assert "page_id" in ids

    def test_deploy_flags(self, mock_client):
        ids = dd.deploy_page("Flags & Alerts", mock_client, dry_run=False)
        assert ids is not None
        assert "page_id" in ids
        assert "flagged_days_table" in ids["views"]

    def test_deploy_full_table(self, mock_client):
        ids = dd.deploy_page("Full Data Table", mock_client, dry_run=False)
        assert ids is not None
        assert "full_table" in ids["views"]

    def test_deploy_settings(self, mock_client):
        ids = dd.deploy_page("Settings & Reference", mock_client, dry_run=False)
        assert ids is not None
        assert "page_id" in ids

    def test_deploy_unknown_page(self, mock_client):
        ids = dd.deploy_page("Nonexistent Page", mock_client, dry_run=False)
        assert ids is None

    def test_deploy_dry_run(self):
        ids = dd.deploy_page("Daily Dashboard", None, dry_run=True)
        assert ids is not None
        assert "dry-run" in ids["page_id"]


# ============================================================
# Full deploy_all tests
# ============================================================

class TestDeployAll:
    """Test deploying all pages and config file output."""

    def test_deploy_all_dry_run(self, tmp_config):
        result = dd.deploy_all(dry_run=True)
        assert len(result) == 5
        assert "Daily Dashboard" in result
        assert "Trends" in result
        assert "Flags & Alerts" in result
        assert "Full Data Table" in result
        assert "Settings & Reference" in result

    def test_deploy_all_creates_config_file(self, tmp_config):
        dd.deploy_all(dry_run=True)
        assert tmp_config.exists()
        config = json.loads(tmp_config.read_text())
        assert len(config) == 5

    def test_deploy_single_page(self, tmp_config):
        result = dd.deploy_all(dry_run=True, single_page="Trends")
        assert len(result) == 1
        assert "Trends" in result

    def test_deploy_single_page_merges_config(self, tmp_config):
        # First deploy: all pages
        dd.deploy_all(dry_run=True)
        assert tmp_config.exists()
        first_config = json.loads(tmp_config.read_text())
        assert len(first_config) == 5

        # Second deploy: single page (should merge)
        dd.deploy_all(dry_run=True, single_page="Trends")
        second_config = json.loads(tmp_config.read_text())
        assert len(second_config) == 5
        # The Trends entry should be updated
        assert "Trends" in second_config

    def test_config_file_structure(self, tmp_config):
        dd.deploy_all(dry_run=True)
        config = json.loads(tmp_config.read_text())

        for page_name, page_data in config.items():
            assert "page_id" in page_data, f"{page_name} missing page_id"
            assert "views" in page_data, f"{page_name} missing views"
            assert "blocks" in page_data, f"{page_name} missing blocks"
            assert isinstance(page_data["views"], dict)
            assert isinstance(page_data["blocks"], dict)

    def test_daily_dashboard_config_has_views(self, tmp_config):
        dd.deploy_all(dry_run=True)
        config = json.loads(tmp_config.read_text())
        daily = config["Daily Dashboard"]
        assert "exertion_view" in daily["views"]
        assert "notes_view" in daily["views"]
        assert "workout_view" in daily["views"]

    def test_deploy_all_with_mock_client(self, tmp_config, mock_client):
        with mock.patch("deploy_dashboard.httpx.Client", return_value=mock_client):
            result = dd.deploy_all(dry_run=False)
        assert len(result) == 5
        assert tmp_config.exists()

    def test_deploy_all_respects_page_order(self, tmp_config):
        """Pages should be created in the order defined by PAGE_SPECS."""
        result = dd.deploy_all(dry_run=True)
        page_names = list(result.keys())
        expected = list(dd.PAGE_SPECS.keys())
        assert page_names == expected


# ============================================================
# Page specs and constants tests
# ============================================================

class TestConstants:
    """Test that configuration constants match the design spec."""

    def test_page_specs_count(self):
        assert len(dd.PAGE_SPECS) == 5

    def test_page_names(self):
        expected = {
            "Daily Dashboard", "Trends", "Flags & Alerts",
            "Full Data Table", "Settings & Reference",
        }
        assert set(dd.PAGE_SPECS.keys()) == expected

    def test_page_icons(self):
        assert dd.PAGE_SPECS["Daily Dashboard"] == "📊"
        assert dd.PAGE_SPECS["Trends"] == "📈"
        assert dd.PAGE_SPECS["Flags & Alerts"] == "🚩"
        assert dd.PAGE_SPECS["Full Data Table"] == "📋"
        assert dd.PAGE_SPECS["Settings & Reference"] == "⚙️"

    def test_parent_page_id(self):
        assert dd.PARENT_PAGE_ID == "339d7cd8-531f-800b-b02d-efefaa086bf5"

    def test_database_id(self):
        assert dd.NOTION_DATABASE_ID == "339d7cd8-531f-819f-85b2-c769696ea27c"

    def test_notion_version(self):
        assert dd.NOTION_VERSION == "2022-06-28"


# ============================================================
# CLI argument parsing tests
# ============================================================

class TestCLI:
    """Test CLI argument parsing."""

    def test_default_args(self):
        with mock.patch("sys.argv", ["deploy_dashboard.py"]):
            parser = __import__("argparse").ArgumentParser()
            parser.add_argument("--dry-run", action="store_true")
            parser.add_argument("--page", type=str, default=None)
            args = parser.parse_args([])
            assert args.dry_run is False
            assert args.page is None

    def test_dry_run_flag(self):
        parser = __import__("argparse").ArgumentParser()
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--page", type=str, default=None)
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_page_flag(self):
        parser = __import__("argparse").ArgumentParser()
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--page", type=str, default=None)
        args = parser.parse_args(["--page", "Trends"])
        assert args.page == "Trends"

    def test_both_flags(self):
        parser = __import__("argparse").ArgumentParser()
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--page", type=str, default=None)
        args = parser.parse_args(["--dry-run", "--page", "Daily Dashboard"])
        assert args.dry_run is True
        assert args.page == "Daily Dashboard"


# ============================================================
# Dashboard content correctness tests
# ============================================================

class TestDashboardContent:
    """Verify the dashboard content matches the design spec."""

    def test_recovery_callout_uses_zone_colors(self):
        """Verify recovery callout uses the correct color scheme."""
        blocks = dd.build_daily_dashboard_blocks()
        recovery = blocks[0]
        assert recovery["callout"]["color"] == "green_background"

    def test_recovery_breakdown_is_gray(self):
        blocks = dd.build_daily_dashboard_blocks()
        breakdown = blocks[1]
        assert breakdown["callout"]["color"] == "gray_background"

    def test_settings_baselines_values(self):
        """Verify baseline values match coaching-layer.md."""
        blocks = dd.build_settings_blocks()
        paragraphs = [b for b in blocks if b["type"] == "paragraph"]
        texts = [p["paragraph"]["rich_text"][0]["text"]["content"] for p in paragraphs]

        assert any("53.2 ms" in t for t in texts), "HRV baseline missing"
        assert any("61" in t and "66" in t for t in texts), "RHR range missing"
        assert any("50 min" in t for t in texts), "Deep sleep target missing"
        assert any("35 min" in t for t in texts), "Deep sleep floor missing"
        assert any("40 ms" in t for t in texts), "HRV floor missing"

    def test_settings_recovery_algorithm_toggle(self):
        """Recovery algorithm toggle should contain scoring details."""
        blocks = dd.build_settings_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        algo = [
            t for t in toggles
            if "Recovery Scoring" in t["toggle"]["rich_text"][0]["text"]["content"]
        ][0]
        children_text = " ".join(
            c["paragraph"]["rich_text"][0]["text"]["content"]
            for c in algo["toggle"]["children"]
        )
        assert "HRV component" in children_text
        assert "RHR component" in children_text
        assert "Hard Gates" in children_text

    def test_settings_stimulant_protocol(self):
        """Stimulant protocol toggle should contain decision tree."""
        blocks = dd.build_settings_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        protocol = [
            t for t in toggles
            if "Stimulant Protocol" in t["toggle"]["rich_text"][0]["text"]["content"]
        ][0]
        children_text = " ".join(
            c["paragraph"]["rich_text"][0]["text"]["content"]
            for c in protocol["toggle"]["children"]
        )
        assert "Vyvanse 60mg" in children_text
        assert "HRV < 40" in children_text
        assert "Both boosters cleared" in children_text

    def test_flags_all_9_definitions(self):
        """Flag definitions toggle should list all 9 flags."""
        blocks = dd.build_flags_blocks()
        toggles = [b for b in blocks if b["type"] == "toggle"]
        flag_defs = toggles[0]
        children = flag_defs["toggle"]["children"]
        assert len(children) == 9

        all_text = " ".join(
            c["paragraph"]["rich_text"][0]["text"]["content"] for c in children
        )
        for flag_name in [
            "flag_deep_sleep_low", "flag_deep_gate_50", "flag_hrv_very_low",
            "flag_rhr_elevated", "flag_resp_rate_high", "flag_spo2_low",
            "flag_sleep_fragmented", "flag_early_wake", "flag_recovery_red_gate",
        ]:
            assert flag_name in all_text, f"Missing flag definition: {flag_name}"

    def test_trends_tab_windows(self):
        """Trends tabs should be 5/10/20/40 days per design spec."""
        blocks = dd.build_trends_blocks()
        tabs = blocks[0]["tab_block"]["children"]
        titles = [t["tab"]["title"] for t in tabs]
        assert titles == ["5 Days", "10 Days", "20 Days", "40 Days"]


# ============================================================
# Headers and auth tests
# ============================================================

class TestHeaders:
    """Test HTTP header construction."""

    def test_headers_format(self):
        # Temporarily set token for test
        original = dd.NOTION_TOKEN
        try:
            dd.NOTION_TOKEN = "test-token-123"
            headers = dd._headers()
            assert headers["Authorization"] == "Bearer test-token-123"
            assert headers["Notion-Version"] == "2022-06-28"
            assert headers["Content-Type"] == "application/json"
        finally:
            dd.NOTION_TOKEN = original
