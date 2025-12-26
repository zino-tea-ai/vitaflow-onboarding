import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-29-36_gpt-5.2\\py_1_1.py']



async def act(page):
    # Scope to the main content table that contains the list of stories.
    main_table = page.get_by_role("document", name="Hacker News").get_by_role("table").nth(0)

    # Story title rows are identifiable by containing an "upvote" link.
    story_rows = main_table.get_by_role("row").filter(
        has=page.get_by_role("link", name="upvote")
    )

    # Extract the title link name from each story row.
    titles = await story_rows.evaluate_all(
        """(rows) => rows.map(row => {
          // In a story row, anchors are typically: [upvote], [title], [site]
          const anchors = Array.from(row.querySelectorAll('a'))
          const titleAnchor = anchors.find(a => (a.textContent || '').trim() && (a.textContent || '').trim().toLowerCase() !== 'upvote')
          return titleAnchor ? (titleAnchor.textContent || '').trim() : ''
        })"""
    )

    print(titles)
    return titles