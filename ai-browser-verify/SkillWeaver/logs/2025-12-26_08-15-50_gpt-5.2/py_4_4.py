import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_4_4.py']



import asyncio

async def act(page):
    # Scope to outer content rowgroup
    content_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    # The big container row that contains all stories ends with/contains "More"
    stories_container_row = content_rowgroup.get_by_role("row", name="More")

    # Inner stories table rowgroup
    stories_rowgroup = (
        stories_container_row
        .get_by_role("cell")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    # Title rows contain an "upvote" link
    title_rows = stories_rowgroup.get_by_role("row").filter(
        has=stories_rowgroup.get_by_role("link", name="upvote")
    )

    # In each title row, the title cell includes "(domain)" in its accessible name
    # the first link inside that cell is the story title.
    title_links = title_rows.get_by_role("cell", name="(").get_by_role("link").first

    titles = await title_links.all_inner_texts()
    print(titles)
    return titles