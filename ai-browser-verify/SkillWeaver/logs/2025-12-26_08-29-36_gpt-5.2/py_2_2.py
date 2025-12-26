import asyncio, re
from skillweaver.agent import vars

(print,) = vars['C:\\Users\\WIN\\Desktop\\Cursor Project\\ai-browser-verify\\SkillWeaver\\logs\\2025-12-26_08-29-36_gpt-5.2\\py_2_2.py']



async def act(page):
    titles = await page.evaluate("""() => {
      const selectors = ['span.titleline > a', 'a.storylink', 'a.titlelink']
      let anchors = []
      for (const sel of selectors) {
        anchors = Array.from(document.querySelectorAll(sel))
        if (anchors.length) break
      }
      return anchors.map(a => (a.textContent || '').trim())
    }""")

    print(titles)
    return titles