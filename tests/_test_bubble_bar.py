# tests/_test_bubble_bar.py — 通过 Service Worker 设置 displayMode=bar 后测试收藏按钮
import time, pathlib, threading, http.server, socketserver
from playwright.sync_api import sync_playwright

EXT_PATH = str(pathlib.Path(__file__).resolve().parent.parent / 'extension')
TEST_HTML = '<html><body style="padding:40px;font-size:20px;"><p id="p1">Hello world test sentence.</p></body></html>'
PORT = 8767
httpd = socketserver.TCPServer(('127.0.0.1', PORT), http.server.SimpleHTTPRequestHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
pathlib.Path('tests/_bubble_test.html').write_text(TEST_HTML, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir='./tmp_profile_bubble3', headless=False,
        args=[f'--disable-extensions-except={EXT_PATH}', f'--load-extension={EXT_PATH}'],
        no_viewport=True,
    )
    time.sleep(4)

    # 找到扩展的 Service Worker
    sw = None
    for sw_candidate in browser.service_workers:
        url = sw_candidate.url
        if 'background.js' in url or 'chrome-extension' in url:
            sw = sw_candidate
            break
    print(f'Service Worker: {sw.url if sw else None}')

    if sw:
        # 在 Service Worker 上下文设置 displayMode=bar（能访问 chrome.storage）
        sw.evaluate('''() => new Promise(r => {
            chrome.storage.local.get('winocr_settings_v1', o => {
                const cur = o.winocr_settings_v1 || {};
                cur.displayMode = 'bar';
                chrome.storage.local.set({ winocr_settings_v1: cur }, () => r(true));
            });
        })''')
        print('已设置 displayMode=bar')
        time.sleep(1)

    page = browser.pages[0]
    page.goto(f'http://127.0.0.1:{PORT}/tests/_bubble_test.html')
    page.wait_for_load_state('domcontentloaded')
    time.sleep(2.5)

    # 模拟划词
    page.evaluate('''() => {
        const el = document.getElementById('p1');
        const range = document.createRange();
        range.selectNodeContents(el);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        const rect = el.getBoundingClientRect();
        el.dispatchEvent(new MouseEvent('mouseup', { bubbles:true, clientX:rect.left+10, clientY:rect.top+rect.height/2 }));
    }''')
    time.sleep(1)

    bubble = page.query_selector('.winocr-bubble')
    if bubble:
        cls = bubble.get_attribute('class')
        btns = [b.text_content() for b in bubble.query_selector_all('button')]
        print(f'气泡class: {cls}')
        print(f'按钮: {btns}')
        if '记录' in btns:
            print('[OK] 收藏按钮「记录」存在（bar 模式）')
        else:
            print('[FAIL] 收藏按钮「记录」缺失')
        page.screenshot(path='tests/bubble_bar.png')
    else:
        print('[FAIL] 无气泡')

    browser.close()
    httpd.shutdown()
