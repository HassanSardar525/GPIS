"""Opt-in browser regression against a running GPIS instance; no LLM calls."""
import os

import pytest


def test_workspace_navigation_and_charts(tmp_path):
    if not os.getenv('GPIS_BROWSER_TEST_URL'):
        pytest.skip('Set GPIS_BROWSER_TEST_URL to test a running app')
    playwright = pytest.importorskip('playwright.sync_api')
    sync_playwright, expect = playwright.sync_playwright, playwright.expect
    with sync_playwright() as p:
     browser=p.chromium.launch(channel=os.getenv('GPIS_BROWSER_CHANNEL', 'chrome'),headless=True)
     page=browser.new_page(viewport={'width':1280,'height':900})
     errors=[]
     page.on('pageerror',lambda error:errors.append(str(error)))
     page.goto(os.environ['GPIS_BROWSER_TEST_URL'],wait_until='networkidle')
     expect(page.locator('#district-select option')).to_have_count(36)
     expect(page.locator('#overview-page')).to_be_visible()
     expect(page.locator('#district-page')).to_be_hidden()
     expect(page.locator('#compare-page')).to_be_hidden()
     page.locator('#district-select').select_option('multan')
     expect(page.locator('#district-name')).to_have_text('Multan')
     page.locator('#open-profile').click()
     expect(page.locator('#district-page')).to_be_visible()
     expect(page.locator('#chat-form')).to_be_visible()
     session=page.evaluate("window.localStorage.getItem('gpis.sessionId')")
     page.locator('[data-nav=compare]').click()
     expect(page.locator('#compare-page')).to_be_visible()
     expect(page.locator('#chat-form')).to_be_hidden()
     expect(page.locator('#ranking-list .census-bar')).to_have_count(36)
     expect(page.locator('#fact-comparison tbody tr')).to_have_count(5)
     expect(page.locator('#year-chart svg')).to_be_visible()
     expect(page.locator('#year-chart tbody tr')).to_have_count(2)
     page.locator('#ranking-category').select_option('overall')
     expect(page.locator('#ranking-list li')).to_have_count(10)
     page.locator('#ranking-category').select_option('census:population_2023')
     expect(page.locator('#ranking-list .census-bar')).to_have_count(36)
     page.set_viewport_size({'width':661,'height':598})
     page.screenshot(path=str(tmp_path / 'compare.png'),full_page=True)
     page.locator('#district-select').select_option('lahore')
     expect(page.locator('#district-name')).to_have_text('Lahore')
     expect(page.locator('#trend-change')).to_have_text('Unavailable')
     expect(page.locator('#year-chart svg')).to_have_count(0)
     page.locator('[data-nav=district]').click()
     expect(page.locator('#chat-form')).to_be_visible()
     assert page.evaluate("window.localStorage.getItem('gpis.sessionId')")==session
     page.reload(wait_until='networkidle')
     expect(page.locator('#district-name')).to_have_text('Lahore')
     page.set_viewport_size({'width':390,'height':844})
     assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
     page.screenshot(path=str(tmp_path / 'profile.png'),full_page=True)
     assert not errors,errors
     print('Browser checks passed: navigation, preserved session/selection, 36 census bars, 10 score bars, 5 comparison facts, 2 yearly points, unavailable trends, deep links, mobile layout')
     browser.close()
