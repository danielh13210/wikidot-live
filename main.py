import asyncio
from playwright.async_api import async_playwright
import httpx
import re
import os
import time
from datetime import datetime, timezone
BASE_URL=os.environ['BASE_URL']

async def get_ftml(page):
  await page.locator("#view-source-button").dispatch_event("click")
  content=page.locator("#action-area > div.page-source")
  await content.wait_for(state="attached")
  return await content.inner_text()

async def get_creation_date(page):
  await page.locator("#history-button").click()
  await page.locator("#revision-list").wait_for(state="attached")
  next_button=page.locator("#revision-list > div.pager > span.target").last
  next_button=next_button.filter(
    has=page.locator("a"),
    has_text="»"
  )
  page_count=page.locator("#revision-list > div.pager > span.pager-no").first
  await page.locator("#history-form-1 > div.buttons").wait_for(state="attached")
  await asyncio.sleep(0.1)
  print("start")
  if (await next_button.count())>0:
    print("found")
    while (await next_button.count())>0:
      await next_button.click()
      print("clicked")
      original=await page_count.text_content()
      await page.wait_for_selector(f'#revision-list > div.pager > span.pager-no:not(:text-is(\"{original}\"))')
  print("done")
  creation_revision=page.locator("#revision-list > table.page-history > tbody > tr").last
  view_first=creation_revision.locator("td.optionstd > a").first
  await view_first.click()
  date_row=page.locator("#page-version-info > table > tbody > tr").nth(1)
  date_field=date_row.locator("> td").nth(1)
  date=(await date_field.text_content()).strip()
  return datetime.strptime(date,"%d %b %Y, %H:%M").replace(tzinfo=timezone.utc).isoformat(timespec="seconds")

#work around a wikidot bug
async def get_wikidot_token7():
  #curl -I https://scp-wiki.wikidot.com | grep -Po "^set-cookie: wikidot_token7=\K\S*"
  async with httpx.AsyncClient() as client:
    response=await client.head(BASE_URL)
    return response.cookies.get("wikidot_token7")

async def handle_ftml(reader: asyncio.StreamReader,writer: asyncio.StreamWriter,context):
  page=await context.new_page()
  page_id=(await reader.readline()).decode().strip()
  await page.goto(f"{BASE_URL}/{page_id}")
  content=(await get_ftml(page)).encode('utf-8')
  writer.write(content)
  writer.write(b'\n')
  creation_date=await get_creation_date(page)
  writer.write(f'..CREATION: {creation_date}'.encode('utf-8'))
  writer.write(b'\n')
  await writer.drain()
  await page.close()
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
