from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_trend_comparison_and_rag_states():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="trend-periods"' in html
    assert html.count('id="chat-form"') == 1
    assert 'id="compare-scores"' not in html
    assert 'id="compare-trends"' not in html
    assert 'id="compare-district"' not in html
    assert "/trends/development-budget" in script
    assert "data.mode" in script and "data.route" in script and "data.trace_id" in script
    assert "Rank ${rank.rank} of ${state.districts.length}" in script
    assert "of 5" not in script


def test_chat_output_is_escaped_before_html_rendering():
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "escapeHtml(data.answer)" in script
    assert "safeUrl(citation.url)" in script


def test_structured_comparison_renders_inside_existing_chat_panel():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert html.count('id="chat-form"') == 1
    assert "function renderComparison(comparison)" in script
    assert "renderComparison(data.comparison)" in script
    assert "component.values[left.slug]" in script
    assert "escapeHtml(component.label)" in script
    assert "comparison.trends" in script
    assert ".comparison-result" in styles
    assert ".comparison-table-wrap { overflow-x: auto; }" in styles
