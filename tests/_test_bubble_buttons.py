# tests/_test_bubble_buttons.py — Playwright 自动化测试划词气泡（翻译 + 收藏按钮）
import time, sys, pathlib, threading, http.server, socketserver
from playwright.sync_api import sync_playwright

EXT_PATH = str(pathlib.Path(__file__).resolve().parent.parent / 'extension')

TEST_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body style="padding:40px;font-size:20px;">
<p id="p1">Hello, world. This is a test sentence for translation.</p>
<p id="p2">你好，世界。这是用于翻译测试的中文句子。</p>
</body></html>"""

# 启动一个临时 HTTP 服务器提供测试页
PORT = 8765
handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, **k)
httpd = socketserver.TCPServer(('127.0.0.1', PORT), handler)
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()
# 把测试页写到一个文件供服务器提供
pathlib.Path('tests/_bubble_test.html').write_text(TEST_HTML, encoding='utf-8')

def log(m): print(m, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir='./tmp_profile_bubble',
        headless=False,
        args=[
            f'--disable-extensions-except={EXT_PATH}',
            f'--load-extension={EXT_PATH}',
        ],
        no_viewport=True,
    )
    pages = browser.pages
    page = pages[0] if pages else browser.new_page()

    log('等待扩展加载…')
    time.sleep(4)

    page.goto(f'http://127.0.0.1:{PORT}/tests/_bubble_test.html')
    page.wait_for_load_state('domcontentloaded')
    time.sleep(2)  # content script 注入

    # 用 JS 精确模拟选中 + 触发 mouseup（Playwright mouse 事件在部分站点不触发 selection）
    def select_and_bubble(sel_id):
        page.evaluate(f'''() => {{
            const el = document.getElementById("{sel_id}");
            const range = document.createRange();
            range.selectNodeContents(el);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            const rect = el.getBoundingClientRect();
            const ev = new MouseEvent('mouseup', {{
                bubbles: true, cancelable: true,
                clientX: rect.left + 10, clientY: rect.top + rect.height/2
            }});
            el.dispatchEvent(ev);
        }}''')
        time.sleep(0.5)

    log('模拟划词（英文）…')
    select_and_bubble('p1')

    try:
        page.wait_for_selector('.winocr-bubble', timeout=4000)
        bubble = page.locator('.winocr-bubble').first
        buttons = bubble.locator('button').all_text_contents()
        log(f'[OK] inline 模式气泡弹出，按钮: {buttons}')
        log(f'{"[OK] 翻译按钮「译」存在" if "译" in buttons else "[FAIL] 翻译按钮「译」缺失"}')
        log(f'{"[OK] 收藏按钮「记录」存在" if "记录" in buttons else "[INFO] inline 模式无收藏按钮"}')
        page.screenshot(path='tests/bubble_inline.png')
        log('已截图 tests/bubble_inline.png')
    except Exception as e:
        log(f'[FAIL] 气泡未弹出: {e}')
        # 检查 content script 是否注入
        has_w = page.evaluate('typeof WINOCR')
        log(f'content script 注入状态: WINOCR = {has_w}')

    # 切到 bar 模式
    log('\n切换到 bar 模式…')
    page.evaluate('''() => new Promise(r => {
        if (chrome && chrome.storage && chrome.storage.local)
            chrome.storage.local.set({ winocr_settings_v1: { displayMode: 'bar' } }, () => r(true));
        else r(false);
    })''')
    time.sleep(1)
    page.reload()
    page.wait_for_load_state('domcontentloaded')
    time.sleep(2)

    log('模拟划词（bar 模式）…')
    select_and_bubble('p1')

    try:
        page.wait_for_selector('.winocr-bubble', timeout=4000)
        bubble = page.locator('.winocr-bubble').first
        buttons = bubble.locator('button').all_text_contents()
        log(f'[OK] bar 模式气泡弹出，按钮: {buttons}')
        log(f'{"[OK] 收藏按钮「记录」存在" if "记录" in buttons else "[FAIL] 收藏按钮「记录」缺失"}')
        page.screenshot(path='tests/bubble_bar.png')
        log('已截图 tests/bubble_bar.png')
    except Exception as e:
        log(f'[FAIL] bar 模式气泡未弹出: {e}')

    time.sleep(2)
    browser.close()
    httpd.shutdown()
    log('测试结束')
