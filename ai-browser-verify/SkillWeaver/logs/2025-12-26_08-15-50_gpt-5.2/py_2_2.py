import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_2_2.py']



import asyncio

async def act(page):
    stories_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
        .get_by_role("row", name="1. upvote Maybe the default settings are too high")
        .get_by_role("cell")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    title_rows = stories_rowgroup.get_by_role("row", name=". upvote")

    # In each title row: link[0] is "upvote", link[1] is the story title.
    title_links = title_rows.get_by_role("link").nth(1)

    titles = await title_links.all_inner_texts()
    print(titles)
    return titles