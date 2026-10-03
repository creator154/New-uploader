import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import logging
import yt_dlp
import cloudscraper
import m3u8
import core as helper
from urllib.parse import quote, urlparse, urljoin
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN
from aiohttp import ClientSession, web
from pyromod import listen
from subprocess import getstatusoutput
from pytube import YouTube
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid

logger = logging.getLogger(__name__)
my_name = "Zx"
cookies_file_path = os.getenv("COOKIES_FILE_PATH", "/modules/youtube_cookies.txt")

# Initialize Bot
bot = Client(
    "bot",
    api_id=37721193,
    api_hash="ed5cbbc0e14a777e1b2deb0c3f763874",
    bot_token="8889799148:AAH7AEjpOeC75bD6DO-TpXsyO4Ie35QWu00"
)

# ---------------- WEB SERVER ----------------
routes = web.RouteTableDef()

@routes.get("/")
async def root(request):
    return web.Response(text="Bot is Running!")

async def web_server():
    app = web.Application()
    app.add_routes(routes)
    return app

# ---------------- START BOT & WEB SERVER ----------------
async def main():
    # Web App Start
    app = web.AppRunner(await web_server())
    await app.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(app, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

    # Telegram Bot Start
    await bot.start()
    me = await bot.get_me()
    print(f"Bot Started Successfully as @{me.username}")

    # Keep bot alive
    from pyrogram import idle
    await idle()

    # Stop Bot
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())

# Helper Functions
def pwdlx_video(url: str, output_filename: str):
    cmd = [
        "yt-dlp",
        "--newline",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--concurrent-fragments",
        "8",
        "--downloader",
        "aria2c",
        "--downloader-args",
        "aria2c:-x16 -s16 -k1M -j16 --file-allocation=none",
        "-o",
        output_filename,
        url,
    ]
    subprocess.run(cmd, check=True)
    return output_filename

def extract_content_id(url):
    """URL se content ID extract karega with precise debugging"""
    logger.info(f"extract_content_id called with URL: {url}")
    try:
        if 'contentId=' in url:
            logger.info("Found 'contentId=' in URL")
            parts = url.split('contentId=')
            if len(parts) > 1:
                content_id = parts[1]
                logger.info(f"Initial split content ID: {content_id}")
                for char in ['?', '&']:
                    if char in content_id:
                        content_id = content_id.split(char)[0]
                        logger.info(f"After removing query params ('{char}'): {content_id}")
                if content_id.endswith('.m3u8'):
                    content_id = content_id[:-5]
                    logger.info(f"After removing trailing .m3u8: {content_id}")
                elif '.m3u8' in content_id:
                    content_id = content_id.split('.m3u8')[0]
                    logger.info(f"After inline .m3u8 split: {content_id}")
                logger.info(f"✅ Extracted content ID: {content_id}")
                return content_id
        logger.warning("❌ No content ID found in URL")
        return None
    except Exception as e:
        logger.error(f"❌ Error extracting content ID: {e}", exc_info=True)
        return None

def get_jw_signed_url(content_id, access_token):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en",
        "Origin": "https://web.classplusapp.com",
        "Referer": "https://web.classplusapp.com/",
        "Region": "IN",
        "User-Agent": "Mozilla/5.0",
        "X-Access-Token": access_token,
    }
    content_api = (
        "https://api.classplusapp.com/cams/uploader/video/"
        f"jw-signed-url?contentId={quote(content_id, safe='')}"
    )
    print("[1] Trying contentId...")
    r = requests.get(content_api, headers=headers, timeout=15)
    print(f"[CONTENT] Status: {r.status_code}")
    if r.ok:
        data = r.json()
        signed_url = data.get("url")
        if signed_url:
            hostname = (urlparse(signed_url).hostname or "").lower()
            print(f"[CONTENT] Host: {hostname}")
            if hostname == "akamai-cdn.classplusapp.com":
                print("[+] Akamai signed URL found")
                return signed_url
    print("[2] Content URL not Akamai")
    print("[+] Trying liveSessionId API...")
    live_api = (
        "https://api.classplusapp.com/cams/uploader/video/"
        f"jw-signed-url?liveSessionId={quote(content_id, safe='')}"
        "&isAgora=2"
    )
    r = requests.get(live_api, headers=headers, timeout=15)
    print(f"[LIVE] Status: {r.status_code}")
    r.raise_for_status()
    data = r.json()
    signed_url = data.get("url")
    if not signed_url:
        print("[!] Live signed URL not found")
        return None
    print("[+] Live signed URL received")
    return signed_url

def new_classplus_cdn(url, raw_text2, output_filename):
    format_selector = (
        f"bestvideo[height<={raw_text2}]"
        f"+bestaudio/best[height<={raw_text2}]"
    )
    cmd = [
        "yt-dlp",
        "--newline",
        "-f",
        format_selector,
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--concurrent-fragments",
        "8",
        "--downloader",
        "aria2c",
        "--downloader-args",
        "aria2c:-x16 -s16 -k1M -j16 --file-allocation=none",
        "--add-header",
        "Origin: https://web.classplusapp.com",
        "--add-header",
        "Referer: https://web.classplusapp.com/",
        "-o",
        output_filename,
        url,
    ]
    subprocess.run(cmd, check=True)
    return output_filename

class Data:
    START = "🦋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ʙᴀʙʏ 🦋 {0} \n\n"

# Bot Commands
@bot.on_message(filters.command("start"))
async def start(client: Client, msg: Message):
    user = await client.get_me()
    start_message = await client.send_message(msg.chat.id, Data.START.format(msg.from_user.mention))
    await asyncio.sleep(1)
    await start_message.edit_text(Data.START.format(msg.from_user.mention) + "Initializing Uploader bot... 🤖\n\nProgress: [⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%\n\n")
    await asyncio.sleep(1)
    await start_message.edit_text(Data.START.format(msg.from_user.mention) + "Loading features... ⏳\n\nProgress: [🟥🟥🟥⬜⬜⬜⬜⬜⬜] 25%\n\n")
    await asyncio.sleep(1)
    await start_message.edit_text(Data.START.format(msg.from_user.mention) + "This may take a moment, sit back and relax! 😊\n\nProgress: [🟧🟧🟧🟧🟧⬜⬜⬜⬜] 50%\n\n")
    await asyncio.sleep(1)
    await start_message.edit_text(Data.START.format(msg.from_user.mention) + "Checking Bot Status... 🔍\n\nProgress: [🟨🟨🟨🟨🟨🟨🟨⬜⬜] 75%\n\n")
    await asyncio.sleep(1)
    await start_message.edit_text(Data.START.format(msg.from_user.mention) + "ᴄʜᴇᴄᴋɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴀᴄᴛɪᴠᴇ... ᴄᴏᴍᴍᴀɴᴅ ᴘᴛᴀ ʜᴀɪ ᴋɪ ɴʜɪ ᴊɪ 🙃\nᴄᴏɴᴛᴀᴄᴛ @SumitTripathi 🔍\n\nᴘʀᴏɢʀᴇꜱꜱ:[🟩🟥🟩🟥🟩🟥🟩🟥🟩] 100%")

@bot.on_message(filters.command(["stop"]))
async def restart_handler(_, m):
    await m.reply_text("STOPPED🛑", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command(["baby"]))
async def txt_handler(bot: Client, m: Message):
    editable = await m.reply_text("🍁ʜɪ ɪ'ᴍ ᴘᴏᴡᴇʀꜰᴜʟ ᴛxᴛ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ.\n🍁ꜱᴇɴᴅ ᴀ ᴛxᴛ ꜰɪʟᴇ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ ʙᴇɢɪɴ...")
    input_msg: Message = await bot.listen(editable.chat.id)
    x = await input_msg.download()
    await input_msg.delete(True)
    file_name, ext = os.path.splitext(os.path.basename(x))
    credit = "@jaat_mk"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MzYxNTE3MzAuMTI2LCJkYXRhIjp7Il9pZCI6IjYzMDRjMmY3Yzc5NjBlMDAxODAwNDQ4NyIsInVzZXJuYW1lIjoiNzc2MTAxNzc3MCIsImZpcnN0TmFtZSI6IkplZXZgbmFyYXlhbiIsImxhc3ROYW1lIjoic2FoIiwib3JnYW5pemF0aW9uIjp7Il9pZCI6IjVlYjM5M2VlOTVmYWI3NDY4YTc5ZDE4OSIsIndlYnNpdGUiOiJwaHlzaWNzd2FsbGFoLmNvbSIsIm5hbWUiOiJQaHlzaWNzd2FsbGFoLIn0sImVtYWlsIjoiV1dXLkpFRVZOQVJBWUFOU0FIQEdNQUlMLkNPTSIsInJvbGVzIjpbIjViMjdiZDk2NTg0MmY5NTBhNzc4YzZlZiJdLCJjb3VudHJ5R3JvdXAiOiJJTiIsInR5cGUiOiJVU0VSIn0sImlhdCI6MTczNTU0NjkzMH0.iImf90mFu_cI-xINBv4t0jVz-rWK1zeXOIwIFvkrS0M"
    try:
        with open(x, "r") as f:
            content = f.read().split("\n")
        links = [i.split("://", 1) for i in content if "://" in i]
        os.remove(x)
    except Exception:
        await m.reply_text("Invalid file input.")
        if os.path.exists(x):
            os.remove(x)
        return

    await editable.edit(f"Total links found are **{len(links)}**\n\nSend From where you want to download initial is **1**")
    input0: Message = await bot.listen(editable.chat.id)
    raw_text = input0.text
    await input0.delete(True)
    try:
        arg = int(raw_text)
    except Exception:
        arg = 1

    await editable.edit("**Enter Your Batch Name or send Zx for grabing from text filename.**")
    input1: Message = await bot.listen(editable.chat.id)
    raw_text0 = input1.text
    await input1.delete(True)
    b_name = file_name if raw_text0 == 'd' else raw_text0

    await editable.edit("**Enter resolution.\n Eg : 480 or 720**")
    input2: Message = await bot.listen(editable.chat.id)
    raw_text2 = input2.text
    await input2.delete(True)
    res_map = {"144": "256x144", "240": "426x240", "360": "640x360", "480": "854x480", "720": "1280x720", "1080": "1920x1080"}
    res = res_map.get(raw_text2, "UN")

    await editable.edit("**Enter Watermark Text\nSend /d for No Watermark**")
    input_wm: Message = await bot.listen(editable.chat.id)
    WM = input_wm.text
    await input_wm.delete(True)

    await editable.edit("**Enter Your Name or send 'Zx' for use default.\n Eg : @SumitTripathi **")
    input3: Message = await bot.listen(editable.chat.id)
    raw_text3 = input3.text
    await input3.delete(True)
    CR = credit if raw_text3 == 'de' else raw_text3

    await editable.edit("**Enter Your PW Token For 𝐌𝐏𝐃 𝐔𝐑𝐋 or send '/Zx' for use default**")
    input4: Message = await bot.listen(editable.chat.id)
    raw_text4 = input4.text
    await input4.delete(True)
    access_token = token if raw_text4 == 'unknown' else raw_text4

    await editable.edit("Now send the **Thumb url**\n**Eg :** ``\n\nor Send `no`")
    input6: Message = await bot.listen(editable.chat.id)
    raw_text6 = input6.text
    await input6.delete(True)
    await editable.delete()
    
    thumb = raw_text6
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    count = int(arg)
    for i in range(arg - 1, len(links)):
        Vxy = links[i][1].replace("file/d/", "uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing", "")
        url = "https://" + Vxy

        if "visionias" in url:
            async with ClientSession() as session:
                async with session.get(url, headers={'Referer': 'http://www.visionias.in/', 'User-Agent': 'Mozilla/5.0'}) as resp:
                    text = await resp.text()
                    match = re.search(r"(https://.*?playlist.m3u8.*?)\"", text)
                    if match:
                        url = match.group(1)
        elif 'https://contentId=' in url or 'contentHashIdl=' in url:
            content_id = extract_content_id(url)
            cpurl = get_jw_signed_url(content_id, access_token)
            if cpurl:
                url = cpurl
        elif "/index_6.m3u8?" in url:
            url = f"https://ankitshakyaxapi.vercel.app//api/pwlive/download?url={url}"
        elif '/master.mpd' in url or "/dash/" in url or ".mp4?" in url or "?Signature=" in url or "d1d34p8vz63oiq.cloudfront.net" in url or "parentId=" in url or "childId=" in url:
            if "parentId=" in url or "childId=" in url:
                url = f"https://ankitshakyaxapi.vercel.app/download?mpd_url={url}&token={raw_text4}&quality={raw_text2}"
            elif "p01--streamthorr--8zqnnv98yzb8.code.run" in url:
                if "/dash/" in url:
                    url = re.sub(r'/dash/[^?]*?(?:\?.*)?$', '/master.m3u8', url)
            else:
                url = f"https://ankitshakyaxapi.vercel.app/download?mpd_url={url}&quality={raw_text2}"

        name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
        name = f'{str(count).zfill(3)}) {name1[:60]} {my_name}'

        if "edge.api.brightcove.com" in url:
            bcov = 'bcov_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MjQyMzg3OTEsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiJVMFZ6TkdGU2NuQlZjR3h5TkZwV09FYzBURGxOZHowOSIsImlkIjoiZEUxbmNuZFBNblJqVEROVmFWTlFWbXhRTkhoS2R6MDkiLCJmaXJzdF9uYW1lIjoiYVcxV05ITjVSemR6Vm10ak1WUlBSRkF5ZVNzM1VUMDkiLCJlbWFpbCI6Ik5Ga3hNVWhxUXpRNFJ6VlhiR0ppWTJoUk0wMVdNR0pVTlU5clJXSkRWbXRMTTBSU2FHRnhURTFTUlQwPSIsInBob25lIjoiVUhVMFZrOWFTbmQ1ZVcwd1pqUTViRzVSYVc5aGR6MDkiLCJhdmF0YXIiOiJLM1ZzY1M4elMwcDBRbmxrYms4M1JEbHZla05pVVQwOSIsInJlZmVycmFsX2NvZGUiOiJOalZFYzBkM1IyNTBSM3B3VUZWbVRtbHFRVXAwVVQwOSIsImRldmljZV90eXBlIjoiYW5kcm9pZCIsImRldmljZV92ZXJzaW9uIjoiUShBbmRyb2lkIDEwLjApIiwiZGV2aWNlX21vZGVsIjoiU2Ftc3VuZyBTTS1TOTE4QiIsInJlbW90ZV9hZGRyIjoiNTQuMjI2LjI1NS4xNjMsIDU0LjIyNi4yNTUuMTYzIn19.snDdd-PbaoC42OUhn5SJaEGxq0VzfdzO49WTmYgTx8ra_Lz66GySZykpd2SxIZCnrKR6-R10F5sUSrKATv1CDk9ruj_ltCjEkcRq8mAqAytDcEBp72-W0Z7DtGi8LdnY7Vd9Kpaf499P-y3-godolS_7ixClcYOnWxe2nSVD5C9c5HkyisrHTvf6NFAuQC_FD3TzByldbPVKK0ag1UnHRavX8MtttjshnRhv5gJs5DQWj4Ir_dkMcJ4JaVZO3z8j0OxVLjnmuaRBujT-1pavsr1CCzjTbAcBvdjUfvzEhObWfA1-Vl5Y4bUgRHhl1U-0hne4-5fF0aouyu71Y6W0eg'
            url = url.split("bcov_auth")[0] + bcov

        ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]" if "youtu" in url else f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"
        
        if "jw-prod" in url:
            cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
        elif "youtube.com" in url or "youtu.be" in url:
            cmd = f'yt-dlp --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}.mp4"'
        else:
            cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

        cc = f"**➭ Index » {str(count).zfill(3)} ➭ Title » {name1} {res}.mkv ➭ 𝐁𝐚𝐭𝐜𝐡 » {b_name} ➭ Quality » {res} ➭ 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐄𝐃 𝐁𝐘 : {CR}\n\n<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>**"
        cc1 = f"**➭ Index » {str(count).zfill(3)} ➭ Title » {name1}.pdf ➭ 𝐁𝐚𝐭𝐜𝐡 » {b_name} ➭ 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐄𝐃 𝐁𝐘 : {CR}\n\n<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>**"

        try:
            if "drive" in url:
                ka = await helper.download(url, name)
                await bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
                count += 1
                if os.path.exists(ka):
                    os.remove(ka)
                await asyncio.sleep(1)
            elif ".pdf?" in url or ".pdf?URLPrefix=" in url:
                downloaded_pdf = await helper.download_secure_pdf(url, name)
                if downloaded_pdf and os.path.exists(downloaded_pdf):
                    await bot.send_document(chat_id=m.chat.id, document=downloaded_pdf, caption=cc1)
                    count += 1
                    os.remove(downloaded_pdf)
                else:
                    await m.reply_text("❌ Appx PDF download fail ho gaya.")
            elif ".pdf" in url:
                url_clean = url.replace(" ", "%20")
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url_clean)
                if response.status_code == 200:
                    pdf_filename = f"{name}.pdf"
                    with open(pdf_filename, 'wb') as file:
                        file.write(response.content)
                    await bot.send_document(chat_id=m.chat.id, document=pdf_filename, caption=cc1)
                    count += 1
                    os.remove(pdf_filename)
                else:
                    await m.reply_text(f"Failed to download PDF: {response.status_code}")
            elif "transcoded-videos.classx.co.in" in url.lower() or "classx.co.in" in url.lower():
                Show = f"🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢tl𝐞 » `{name}`\n⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2}\n"
                prog = await m.reply_text(Show)
                res_file = await helper.download_secure_video(url, name)
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, res_file, thumb, name, prog)
                count += 1
            elif 'akamai-cdn.classplusapp.com' in url:
                Show = f"🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢tl𝐞 » `{name}`\n⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2}\n"
                prog = await m.reply_text(Show)
                output_filename = f"{name}.mp4"
                res_file = new_classplus_cdn(url, raw_text2, output_filename)
                filename = res_file
                if WM != "/d":
                    wm_file = f"wm_{filename}"
                    os.system(f'''ffmpeg -y -i "{filename}" -vf "drawtext=text='{WM}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black:x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))" -codec:a copy "{wm_file}"''')
                    if os.path.exists(wm_file):
                        os.remove(filename)
                        filename = wm_file
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)
                count += 1
            elif '/master.mpd' in url or "code.run" in url or "/dash/" in url or ".mp4?" in url or "?Signature=" in url or "d1d34p8vz63oiq.cloudfront.net" in url or "parentId=" in url or "childId=" in url:
                Show = f"🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢tl𝐞 » `{name}`\n⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2}\n"
                prog = await m.reply_text(Show)
                output_filename = f"{name}.mp4"
                res_file = pwdlx_video(url, output_filename)
                filename = res_file
                if WM != "/d":
                    wm_file = f"wm_{filename}"
                    os.system(f'''ffmpeg -y -i "{filename}" -vf "drawtext=text='{WM}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black:x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))" -codec:a copy "{wm_file}"''')
                    if os.path.exists(wm_file):
                        os.remove(filename)
                        filename = wm_file
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)
                count += 1
            else:
                Show = f"🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢tl𝐞 » `{name}`\n⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2}\n"
                prog = await m.reply_text(Show)
                res_file = await helper.download_video(url, cmd, name)
                filename = res_file
                if WM != "/d":
                    wm_file = f"wm_{filename}"
                    os.system(f'''ffmpeg -y -i "{filename}" -vf "drawtext=text='{WM}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black:x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))" -codec:a copy "{wm_file}"''')
                    if os.path.exists(wm_file):
                        os.remove(filename)
                        filename = wm_file
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)
                count += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            continue
        except Exception as e:
            await m.reply_text(f"⌘ 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠 𝐈𝐧𝐭𝐞𝐫𝐫𝐮𝐩𝐭𝐞𝐝\n\n⌘ 𝐍𝐚𝐦𝐞 » {name}\n⌘ 𝐋𝐢𝐧𝐤 » `{url}`\nError: {str(e)}")
            continue

    await m.reply_text("𝐄𝐕𝐄𝐑𝐘𝐓𝐇𝐈𝐍𝐆 𝐈𝐒 𝐃𝐎𝐍𝐄 ☑️")

if __name__ == "__main__":
    asyncio.run(main())
