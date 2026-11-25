"""Run the public district journey with real API requests at both viewport widths."""

import asyncio
import os
import sys

import pytest


@pytest.fixture
def browser_page(request):
    url = os.getenv("GPIS_BROWSER_TEST_URL")
    if not url:
        pytest.skip("Set GPIS_BROWSER_TEST_URL for application checks")
    playwright = pytest.importorskip("playwright.sync_api")
    previous = asyncio.get_event_loop_policy()
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(channel=os.getenv("GPIS_BROWSER_CHANNEL", "chrome"))
            page = browser.new_page(viewport={"width": request.param, "height": 844})
            page.goto(url, wait_until="networkidle")
            yield page, playwright.expect
            browser.close()
    finally:
        asyncio.set_event_loop_policy(previous)


@pytest.mark.parametrize("browser_page", [390, 1280], indirect=True)
def test_district_journey(browser_page, tmp_path):
    page, expect = browser_page
    search = page.locator("#district-query")
    search.fill("Multan")
    search.press("Enter")
    expect(page.locator("#district-name")).to_have_text("Multan")
    page.locator("#open-profile").click()
    expect(page.locator("#district-page")).to_be_visible()
    page.locator("[data-nav=compare]").click()
    page.locator("#compare-other").select_option("lahore")
    table = page.locator("#fact-comparison table").first
    expect(table.locator("thead")).to_contain_text("Multan")
    expect(table.locator("thead")).to_contain_text("Lahore")
    literacy = table.locator("tbody tr").first
    expect(literacy.locator("th")).to_contain_text("Total literacy")
    expect(literacy.locator("td").nth(0)).to_contain_text("61.41%")
    expect(literacy.locator("td").nth(1)).to_contain_text("79.62%")
    for i, cell in enumerate(("B1614", "B1284")):
        literacy.locator("td").nth(i).get_by_role("button").click()
        expect(page.locator(".highlight-cell").filter(has_text=cell)).to_be_visible()
        page.locator("#evidence-close").click()
    page.screenshot(path=str(tmp_path / "comparison.png"))
    page.locator("[data-nav=district]").click()
    representation = page.get_by_text("Constituency representation", exact=False).filter(has_text="published 2021").first
    representation.click()
    expect(page.locator("#historical-content details[open]")).to_contain_text("start date unverified", ignore_case=True)
    page.locator("#model-select").select_option("fallback")
    for district, number in (("Multan", "61.41"), ("Lahore", "79.6")):
        if district == "Lahore":
            page.locator("[data-nav=overview]").click()
            search.fill(district)
            search.press("Enter")
            page.locator("#open-profile").click()
        expect(page.locator("#district-name")).to_have_text(district)
        page.locator("#focus-chat").click()
        page.locator("#chat-question").fill("What is the total literacy rate?")
        with page.expect_response(lambda r: r.url.endswith("/api/v1/chat") and r.request.method == "POST", timeout=90000) as response:
            page.locator("#chat-submit").click()
        assert response.value.request.post_data_json["districts"] == [district.lower()]
        data = response.value.json()
        assert data["mode"] == "extractive" and data["citations"]
        answer = page.locator("#chat-answer")
        expect(answer).to_contain_text(district)
        expect(answer).to_contain_text(number)
        expect(answer.locator(".citation-preview").first).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
