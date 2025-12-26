import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-09-18_gpt-5.2\\py_0_0.py']



import asyncio

async def act(page):
    # On Hacker News front page; extract visible story title links.
    # Each story is in a row whose accessible name starts with "N. upvote ...".
    story_rows = page.get_by_role(
        "row",
        name=". upvote",
    )

    titles = []
    count = await story_rows.count()
    for i in range(count):
        row = story_rows.nth(i)
        # The title is the first link in the third cell of the story row.
        title_link = row.get_by_role("cell").nth(2).get_by_role("link").first
        titles.append(await title_link.inner_text())

    print(titles)
    return titles