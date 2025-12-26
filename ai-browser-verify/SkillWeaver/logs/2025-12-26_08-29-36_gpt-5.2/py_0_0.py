import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-29-36_gpt-5.2\\py_0_0.py']



import re

async def act(page):
    # Collect all external story title links on the front page.
    # On HN, story title links point to absolute http(s) URLs, while other links are relative (item, user, from, vote, etc.).
    title_links = page.get_by_role("link").filter(has_not=page.get_by_role("img"))

    # Evaluate in page context to extract accessible names for links whose href starts with http.
    titles = await page.evaluate("""() => {
        const anchors = Array.from(document.querySelectorAll('a'))
        const out = []
        for (const a of anchors) {
          const href = a.getAttribute('href') || ''
          if (/^https?:\/\//i.test(href)) {
            const text = (a.textContent || '').trim()
            // Heuristic: story titles are non-empty and not site links like 'example.com'
            if (text && !/^\w[\w.-]*\.[a-z]{2,}(?:\/[\S]*)?$/i.test(text)) {
              out.push(text)
            }
          }
        }
        return out
    }""")

    print(titles)
    return titles