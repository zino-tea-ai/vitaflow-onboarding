import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-15-50_gpt-5.2\\py_6_6.py']



import asyncio

async def act(page):
    # Wait for at least one story upvote link to ensure the list is present
    first_upvote = (
        page.get_by_role("document", name="Hacker News")
        .get_by_role("link", name="upvote")
        .first
    )
    await first_upvote.wait_for()

    titles = await page.get_by_role("document", name="Hacker News").evaluate_all(
        """
        (docs) => {
          const doc = docs[0]
          const upvotes = Array.from(doc.querySelectorAll('a'))
            .filter(a => (a.textContent || '').trim() === 'upvote')

          return upvotes.map(up => {
            const row = up.closest('tr')
            if (!row) return null
            const titleCell = row.querySelector('td.title')
            if (!titleCell) return null
            const titleLink = titleCell.querySelector('a')
            if (!titleLink) return null
            return titleLink.textContent
          })
        }
        """
    )

    print(titles)
    return titles