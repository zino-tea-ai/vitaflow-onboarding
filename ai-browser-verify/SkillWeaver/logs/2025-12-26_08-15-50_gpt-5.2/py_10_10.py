import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_10_10.py']



import asyncio

async def act(page):
    # Locate the inner stories table rowgroup shown in the accessibility tree
    stories_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
        .get_by_role("row", name="More")
        .get_by_role("cell", name="More")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    titles = await stories_rowgroup.evaluate(
        """
        (rg) => {
          const rows = Array.from(rg.querySelectorAll('tr'))
          const titleRows = rows.filter(r => r.querySelector('a') && Array.from(r.querySelectorAll('a')).some(a => (a.textContent || '').trim() === 'upvote'))
          return titleRows.map(r => {
            const tds = r.querySelectorAll('td')
            const titleTd = tds[2]
            const a = titleTd ? titleTd.querySelector('a') : null
            return a ? a.textContent : null
          })
        }
        """
    )

    print(titles)
    return titles