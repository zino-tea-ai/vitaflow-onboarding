import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_1_1.py']



import asyncio

async def act(page):
    # Scope to the inner stories table rowgroup (contains all story rows)
    stories_rowgroup = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("table")
        .get_by_role("rowgroup")
        .get_by_role(
            "row",
            name="1. upvote Maybe the default settings are too high",
        )
        .get_by_role("cell")
        .get_by_role("table")
        .get_by_role("rowgroup")
    )

    # Story title rows are identifiable because they contain an "upvote" link.
    title_links = stories_rowgroup.get_by_role("row").filter(
        has=page.get_by_role("link", name="upvote")
    ).get_by_role("link").first

    titles = await title_links.all_inner_texts()
    print(titles)
    return titles