import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_3_3.py']



import re

async def act(page):
    # Outer content table -> rowgroup (already at Hacker News front page)
    content_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    # The big row that contains the full list ends with "More" in its accessible name
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
        has=page.get_by_role("link", name="upvote")
    )

    # In each title row, the story title link is the one with an absolute https:// URL
    title_links = title_rows.get_by_role("link", url=re.compile(r"^https://"))

    titles = await title_links.all_inner_texts()
    print(titles)
    return titles