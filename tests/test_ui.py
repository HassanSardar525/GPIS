from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_trend_comparison_and_rag_states():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="trend-periods"' in html
    assert 'id="compare-scores"' in html
    assert 'id="compare-trends"' in html
    assert "/trends/development-budget" in script
    assert "data.mode" in script and "data.route" in script and "data.trace_id" in script
    assert "Rank ${rank.rank} of ${state.districts.length}" in script
    assert "of 5" not in script


def test_chat_output_is_escaped_before_html_rendering():
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "escapeHtml(data.answer)" in script
    assert "safeUrl(citation.url)" in script
