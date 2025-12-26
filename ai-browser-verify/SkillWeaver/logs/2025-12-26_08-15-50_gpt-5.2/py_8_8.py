import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_8_8.py']



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

    # Rows with an upvote link are the main story title rows.
    title_rows = stories_rowgroup.get_by_role("row").filter(
        has=stories_rowgroup.get_by_role("link", name="upvote")
    )

    titles = await title_rows.evaluate_all(
        """
        (rows) => rows.map(r => {
          const tds = r.querySelectorAll('td')
          const titleTd = tds[2]
          if (!titleTd) return null
          const a = titleTd.querySelector('a')
          return a ? a.textContent : null
        })
        """
    )

    print(titles)
    return titles