import asyncio
from playwright.async_api import async_playwright
import httpx
import re
import os
BASE_URL=os.environ['BASE_URL']

async def get_ftml(page,page_id):
  await page.goto(f"{BASE_URL}/{page_id}")
  await page.locator("#view-source-button").dispatch_event("click")
  content=page.locator("#action-area > div.page-source")
  await content.wait_for(state="attached")
  return await content.inner_text()

#work around a wikidot bug
async def get_wikidot_token7():
  #curl -I https://scp-wiki.wikidot.com | grep -Po "^set-cookie: wikidot_token7=\K\S*"
  async with httpx.AsyncClient() as client:
    response=await client.head(BASE_URL)
    return response.cookies.get("wikidot_token7")

async def handle_ftml(reader: asyncio.StreamReader,writer: asyncio.StreamWriter,context):
  page=await context.new_page()
  page_id=(await reader.readline()).decode().strip()
  content=(await get_ftml(page,page_id)).encode('utf-8')
  await page.close()
  writer.write(content)
  await writer.drain()
  writer.close()

async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(
      headless=not bool(os.environ.get('PW_DISPLAY',False)),
      args=[
             "--disable-blink-features=AutomationControlled", # Prevents native override injection
             "--disable-infobars"
           ]
    )
    context=await browser.new_context()
    token=await get_wikidot_token7()
    await context.add_cookies([{"name":"wikidot_token7","value":token,"url":f'{BASE_URL}/'}])
    async def ftml_server_handler(reader: asyncio.StreamReader,writer: asyncio.StreamWriter):
      await handle_ftml(reader,writer,context)
    server = await asyncio.start_server(ftml_server_handler, '127.0.0.1', 9999)
    try:
      await server.serve_forever()
    finally:
      await context.close()
      await browser.close()

asyncio.run(main())
