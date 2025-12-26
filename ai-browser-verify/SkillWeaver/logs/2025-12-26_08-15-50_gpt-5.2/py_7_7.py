import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_7_7.py']



import asyncio

async def act(page):
    # Inner stories table rowgroup
    stories_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
        .get_by_role("row", name="More")
        .get_by_role("cell", name="More")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    # Title rows contain an "upvote" link
    title_rows = stories_rowgroup.get_by_role("row").filter(
        has=stories_rowgroup.get_by_role("link", name="upvote")
    )

    # In each title row, the title cell includes "(domain)" in its accessible name
    # the first link inside that cell is the story title.
    title_links = title_rows.get_by_role("cell", name="(").get_by_role("link").nth(0)

    titles = await title_links.all_inner_texts()
    print(titles)
    return titles