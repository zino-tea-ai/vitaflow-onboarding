import asyncio
import os
import time
import uuid
from tempfile import TemporaryDirectory

import PIL.Image
from aioconsole import aprint
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext, Page, Playwright

from skillweaver.environment.a11y import capture_accessibility_tree
from skillweaver.environment.state import State

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"


def unique_id():
    return uuid.uuid4().hex


scount = 0


class Browser:
    def __init__(
        self,
        playwright_browser: PlaywrightBrowser,
        context: BrowserContext,
        active_page: Page,
        screen_size: tuple[int, int],
    ):
        """
        Use the `make_browser` helper method instead.
        """

        self.playwright_browser = playwright_browser
        self.context = context
        self.active_page = active_page
        self.temp_dir = TemporaryDirectory()
        self.dialog = None
        self.cdp_sessions = {}
        self.screen_size = screen_size

    async def _get_dom(self, page: Page):
        if page not in self.cdp_sessions:
            cdp = await self.context.new_cdp_session(page)
            self.cdp_sessions[page] = cdp
        else:
            cdp = self.cdp_sessions[page]
        dom_snapshot = await cdp.send(
            "DOMSnapshot.captureSnapshot",
            {
                "computedStyles": ["visibility", "display"],
                # Provides clientRect, scrollRect, etc.
                "includeDOMRects": True,
            },  # type: ignore (DOMSnapshot)
        )
        return dom_snapshot

    async def _screenshot(self, page: Page) -> tuple[PIL.Image.Image, PIL.Image.Image]:
        global scount
        assert (
            self.dialog is None
        ), "Cannot take any action while a dialog is open (action: screenshot)."

        # Returns the full and cropped screenshot paths
        scount += 1
        screenshot_path_full = os.path.join(
            self.temp_dir.name, f"screenshot_full{scount}.png"
        )
        screenshot_path = os.path.join(self.temp_dir.name, f"screenshot{scount}.png")
        await page.screenshot(full_page=True, path=screenshot_path_full, timeout=15000)
        await page.screenshot(full_page=False, path=screenshot_path, timeout=15000)
        
        # 读取图像并复制到内存，然后关闭文件句柄
        with PIL.Image.open(screenshot_path) as img:
            screenshot = img.copy()
        with PIL.Image.open(screenshot_path_full) as img_full:
            screenshot_full = img_full.copy()

        # 在 Windows 上需要等待文件句柄释放
        import sys
        if sys.platform == 'win32':
            import gc
            gc.collect()
            try:
                os.remove(screenshot_path_full)
            except PermissionError:
                pass  # 忽略 Windows 文件锁问题
            try:
                os.remove(screenshot_path)
            except PermissionError:
                pass
        else:
            os.remove(screenshot_path_full)
            os.remove(screenshot_path)

        return (screenshot, screenshot_full)

    async def _observe(self) -> State:
        await self.active_page.wait_for_load_state("load")
        return State(
            id=unique_id(),
            url=self.active_page.url,
            title=await self.active_page.title(),
            timestamp=time.time(),
            screenshot=(await self._screenshot(self.active_page))[0],  # BUG
            dom=await self._get_dom(self.active_page),
            dialog=self.dialog,
            accessibility_tree=await capture_accessibility_tree(self.active_page),
        )

    async def observe(self) -> State:
        exc = None
        for attempt in range(3):
            try:
                return await self._observe()
            except Exception as e:
                if (
                    "Execution context was destroyed, most likely because of a navigation"
                    in str(e)
                    and attempt < 2
                ):
                    await aprint("Page navigated after action completed. Retrying.")
                    await asyncio.sleep(2)
                    exc = e
                    continue
                else:
                    raise e

        raise exc  # type: ignore

    async def close(self):
        await self.active_page.close()
        await self.context.close()
        await self.playwright_browser.close()


async def make_browser(
    playwright: Playwright,
    start_url: str,
    storage_state: str | None = None,
    headless=True,
    width=1280,
    height=1440,
    # height=720, # NOTE
    locale="en-US",
    args=(),
    video_dir=None,
    navigation_timeout=16000,
    timeout=5000,
):
    browser = await playwright.chromium.launch(
        traces_dir=None,
        headless=headless,
        args=[
            "--incognito",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
            "--disable-features=CrossSiteDocumentBlockingAlways,CrossSiteDocumentBlockingIfIsolating",
            *args,
        ],
        chromium_sandbox=True if not os.getenv("DOCKER") else False,
        ignore_default_args=["--hide-scrollbars"],
    )
    context = await browser.new_context(
        storage_state=storage_state,
        user_agent=USER_AGENT,
        viewport={"width": width, "height": height},
        locale=locale,
        record_video_dir=video_dir,
        # record_har_path=har_path,
        # geolocation=geolocation,
    )
    context.set_default_timeout(timeout)
    context.set_default_navigation_timeout(navigation_timeout)
    # BUG in Playwright:
    page = await context.new_page()
    await page.goto(start_url)  # state_url
    content = await page.content()
    await aprint("went to", start_url)
    return Browser(browser, context, page, screen_size=(height, width))


async def make_browser_cdp(
    playwright: Playwright,
    cdp_url: str = "http://localhost:9222",
    target_url_filter: str = None,
    width=1280,
    height=720,
    timeout=5000,
    navigation_timeout=16000,
):
    """
    连接到已有浏览器实例（通过 CDP）
    用于连接 NogicOS 的内嵌 webview
    
    Args:
        playwright: Playwright 实例
        cdp_url: CDP 端点 URL，默认 http://localhost:9222
        target_url_filter: 目标页面 URL 过滤器（用于定位 webview）
        width: 视口宽度
        height: 视口高度
    
    Returns:
        Browser 实例
    """
    import urllib.request
    import json
    
    await aprint(f"[CDP] Connecting to {cdp_url}...")
    
    try:
        # 步骤1: 获取 CDP targets 列表，找到 webview 的 WebSocket URL
        webview_ws_url = None
        try:
            with urllib.request.urlopen(f"{cdp_url}/json", timeout=5) as response:
                targets = json.loads(response.read().decode())
                await aprint(f"[CDP] Found {len(targets)} targets")
                
                for target in targets:
                    target_type = target.get('type', '')
                    target_url = target.get('url', '')
                    ws_url = target.get('webSocketDebuggerUrl', '')
                    
                    await aprint(f"[CDP] Target: type={target_type}, url={target_url[:60] if target_url else 'N/A'}...")
                    
                    # 找 webview 类型或非 file:// 的页面
                    if target_type == 'webview':
                        webview_ws_url = ws_url
                        await aprint(f"[CDP] Found webview target: {target_url}")
                        break
                    elif target_type == 'page' and not target_url.startswith('file://'):
                        if target_url_filter is None or target_url_filter in target_url:
                            webview_ws_url = ws_url
                            await aprint(f"[CDP] Found matching page target: {target_url}")
                            break
        except Exception as e:
            await aprint(f"[CDP] Failed to get targets: {e}")
        
        if not webview_ws_url:
            await aprint("[CDP] No webview target found, falling back to browser connection")
            # 回退到原来的方式
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            contexts = browser.contexts
            if contexts and contexts[0].pages:
                page = contexts[0].pages[0]
                return Browser(browser, contexts[0], page, screen_size=(height, width))
            raise RuntimeError("No suitable webview page found")
        
        # 步骤2: 连接到浏览器，然后通过 CDP session 获取 webview 页面
        await aprint(f"[CDP] Connecting to browser and targeting webview...")
        
        # 连接到浏览器级别
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        await aprint("[CDP] Connected to browser")
        
        # 使用 CDP 直接连接到 webview target
        # 从 webview_ws_url 提取 target ID
        # 格式: ws://localhost:9222/devtools/page/TARGET_ID
        target_id = webview_ws_url.split('/')[-1]
        await aprint(f"[CDP] Target ID: {target_id}")
        
        # 创建新的 context 连接到 webview
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        context.set_default_timeout(timeout)
        context.set_default_navigation_timeout(navigation_timeout)
        
        # 尝试通过 CDP session 附加到 webview target
        try:
            cdp_session = await context.new_cdp_session(context.pages[0] if context.pages else None)
            # 获取所有 targets
            targets_result = await cdp_session.send("Target.getTargets")
            await aprint(f"[CDP] Targets: {len(targets_result.get('targetInfos', []))}")
            
            # 找到 webview target 并附加
            for target_info in targets_result.get('targetInfos', []):
                if target_info.get('type') == 'page' and target_info.get('targetId') == target_id:
                    await aprint(f"[CDP] Found target, attaching...")
                    attach_result = await cdp_session.send("Target.attachToTarget", {
                        "targetId": target_id,
                        "flatten": True
                    })
                    await aprint(f"[CDP] Attached: {attach_result}")
                    break
        except Exception as cdp_err:
            await aprint(f"[CDP] CDP session error (non-fatal): {cdp_err}")
        
        # 遍历所有页面找到 webview
        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                if not p.url.startswith('file://') and p.url != 'about:blank':
                    page = p
                    context = ctx
                    await aprint(f"[CDP] Found webview page: {p.url}")
                    break
            if page:
                break
        
        if not page:
            # 如果仍然找不到，使用第一个可用页面
            if browser.contexts and browser.contexts[0].pages:
                page = browser.contexts[0].pages[0]
                context = browser.contexts[0]
                await aprint(f"[CDP] Using fallback page: {page.url}")
            else:
                raise RuntimeError("No pages found")
        
        await aprint(f"[CDP] Final page URL: {page.url}")
        
        return Browser(browser, context, page, screen_size=(height, width))
        
    except Exception as e:
        await aprint(f"[CDP] Connection failed: {e}")
        raise


async def make_browsers(
    playwright: Playwright,
    start_urls: list[str],
    storage_states: list[str | None],
    headless=True,
    width=1280,
    height=1440,
    # height=720, # NOTE
    locale="en-US",
    args=(),
    video_dirs=None,
    navigation_timeout=16000,
    timeout=5000,
):
    browser = await playwright.chromium.launch(
        traces_dir=None,
        headless=headless,
        args=[
            "--incognito",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
            "--disable-features=CrossSiteDocumentBlockingAlways,CrossSiteDocumentBlockingIfIsolating",
            *args,
        ],
        chromium_sandbox=True if not os.getenv("DOCKER") else False,
        ignore_default_args=["--hide-scrollbars"],
    )

    async def __make(storage_state, start_url, video_dir):
        context = await browser.new_context(
            storage_state=storage_state,
            user_agent=USER_AGENT,
            viewport={"width": width, "height": height},
            locale=locale,
            record_video_dir=video_dir,
        )
        context.set_default_timeout(timeout)
        context.set_default_navigation_timeout(navigation_timeout)
        page = await context.new_page()
        await aprint("made new_page")
        await page.goto(start_url)
        await aprint("went to", start_url)
        return Browser(browser, context, page, screen_size=(height, width))

    return await asyncio.gather(
        *[
            __make(storage_state, start_url, video_dir)
            for storage_state, start_url, video_dir in zip(
                storage_states, start_urls, video_dirs or [None] * len(storage_states)
            )
        ]
    )
