# -*- coding: utf-8 -*-
"""
NogicOS Playwright Executor - 使用 Playwright 进行浏览器自动化

与 Cursor 的 Playwright MCP 能力一致：
- 连接到已有 Chrome（通过 Hook 系统 + CDP）
- 获取页面快照（accessibility tree）
- 点击、输入、滚动等操作
- 执行 JavaScript 代码
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Playwright 导入
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("[Playwright] playwright not installed. Run: pip install playwright && playwright install")


@dataclass
class PlaywrightSnapshot:
    """页面快照结果"""
    url: str
    title: str
    snapshot_yaml: str  # Accessibility tree in YAML format
    elements: List[Dict[str, Any]]  # Parsed elements with refs


class NogicPlaywrightExecutor:
    """
    NogicOS Playwright 执行器
    
    能力：
    - 通过 CDP 连接到已 Hook 的 Chrome
    - 获取页面 accessibility snapshot（和 Cursor MCP 一样）
    - 执行各种浏览器操作
    """
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._connected = False
        self._cdp_url = "http://localhost:9222"
    
    async def connect(self, cdp_url: str = "http://localhost:9222") -> bool:
        """
        连接到已打开的 Chrome（通过 CDP）
        
        Args:
            cdp_url: Chrome DevTools Protocol URL
            
        Returns:
            是否连接成功
        """
        # #region agent log
        import json as _json
        with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
            _f.write(_json.dumps({"location":"playwright_executor.py:connect","message":"connect() called","data":{"cdp_url":cdp_url,"playwright_available":PLAYWRIGHT_AVAILABLE},"timestamp":__import__("time").time()*1000,"hypothesisId":"A"}) + "\n")
        # #endregion
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("[Playwright] playwright not available")
            return False
        
        try:
            self._cdp_url = cdp_url
            self._playwright = await async_playwright().start()
            
            # #region agent log
            with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                _f.write(_json.dumps({"location":"playwright_executor.py:connect","message":"playwright started, connecting to CDP","data":{"cdp_url":cdp_url},"timestamp":__import__("time").time()*1000,"hypothesisId":"A"}) + "\n")
            # #endregion
            
            # 连接到已有的 Chrome
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            
            # #region agent log
            with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                _f.write(_json.dumps({"location":"playwright_executor.py:connect","message":"CDP connected","data":{"browser":str(self._browser),"contexts_count":len(self._browser.contexts) if self._browser else 0},"timestamp":__import__("time").time()*1000,"hypothesisId":"C"}) + "\n")
            # #endregion
            
            # 获取现有的 context 和 page
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                
                # #region agent log
                with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                    _f.write(_json.dumps({"location":"playwright_executor.py:connect","message":"got contexts and pages","data":{"contexts_count":len(contexts),"pages_count":len(pages),"page_url":pages[0].url if pages else None},"timestamp":__import__("time").time()*1000,"hypothesisId":"C"}) + "\n")
                # #endregion
                
                if pages:
                    self._page = pages[0]  # 使用第一个页面
            
            self._connected = True
            logger.info(f"[Playwright] Connected to Chrome via CDP: {cdp_url}")
            return True
            
        except Exception as e:
            # #region agent log
            with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                _f.write(_json.dumps({"location":"playwright_executor.py:connect","message":"connect failed","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":__import__("time").time()*1000,"hypothesisId":"A"}) + "\n")
            # #endregion
            logger.error(f"[Playwright] Failed to connect: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._browser:
            # 只断开连接，不关闭浏览器
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._connected = False
        logger.info("[Playwright] Disconnected")
    
    async def get_snapshot(self) -> Optional[PlaywrightSnapshot]:
        """
        获取当前页面的快照（通过 JavaScript 提取表单元素）
        
        由于 CDP 连接的 Page 没有 accessibility 属性，改用 JS 提取
        """
        # #region agent log
        import json as _json
        with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
            _f.write(_json.dumps({"location":"playwright_executor.py:get_snapshot","message":"get_snapshot() called","data":{"connected":self._connected,"has_page":self._page is not None},"timestamp":__import__("time").time()*1000,"hypothesisId":"D"}) + "\n")
        # #endregion
        
        if not self._connected or not self._page:
            logger.error("[Playwright] Not connected")
            return None
        
        try:
            # #region agent log
            import json as _json2
            with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                _f.write(_json2.dumps({"location":"playwright_executor.py:get_snapshot","message":"using JS to extract page elements","data":{"page_url":self._page.url},"timestamp":__import__("time").time()*1000,"hypothesisId":"E1"}) + "\n")
            # #endregion
            
            # 使用 JavaScript 提取页面元素（替代 accessibility.snapshot）
            js_extract = """
            () => {
                const elements = [];
                let refCounter = 0;
                
                // 提取所有输入元素
                document.querySelectorAll('input, textarea, select, button, a, [role="button"], [role="textbox"]').forEach(el => {
                    const ref = 'e' + refCounter++;
                    const rect = el.getBoundingClientRect();
                    
                    // 跳过不可见元素
                    if (rect.width === 0 || rect.height === 0) return;
                    
                    const label = el.labels?.[0]?.textContent?.trim() || 
                                  el.getAttribute('aria-label') || 
                                  el.getAttribute('placeholder') ||
                                  el.closest('label')?.textContent?.trim() ||
                                  '';
                    
                    elements.push({
                        ref: ref,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        label: label.slice(0, 100),
                        value: el.value || '',
                        role: el.getAttribute('role') || el.tagName.toLowerCase(),
                        placeholder: el.placeholder || '',
                        isEmpty: !el.value || el.value.trim() === '',
                        selector: el.id ? '#' + el.id : (el.name ? `[name="${el.name}"]` : null)
                    });
                });
                
                return elements;
            }
            """
            
            elements_data = await self._page.evaluate(js_extract)
            
            # #region agent log
            with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                _f.write(_json2.dumps({"location":"playwright_executor.py:get_snapshot","message":"JS extraction completed","data":{"elements_count":len(elements_data) if elements_data else 0},"timestamp":__import__("time").time()*1000,"hypothesisId":"E1"}) + "\n")
            # #endregion
            
            # 转换为 YAML 格式
            yaml_lines = []
            elements = []
            
            for el in (elements_data or []):
                ref = el.get('ref', '')
                role = el.get('role', 'input')
                label = el.get('label', '')
                value = el.get('value', '')
                
                # 构建 YAML 行
                line_parts = [f"- {role}"]
                if label:
                    line_parts.append(f' "{label}"')
                if value:
                    line_parts.append(f': "{value[:50]}"')
                line_parts.append(f" [ref={ref}]")
                
                yaml_lines.append("".join(line_parts))
                elements.append(el)
            
            return PlaywrightSnapshot(
                url=self._page.url,
                title=await self._page.title(),
                snapshot_yaml="\n".join(yaml_lines),
                elements=elements,
            )
            
        except Exception as e:
            # #region agent log
            import json as _json3
            import traceback
            with open(r"c:\Users\TE\532-CorporateHell-Git\nogicos\.cursor\debug.log", "a") as _f:
                _f.write(_json3.dumps({"location":"playwright_executor.py:get_snapshot","message":"EXCEPTION in get_snapshot","data":{"error":str(e),"error_type":type(e).__name__,"traceback":traceback.format_exc()[:500]},"timestamp":__import__("time").time()*1000,"hypothesisId":"E1"}) + "\n")
            # #endregion
            logger.error(f"[Playwright] Snapshot failed: {e}")
            return None
    
    async def click(self, ref: str, element_description: str = "") -> bool:
        """
        点击元素
        
        Args:
            ref: 元素引用（如 "e12"）或选择器
            element_description: 元素描述（用于日志）
        """
        if not self._connected or not self._page:
            return False
        
        try:
            # 获取当前快照以查找元素
            snapshot = await self.get_snapshot()
            if not snapshot:
                return False
            
            # 在元素列表中查找匹配的 ref
            target_element = None
            for el in snapshot.elements:
                if el.get('ref') == ref:
                    target_element = el
                    break
            
            if target_element:
                selector = target_element.get('selector')
                if selector:
                    await self._page.locator(selector).click()
                    logger.info(f"[Playwright] Clicked: {element_description or selector}")
                    return True
                
                # 尝试通过 label 点击
                label = target_element.get('label', '')
                if label:
                    await self._page.get_by_text(label).click()
                    logger.info(f"[Playwright] Clicked: {element_description or label}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[Playwright] Click failed: {e}")
            return False
    
    async def type_text(self, ref: str, text: str, element_description: str = "") -> bool:
        """
        在元素中输入文本
        
        Args:
            ref: 元素引用（如 "e12"）或选择器
            text: 要输入的文本
            element_description: 元素描述
        """
        if not self._connected or not self._page:
            return False
        
        try:
            # 获取当前快照以查找元素
            snapshot = await self.get_snapshot()
            if not snapshot:
                return False
            
            # 在元素列表中查找匹配的 ref
            target_element = None
            for el in snapshot.elements:
                if el.get('ref') == ref:
                    target_element = el
                    break
            
            if target_element:
                selector = target_element.get('selector')
                if selector:
                    await self._page.locator(selector).fill(text)
                    logger.info(f"[Playwright] Typed into: {element_description or selector}")
                    return True
                
                # 尝试通过 name 定位
                name = target_element.get('name')
                if name:
                    await self._page.locator(f"[name='{name}']").fill(text)
                    logger.info(f"[Playwright] Typed into: {element_description or name}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[Playwright] Type failed: {e}")
            return False
    
    async def evaluate(self, script: str) -> Any:
        """
        执行 JavaScript 代码
        
        Args:
            script: JavaScript 代码
            
        Returns:
            执行结果
        """
        if not self._connected or not self._page:
            return None
        
        try:
            result = await self._page.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"[Playwright] Evaluate failed: {e}")
            return None
    
    async def navigate(self, url: str) -> bool:
        """导航到 URL"""
        if not self._connected or not self._page:
            return False
        
        try:
            await self._page.goto(url)
            logger.info(f"[Playwright] Navigated to: {url}")
            return True
        except Exception as e:
            logger.error(f"[Playwright] Navigate failed: {e}")
            return False
    
    async def find_empty_fields(self) -> List[Dict[str, Any]]:
        """
        查找页面上的空白表单字段
        
        Returns:
            空白字段列表，每个包含 label, ref, placeholder
        """
        if not self._connected or not self._page:
            return []
        
        try:
            # 执行 JavaScript 查找空白字段
            result = await self._page.evaluate("""
                () => {
                    const textboxes = document.querySelectorAll('input[type="text"], textarea');
                    const emptyFields = [];
                    textboxes.forEach((field, index) => {
                        const value = field.value || field.textContent || '';
                        const label = field.closest('[class]')?.previousElementSibling?.textContent || 
                                     field.getAttribute('name') || 
                                     field.getAttribute('placeholder') || 
                                     `Field ${index}`;
                        if (value.trim() === '' || value.trim() === 'https://') {
                            emptyFields.push({
                                label: label.substring(0, 100),
                                placeholder: field.placeholder || '',
                                value: value,
                                tagName: field.tagName,
                                name: field.name || '',
                            });
                        }
                    });
                    return emptyFields;
                }
            """)
            
            logger.info(f"[Playwright] Found {len(result)} empty fields")
            return result
            
        except Exception as e:
            logger.error(f"[Playwright] Find empty fields failed: {e}")
            return []
    
    async def fill_field_by_label(self, label_contains: str, text: str) -> bool:
        """
        根据 label 填写字段
        
        Args:
            label_contains: label 包含的文本
            text: 要填写的内容
        """
        if not self._connected or not self._page:
            return False
        
        try:
            # 使用更智能的定位策略
            # 1. 尝试找到包含特定文本的 label，然后找到对应的 input/textarea
            result = await self._page.evaluate(f"""
                (labelText) => {{
                    // 查找所有可能的容器
                    const containers = document.querySelectorAll('div, section, fieldset');
                    for (const container of containers) {{
                        const text = container.textContent || '';
                        if (text.includes(labelText)) {{
                            // 在这个容器中查找 textarea 或 input
                            const field = container.querySelector('textarea, input[type="text"]');
                            if (field && (field.value.trim() === '' || field.value.trim() === 'https://')) {{
                                return {{
                                    found: true,
                                    tagName: field.tagName.toLowerCase(),
                                    name: field.name || '',
                                }};
                            }}
                        }}
                    }}
                    return {{ found: false }};
                }}
            """, label_contains)
            
            if result.get('found'):
                # 使用 Playwright 的 label 定位
                if result.get('name'):
                    locator = self._page.locator(f"textarea[name='{result['name']}'], input[name='{result['name']}']")
                else:
                    locator = self._page.get_by_label(label_contains, exact=False)
                
                await locator.fill(text)
                logger.info(f"[Playwright] Filled field: {label_contains}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[Playwright] Fill field failed: {e}")
            return False
    
    def _find_element_by_ref(self, snapshot: Dict, target_ref: str, current_ref: List[int] = None) -> Optional[Dict]:
        """递归查找元素"""
        if current_ref is None:
            current_ref = [0]
        
        if not snapshot:
            return None
        
        ref = f"e{current_ref[0]}"
        current_ref[0] += 1
        
        if ref == target_ref:
            return snapshot
        
        for child in snapshot.get('children', []):
            result = self._find_element_by_ref(child, target_ref, current_ref)
            if result:
                return result
        
        return None


# 全局单例
_executor: Optional[NogicPlaywrightExecutor] = None


def get_playwright_executor() -> NogicPlaywrightExecutor:
    """获取 Playwright 执行器单例"""
    global _executor
    if _executor is None:
        _executor = NogicPlaywrightExecutor()
    return _executor


def register_playwright_tools(registry):
    """
    注册 Playwright 工具到 NogicOS
    
    这些工具与 Cursor Playwright MCP 的能力一致
    """
    from .base import ToolCategory
    
    @registry.action(
        description="""Get accessibility snapshot of the current page (like Cursor MCP browser_snapshot).
        
This returns a YAML-like structure of all interactive elements on the page.
Each element has a 'ref' that can be used for click/type operations.

Use this to:
- Understand what's on the page
- Find form fields to fill
- Locate buttons to click

Note: hwnd parameter is optional and ignored (Playwright uses CDP connection instead).""",
        category=ToolCategory.BROWSER,
    )
    async def playwright_snapshot(hwnd: str = None) -> Dict[str, Any]:
        """Get page accessibility snapshot. hwnd is optional and ignored."""
        executor = get_playwright_executor()
        
        if not executor._connected:
            # 尝试连接
            success = await executor.connect()
            if not success:
                return {
                    "success": False,
                    "error": "Failed to connect to Chrome. Make sure Chrome is running with --remote-debugging-port=9222"
                }
        
        snapshot = await executor.get_snapshot()
        if snapshot:
            return {
                "success": True,
                "url": snapshot.url,
                "title": snapshot.title,
                "snapshot": snapshot.snapshot_yaml,
                "element_count": len(snapshot.elements),
            }
        else:
            return {
                "success": False,
                "error": "Failed to get snapshot"
            }
    
    @registry.action(
        description="""Click an element on the page.
        
Args:
    element_description: Human-readable description of what to click
    ref: Element reference from snapshot (e.g. 'e12')""",
        category=ToolCategory.BROWSER,
    )
    async def playwright_click(element_description: str, ref: str) -> Dict[str, Any]:
        """Click an element"""
        executor = get_playwright_executor()
        
        if not executor._connected:
            return {"success": False, "error": "Not connected to browser"}
        
        success = await executor.click(ref, element_description)
        return {
            "success": success,
            "message": f"Clicked: {element_description}" if success else "Click failed"
        }
    
    @registry.action(
        description="""Type text into an input field.
        
Args:
    element_description: Human-readable description of the field
    ref: Element reference from snapshot
    text: Text to type""",
        category=ToolCategory.BROWSER,
    )
    async def playwright_type(element_description: str, ref: str, text: str) -> Dict[str, Any]:
        """Type text into element"""
        executor = get_playwright_executor()
        
        if not executor._connected:
            return {"success": False, "error": "Not connected to browser"}
        
        success = await executor.type_text(ref, text, element_description)
        return {
            "success": success,
            "message": f"Typed into: {element_description}" if success else "Type failed"
        }
    
    @registry.action(
        description="""Find all empty form fields on the current page.
        
Returns a list of empty fields with their labels.""",
        category=ToolCategory.BROWSER,
    )
    async def playwright_find_empty_fields() -> Dict[str, Any]:
        """Find empty form fields"""
        executor = get_playwright_executor()
        
        if not executor._connected:
            success = await executor.connect()
            if not success:
                return {"success": False, "error": "Not connected to browser"}
        
        fields = await executor.find_empty_fields()
        return {
            "success": True,
            "empty_fields": fields,
            "count": len(fields),
        }
    
    @registry.action(
        description="""Fill a form field by its label text.
        
Args:
    label_contains: Text that the field's label contains
    text: Text to fill in""",
        category=ToolCategory.BROWSER,
    )
    async def playwright_fill_by_label(label_contains: str, text: str) -> Dict[str, Any]:
        """Fill field by label"""
        executor = get_playwright_executor()
        
        if not executor._connected:
            return {"success": False, "error": "Not connected to browser"}
        
        success = await executor.fill_field_by_label(label_contains, text)
        return {
            "success": success,
            "message": f"Filled field containing '{label_contains}'" if success else "Fill failed"
        }
    
    @registry.action(
        description="""Execute JavaScript on the page.
        
Args:
    script: JavaScript code to execute (as a function body)""",
        category=ToolCategory.BROWSER,
    )
    async def playwright_evaluate(script: str) -> Dict[str, Any]:
        """Execute JavaScript"""
        executor = get_playwright_executor()
        
        if not executor._connected:
            return {"success": False, "error": "Not connected to browser"}
        
        result = await executor.evaluate(script)
        return {
            "success": True,
            "result": result,
        }
    
    logger.info("[Playwright] Playwright tools registered")


# 测试函数
async def test_playwright():
    """测试 Playwright 执行器"""
    executor = NogicPlaywrightExecutor()
    
    # 连接到 Chrome
    connected = await executor.connect("http://localhost:9222")
    print(f"Connected: {connected}")
    
    if connected:
        # 获取快照
        snapshot = await executor.get_snapshot()
        if snapshot:
            print(f"URL: {snapshot.url}")
            print(f"Title: {snapshot.title}")
            print(f"Elements: {len(snapshot.elements)}")
            print("Snapshot:")
            print(snapshot.snapshot_yaml[:500])
        
        # 查找空白字段
        empty = await executor.find_empty_fields()
        print(f"Empty fields: {empty}")
        
        await executor.disconnect()


if __name__ == "__main__":
    asyncio.run(test_playwright())
