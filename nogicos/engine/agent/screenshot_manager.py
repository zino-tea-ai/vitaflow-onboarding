"""
NogicOS 截图内存管理
====================

防止截图导致的内存泄漏。

策略:
1. 压缩存储 (JPEG 85%)
2. LRU 淘汰
3. 内存上限控制
4. 延迟转换 base64

参考:
- Anthropic Computer Use 截图处理
- ByteBot 上下文压缩
"""

import base64
import uuid
import asyncio
import logging
import time
from io import BytesIO
from typing import Dict, Optional
from collections import OrderedDict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotEntry:
    """截图条目"""
    id: str
    data: bytes           # 压缩后的图片数据
    size: int             # 字节大小
    timestamp: float      # 创建时间
    hwnd: int             # 来源窗口
    width: int = 0        # 图片宽度
    height: int = 0       # 图片高度


class ScreenshotManager:
    """
    截图管理器 - 内存安全的截图存储
    
    特性:
    - 压缩存储，减少 50-70% 内存
    - LRU 淘汰策略
    - 内存上限控制
    - 按需转换 base64
    
    使用示例:
    ```python
    manager = get_screenshot_manager()
    
    # 存储截图
    screenshot_id = await manager.store(image_bytes, hwnd=12345)
    
    # 获取 base64（按需转换）
    base64_data = await manager.get_base64(screenshot_id)
    
    # 检查内存使用
    stats = manager.get_stats()
    print(f"Memory usage: {stats['total_size_mb']:.2f} MB")
    ```
    """
    
    # 默认配置
    MAX_MEMORY_MB = 50
    MAX_ENTRIES = 100
    JPEG_QUALITY = 85
    
    def __init__(self, max_memory_mb: int = None, max_entries: int = None):
        """
        初始化截图管理器
        
        Args:
            max_memory_mb: 最大内存使用 (MB)
            max_entries: 最大截图数量
        """
        self.max_memory_bytes = (max_memory_mb or self.MAX_MEMORY_MB) * 1024 * 1024
        self.max_entries = max_entries or self.MAX_ENTRIES
        
        self._cache: OrderedDict[str, ScreenshotEntry] = OrderedDict()
        self._total_size = 0
        self._lock = asyncio.Lock()
        
        # 统计
        self._store_count = 0
        self._evict_count = 0
    
    async def store(
        self, 
        image_data: bytes, 
        hwnd: int = 0,
        compress: bool = True,
    ) -> str:
        """
        存储截图
        
        Args:
            image_data: 原始图片数据 (PNG/BMP/JPEG)
            hwnd: 来源窗口句柄
            compress: 是否压缩 (默认 True)
            
        Returns:
            截图 ID
        """
        # 压缩图片
        if compress:
            compressed, width, height = await self._compress(image_data)
        else:
            compressed = image_data
            width, height = 0, 0
        
        screenshot_id = str(uuid.uuid4())[:8]
        entry = ScreenshotEntry(
            id=screenshot_id,
            data=compressed,
            size=len(compressed),
            timestamp=time.time(),
            hwnd=hwnd,
            width=width,
            height=height,
        )
        
        async with self._lock:
            # 添加到缓存
            self._cache[screenshot_id] = entry
            self._total_size += entry.size
            
            # 移动到末尾 (LRU)
            self._cache.move_to_end(screenshot_id)
            
            # 检查并淘汰
            await self._evict_if_needed()
            
            self._store_count += 1
        
        logger.debug(f"Screenshot stored: {screenshot_id} ({entry.size / 1024:.1f} KB)")
        return screenshot_id
    
    async def get_base64(self, screenshot_id: str) -> Optional[str]:
        """
        获取 base64 编码的截图
        
        按需转换，避免预先占用内存
        
        Args:
            screenshot_id: 截图 ID
            
        Returns:
            base64 编码的字符串，或 None
        """
        async with self._lock:
            entry = self._cache.get(screenshot_id)
            if not entry:
                return None
            
            # 更新 LRU 顺序
            self._cache.move_to_end(screenshot_id)
        
        return base64.b64encode(entry.data).decode('utf-8')
    
    async def get_raw(self, screenshot_id: str) -> Optional[bytes]:
        """获取原始压缩数据"""
        async with self._lock:
            entry = self._cache.get(screenshot_id)
            if entry:
                self._cache.move_to_end(screenshot_id)
                return entry.data
        return None
    
    async def get_entry(self, screenshot_id: str) -> Optional[ScreenshotEntry]:
        """获取完整的截图条目"""
        async with self._lock:
            entry = self._cache.get(screenshot_id)
            if entry:
                self._cache.move_to_end(screenshot_id)
                return entry
        return None
    
    async def delete(self, screenshot_id: str) -> bool:
        """删除截图"""
        async with self._lock:
            entry = self._cache.pop(screenshot_id, None)
            if entry:
                self._total_size -= entry.size
                logger.debug(f"Screenshot deleted: {screenshot_id}")
                return True
        return False
    
    async def delete_by_hwnd(self, hwnd: int) -> int:
        """删除指定窗口的所有截图"""
        async with self._lock:
            to_delete = [
                sid for sid, entry in self._cache.items()
                if entry.hwnd == hwnd
            ]
            
            for sid in to_delete:
                entry = self._cache.pop(sid)
                self._total_size -= entry.size
            
            return len(to_delete)
    
    async def _compress(self, image_data: bytes) -> tuple[bytes, int, int]:
        """
        压缩图片为 JPEG
        
        Returns:
            (compressed_data, width, height)
        """
        try:
            from PIL import Image
        except ImportError:
            logger.warning("PIL not installed, skipping compression")
            return image_data, 0, 0
        
        loop = asyncio.get_event_loop()
        
        def _do_compress():
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            
            # 转换为 RGB (JPEG 不支持 RGBA)
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 压缩为 JPEG
            output = BytesIO()
            img.save(output, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
            return output.getvalue(), width, height
        
        return await loop.run_in_executor(None, _do_compress)
    
    async def _evict_if_needed(self):
        """淘汰过期条目"""
        evicted = 0
        
        # 按数量淘汰
        while len(self._cache) > self.max_entries:
            oldest_id, oldest_entry = self._cache.popitem(last=False)
            self._total_size -= oldest_entry.size
            evicted += 1
        
        # 按内存淘汰
        while self._total_size > self.max_memory_bytes and self._cache:
            oldest_id, oldest_entry = self._cache.popitem(last=False)
            self._total_size -= oldest_entry.size
            evicted += 1
        
        if evicted > 0:
            self._evict_count += evicted
            logger.debug(f"Evicted {evicted} screenshots")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "count": len(self._cache),
            "total_size_mb": self._total_size / (1024 * 1024),
            "max_size_mb": self.max_memory_bytes / (1024 * 1024),
            "usage_percent": (self._total_size / self.max_memory_bytes * 100) if self.max_memory_bytes > 0 else 0,
            "store_count": self._store_count,
            "evict_count": self._evict_count,
        }
    
    async def clear(self):
        """清空所有截图"""
        async with self._lock:
            self._cache.clear()
            self._total_size = 0
            logger.info("Screenshot cache cleared")
    
    def get_recent(self, count: int = 5) -> list[str]:
        """获取最近的截图 ID 列表"""
        return list(self._cache.keys())[-count:]


# ========== 单例模式 ==========

_screenshot_manager: Optional[ScreenshotManager] = None


def get_screenshot_manager() -> ScreenshotManager:
    """获取全局截图管理器（单例）"""
    global _screenshot_manager
    if _screenshot_manager is None:
        _screenshot_manager = ScreenshotManager()
    return _screenshot_manager


def set_screenshot_manager(manager: ScreenshotManager):
    """设置全局截图管理器（用于测试）"""
    global _screenshot_manager
    _screenshot_manager = manager
