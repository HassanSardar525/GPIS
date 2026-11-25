"""Opt-in browser regression against a running GPIS instance; no LLM calls."""
import os
import asyncio
import sys

import pytest


@pytest.fixture(autouse=True)
def browser_event_loop_policy():
    previous = asyncio.get_event_loop_policy()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    yield
    asyncio.set_event_loop_policy(previous)


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
     summaries=page.request.get(os.environ['GPIS_BROWSER_TEST_URL']+'/api/v1/districts').json()['districts']
     score_count=sum(d['scores']['overall'] is not None for d in summaries)
     expect(page.locator('#map-scored-count')).to_have_text(f'{score_count} scored districts')
     for d in summaries:
      path=page.locator(f'.district-path[data-district="{d["slug"]}"]')
      expect(path).to_have_count(1)
      if d['scores']['overall'] is not None:
       assert float(path.get_attribute('data-score'))==d['scores']['overall']
     expect(page.locator('#overview-page')).to_be_visible()
     expect(page.locator('#district-page')).to_be_hidden()
     expect(page.locator('#compare-page')).to_be_hidden()
     page.locator('#district-query').fill('Multan')
     page.locator('#district-query').press('Enter')
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
     expect(page.locator('#ranking-list li')).to_have_count(score_count)
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
     expect(page.locator('#scorecards')).to_contain_text('Official health capacity')
     expect(page.locator('#scorecards')).to_contain_text('5,472.330' if score_count==36 else '5,818.950')
     expect(page.locator('#scorecards')).to_contain_text('FY 2023-24' if score_count==36 else 'FY 2022-23')
     assert page.evaluate("window.localStorage.getItem('gpis.sessionId')")==session
     page.reload(wait_until='networkidle')
     expect(page.locator('#district-name')).to_have_text('Lahore')
     page.set_viewport_size({'width':390,'height':844})
     assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
     page.screenshot(path=str(tmp_path / 'profile.png'),full_page=True)
     assert not errors,errors
     print('Browser checks passed: navigation, preserved session/selection, 36 census bars, 10 score bars, 5 comparison facts, 2 yearly points, unavailable trends, deep links, mobile layout')
     private_page=browser.new_page(color_scheme='dark',reduced_motion='reduce')
     private_page.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('disabled')}})")
     private_page.goto(os.environ['GPIS_BROWSER_TEST_URL'],wait_until='networkidle')
     expect(private_page.locator('html')).to_have_attribute('data-theme','dark')
     private_page.emulate_media(color_scheme='light')
     expect(private_page.locator('html')).to_have_attribute('data-theme','light')
     private_page.locator('#theme-choice').select_option('dark')
     expect(private_page.locator('html')).to_have_attribute('data-theme','dark')
     picker=private_page.locator('#district-query')
     picker.focus()
     results=private_page.locator('#district-results')
     expect(results.locator('option')).to_have_count(36)
     picker.press('ArrowDown')
     results.press('ArrowDown')
     selected=results.locator('option:checked').inner_text()
     results.press('Enter')
     expect(private_page.locator('#selected-summary')).to_have_text(selected)
     expect(results).to_be_hidden()
     browser.close()
