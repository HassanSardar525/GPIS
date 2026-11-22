"""Real browser evidence navigation, state preservation and accessible controls."""
import asyncio
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def event_loop_policy():
    previous=asyncio.get_event_loop_policy()
    if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    yield
    asyncio.set_event_loop_policy(previous)


def test_history_and_evidence_browser(tmp_path):
    url=os.getenv('GPIS_BROWSER_TEST_URL')
    if not url:pytest.skip('Set GPIS_BROWSER_TEST_URL for live browser checks')
    playwright=pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch(channel=os.getenv('GPIS_BROWSER_CHANNEL','chrome'),headless=True)
        page=browser.new_page(viewport={'width':1280,'height':900})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url+'/#/district/multan',wait_until='networkidle')
        expect=playwright.expect
        expect(page.locator('#historical-content')).to_contain_text('Change across multiple administrations')
        expect(page.locator('#historical-content tbody tr')).to_have_count(2)
        page.locator('#chat-question').fill('Keep this draft while reading the evidence')
        session=page.evaluate("state.sessionId")
        point=page.locator('.history-point').first
        point.focus();point.press('Enter')
        expect(page.locator('#evidence-panel')).to_be_visible()
        expect(page.locator('#evidence-page-label')).to_contain_text('PDF page 22 · printed page 7')
        expect(page.locator('.evidence-highlight')).to_have_count(1)
        expect(page.locator('#evidence-text')).to_contain_text('22 institutions')
        page.locator('#evidence-zoom').fill('150')
        page.screenshot(path=str(tmp_path/'scan-evidence.png'))
        deep=page.url
        page.keyboard.press('Escape')
        expect(page.locator('#evidence-panel')).not_to_be_visible()
        expect(page.locator('#chat-question')).to_have_value('Keep this draft while reading the evidence')
        page.locator('[data-tenure="naqvi-2023"]').click()
        expect(page.locator('.history-result')).to_contain_text('Insufficient evidence')
        expect(page.locator('.selected-point')).to_have_count(1)
        page.locator('[data-tenure=""]').click()
        page.locator('[data-history-category="spending"]').click()
        expect(page.locator('.history-result')).to_contain_text('Change across multiple administrations')
        expect(page.locator('.history-result')).to_contain_text('Maryam Nawaz')
        page.locator('.history-point').first.click()
        expect(page.locator('#evidence-page-label')).to_contain_text('PDF page 26 · printed page 15')
        expect(page.locator('.evidence-highlight')).to_have_count(2)
        page.screenshot(path=str(tmp_path/'budget-evidence.png'))
        page.locator('#evidence-close').click()
        page.locator('[data-history-category="education"]').click()
        expect(page.locator('.history-point')).to_have_count(1)
        page.locator('.history-point').click()
        expect(page.locator('.highlight-cell')).to_have_count(1)
        expect(page.locator('.highlight-cell')).to_contain_text('B1614')
        page.locator('#evidence-close').click()
        page.locator('#chat-question').fill('Who was chief minister during the change in Multan hospital numbers?')
        page.locator('#model-select').select_option('fallback')
        page.locator('#chat-form button[type=submit]').click()
        expect(page.locator('#chat-answer')).to_contain_text('Parvez Elahi')
        page.locator('#chat-answer [data-evidence]').first.click()
        expect(page.locator('#evidence-panel')).to_be_visible()
        page.locator('#evidence-close').click()
        assert page.evaluate("localStorage.getItem('gpis.sessionId')")==session
        expect(page.locator('#chat-answer')).to_contain_text('Parvez Elahi')
        assert page.evaluate('''() => {
            const el=document.createElement('div');
            el.innerHTML=renderAnswerWithEvidence('<img src=x onerror=alert(1)> [known]', [{evidence_id:'known',anchor_ids:['safe']}]);
            return !el.querySelector('img') && el.textContent.includes('<img') && el.querySelector('button').dataset.evidence==='safe';
        }''')
        page.goto(deep,wait_until='networkidle')
        expect(page.locator('#district-name')).to_have_text('Multan')
        expect(page.locator('#evidence-panel')).to_be_visible()
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(tmp_path/'evidence-mobile.png'))
        page.keyboard.press('Escape')
        expect(page.locator('#evidence-panel')).not_to_be_visible()
        assert not errors,errors
        browser.close()
