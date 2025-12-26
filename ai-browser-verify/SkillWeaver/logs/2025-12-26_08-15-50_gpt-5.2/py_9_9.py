import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_9_9.py']



import asyncio

async def act(page):
    stories_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
        .get_by_role("row", name="More")
        .get_by_role("cell", name="More")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    titles = await stories_rowgroup.evaluate_all(
        """
        (rowgroups) => {
          const rg = rowgroups[0]
          if (!rg) return []
          return Array.from(rg.querySelectorAll('a'))
            .filter(a => (a.getAttribute('href') || '').startsWith('https://'))
            .map(a => a.textContent)
        }
        """
    )

    print(titles)
    return titles