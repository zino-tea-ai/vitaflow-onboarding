# -*- coding: utf-8 -*-
"""
NogicOS Health Checks
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class HealthResult:
    """Health check result"""
    module: str
    status: str  # healthy, unhealthy, degraded
    latency_ms: float = 0.0
    error: Optional[str] = None


class HealthChecker:
    """System health checker"""
    
    async def check_all(self) -> dict:
        """Check all modules"""
        results = {
            "hive": await self.check_hive(),
            "browser": await self.check_browser(),
            "knowledge": await self.check_knowledge(),
        }
        
        statuses = [r.status for r in results.values()]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"
        
        return {
            "overall": overall,
            "modules": {k: {"status": v.status, "error": v.error} for k, v in results.items()},
        }
    
    async def check_hive(self) -> HealthResult:
        """Check hive module"""
        start = time.time()
        try:
            from engine.hive.graph import create_agent
            agent = create_agent()
            
            # Check API key
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return HealthResult("hive", "degraded", error="No API key")
            
            return HealthResult("hive", "healthy", (time.time() - start) * 1000)
        except Exception as e:
            return HealthResult("hive", "unhealthy", error=str(e))
    
    async def check_browser(self) -> HealthResult:
        """Check browser module"""
        start = time.time()
        try:
            from engine.browser.session import BrowserSession
            return HealthResult("browser", "healthy", (time.time() - start) * 1000)
        except Exception as e:
            return HealthResult("browser", "unhealthy", error=str(e))
    
    async def check_knowledge(self) -> HealthResult:
        """Check knowledge module"""
        start = time.time()
        try:
            from engine.knowledge.store import KnowledgeStore
            store = KnowledgeStore()
            return HealthResult("knowledge", "healthy", (time.time() - start) * 1000)
        except Exception as e:
            return HealthResult("knowledge", "degraded", error=str(e))


async def check_all() -> dict:
    """Convenience function"""
    return await HealthChecker().check_all()


def main():
    """CLI entry point"""
    # Add to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # Load API keys
    try:
        from api_keys import setup_env
        setup_env()
    except ImportError:
        pass
    
    print("=" * 50)
    print("NogicOS Health Check")
    print("=" * 50)
    
    results = asyncio.run(check_all())
    
    print(f"\nOverall: {results['overall'].upper()}")
    print("-" * 50)
    
    for module, data in results["modules"].items():
        icon = "OK" if data["status"] == "healthy" else "WARN" if data["status"] == "degraded" else "FAIL"
        print(f"[{icon}] {module}: {data['status']}")
        if data.get("error"):
            print(f"      Error: {data['error']}")


if __name__ == "__main__":
    main()

