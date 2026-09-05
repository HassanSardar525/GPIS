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
    assert "Rank ${rank.rank} of ${state.districts.filter(item => item.scores[category] != null).length}" in script
    assert "of 5" not in script


def test_chat_output_is_escaped_before_html_rendering():
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "escapeHtml(data.answer)" in script
    assert "safeUrl(citation.url)" in script
    assert "escapeHtml(citation.passage)" in script
    assert "escapeHtml(citation.title)" in script
    assert "escapeHtml(citation.publisher)" in script
    assert "escapeHtml(citation.period)" in script
    assert "escapeHtml(citation.locator)" in script


def test_source_previews_are_inside_the_existing_chat_panel():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert html.count('id="chat-form"') == 1
    assert "function renderCitations(citations = [])" in script
    assert '<details class="citation-preview">' in script
    assert "Retrieved passage" in script
    assert "No retrieved passage is available" in script
    assert "Official source link unavailable" in script
    assert ".citation-preview" in styles


def test_session_controls_explain_persistence_new_chat_and_deletion():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert 'id="new-chat"' in html
    assert 'id="delete-chat"' in html
    assert 'id="memory-note"' in html
    assert "survives page and API restarts" in html
    assert "function startNewChat(message = initialChatMessage)" in script
    assert "function deleteCurrentChat()" in script
    assert "state.chatRequest += 1" in script
    assert "window.localStorage.getItem('gpis.sessionId')" in script
    assert "window.localStorage.setItem('gpis.sessionId', sessionId)" in script
    assert "/api/v1/sessions/${encodeURIComponent(state.sessionId)}" in script
    assert "error.code === 'session_expired'" in script
    assert "document.querySelector('#chat-question').value = ''" in script


def test_loading_failure_accessibility_and_mobile_states_are_explicit():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert 'aria-live="polite"' in html
    assert 'aria-busy="false"' in html
    assert "requestId !== state.districtRequest" in script
    assert "requestId !== state.rankingRequest" in script
    assert 'data-action="retry-chat"' in script
    assert "A deterministic fallback answer is shown" in script
    assert ".skeleton" in styles
    assert "@media (max-width: 520px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


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


def test_score_quality_metadata_is_rendered_and_escaped():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert 'id="overall-quality"' in html
    assert "function renderScoreQuality(detail)" in script
    assert "escapeHtml(detail.version)" in script
    assert "escapeHtml(detail.reporting_period)" in script
    assert "detail.warnings.map(item => `<li>${escapeHtml(item)}</li>`)" in script
    assert "data.score_details.education" in script
    assert "district.score_detail" in script
    assert ".score-quality" in styles
