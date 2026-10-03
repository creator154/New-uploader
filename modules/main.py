import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import urllib.parse
from urllib.parse import quote, urlparse
import logging
import yt_dlp
import cloudscraper
import m3u8
import core as helper
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN
from aiohttp import ClientSession
from pyromod import listen
from subprocess import getstatusoutput
from pytube import YouTube
from aiohttp import web
from urllib.parse import quote, urljoin
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(name)

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

# ---------------- START BOT ----------------
async def start_bot():
    await bot.start()
    me = await bot.get_me()
    print(f"Bot Started Successfully as @{me.username}")
async def stop_bot():
    await bot.stop()

async def main():
    await start_bot()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await stop_bot()

if __name__ == "__main__":
    asyncio.run(main())
    
import os
import subprocess

def pwdlx_video(url: str, output_filename: str):
cmd = [
"yt-dlp",
"--newline",
"--merge-output-format", "mp4",
"--remux-video", "mp4",
"--concurrent-fragments", "8",
"--downloader", "aria2c",
"--downloader-args",
"aria2c:-x16 -s16 -k1M -j16 --file-allocation=none",
"-o", output_filename,
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
              
            # 1. URL parameters ('?' ya '&') se split karein taaki baaki ka URL hat jaye  
            for char in ['?', '&']:  
                if char in content_id:  
                    content_id = content_id.split(char)[0]  
                    logger.info(f"After removing query params ('{char}'): {content_id}")  
              
            # 2. Agar end me '.m3u8' hai toh use hatao  
            if content_id.endswith('.m3u8'):  
                content_id = content_id[:-5] # .m3u8 exactly 5 characters ka hota hai  
                logger.info(f"After removing trailing .m3u8: {content_id}")  
            # Back-up check agar URL ke beech me kahin string ke sath .m3u8 laga ho  
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

# 1. First try: contentId  
content_api = (  
    "https://api.classplusapp.com/cams/uploader/video/"  
    f"jw-signed-url?contentId={quote(content_id, safe='')}"  
)  

print("[1] Trying contentId...")  

r = requests.get(  
    content_api,  
    headers=headers,  
    timeout=15  
)  

print(f"[CONTENT] Status: {r.status_code}")  

if r.ok:  
    data = r.json()  
    signed_url = data.get("url")  

    if signed_url:  
        hostname = (urlparse(signed_url).hostname or "").lower()  

        print(f"[CONTENT] Host: {hostname}")  

        # Akamai URL → directly use it  
        if hostname == "akamai-cdn.classplusapp.com":  
            print("[+] Akamai signed URL found")  
            return signed_url  

# 2. Fallback: same ID as liveSessionId  
print("[2] Content URL not Akamai")  
print("[+] Trying liveSessionId API...")  

live_api = (  
    "https://api.classplusapp.com/cams/uploader/video/"  
    f"jw-signed-url?liveSessionId={quote(content_id, safe='')}"  
    "&isAgora=2"  
)  

r = requests.get(  
    live_api,  
    headers=headers,  
    timeout=15  
)  

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
    "-f", format_selector,  
    "--merge-output-format", "mp4",  
    "--remux-video", "mp4",  
    "--concurrent-fragments", "8",  
    "--downloader", "aria2c",  
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

--------------------------------------------

class Data:
START = (
"🦋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ʙᴀʙʏ 🦋 {0} \n\n"
)

Define the start command handler

@bot.on_message(filters.command("start"))
async def start(client: Client, msg: Message):
user = await client.get_me()
mention = user.mention
start_message = await client.send_message(
msg.chat.id,
Data.START.format(msg.from_user.mention)
)

await asyncio.sleep(1)  
await start_message.edit_text(  
    Data.START.format(msg.from_user.mention) +  
    "Initializing Uploader bot... 🤖\n\n"  
    "Progress: [⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%\n\n"  
)  

await asyncio.sleep(1)  
await start_message.edit_text(  
    Data.START.format(msg.from_user.mention) +  
    "Loading features... ⏳\n\n"  
    "Progress: [🟥🟥🟥⬜⬜⬜⬜⬜⬜] 25%\n\n"  
)  
  
await asyncio.sleep(1)  
await start_message.edit_text(  
    Data.START.format(msg.from_user.mention) +  
    "This may take a moment, sit back and relax! 😊\n\n"  
    "Progress: [🟧🟧🟧🟧🟧⬜⬜⬜⬜] 50%\n\n"  
)  

await asyncio.sleep(1)  
await start_message.edit_text(  
    Data.START.format(msg.from_user.mention) +  
    "Checking Bot Status... 🔍\n\n"  
    "Progress: [🟨🟨🟨🟨🟨🟨🟨⬜⬜] 75%\n\n"  
)  

await asyncio.sleep(1)  
await start_message.edit_text(  
    Data.START.format(msg.from_user.mention) +  
    "ᴄʜᴇᴄᴋɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴀᴄᴛɪᴠᴇ... ᴄᴏᴍᴍᴀɴᴅ ᴘᴛᴀ ʜᴀɪ ᴋɪ ɴʜɪ ᴊɪ 🙃\n"

"ᴄᴏɴᴛᴀᴄᴛ @SumitTripathi 🔍\n\n"
"ᴘʀᴏɢʀᴇꜱꜱ:[🟩🟥🟩🟥🟩🟥🟩🟥🟩] 100%"
)

@bot.on_message(filters.command(["stop"]) )
async def restart_handler(_, m):
await m.reply_text("STOPPED🛑", True)
os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command(["baby"]) )
async def txt_handler(bot: Client, m: Message):
editable = await m.reply_text(f"🍁ʜɪ ɪ'ᴍ ᴘᴏᴡᴇʀꜰᴜʟ ᴛxᴛ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ.\n🍁ꜱᴇɴᴅ ᴀ ᴛxᴛ ꜰɪʟᴇ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ ʙᴇɢɪɴ...")
input: Message = await bot.listen(editable.chat.id)
x = await input.download()
await input.delete(True)
file_name, ext = os.path.splitext(os.path.basename(x))
credit = f"@jaat_mk"
token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MzYxNTE3MzAuMTI2LCJkYXRhIjp7Il9pZCI6IjYzMDRjMmY3Yzc5NjBlMDAxODAwNDQ4NyIsInVzZXJuYW1lIjoiNzc2MTAxNzc3MCIsImZpcnN0TmFtZSI6IkplZXYgbmFyYXlhbiIsImxhc3ROYW1lIjoic2FoIiwib3JnYW5pemF0aW9uIjp7Il9pZCI6IjVlYjM5M2VlOTVmYWI3NDY4YTc5ZDE4OSIsIndlYnNpdGUiOiJwaHlzaWNzd2FsbGFoLmNvbSIsIm5hbWUiOiJQaHlzaWNzd2FsbGFoIn0sImVtYWlsIjoiV1dXLkpFRVZOQVJBWUFOU0FIQEdNQUlMLkNPTSIsInJvbGVzIjpbIjViMjdiZDk2NTg0MmY5NTBhNzc4YzZlZiJdLCJjb3VudHJ5R3JvdXAiOiJJTiIsInR5cGUiOiJVU0VSIn0sImlhdCI6MTczNTU0NjkzMH0.iImf90mFu_cI-xINBv4t0jVz-rWK1zeXOIwIFvkrS0M"
try:
with open(x, "r") as f:
content = f.read()
content = content.split("\n")
links = []
for i in content:
links.append(i.split("://", 1))
os.remove(x)
except:
await m.reply_text("Invalid file input.")
os.remove(x)
return

await editable.edit(f"Total links found are **{len(links)}**\n\nSend From where you want to download initial is **1**")  
input0: Message = await bot.listen(editable.chat.id)  
raw_text = input0.text  
await input0.delete(True)  
try:  
    arg = int(raw_text)  
except:  
    arg = 1  
await editable.edit("**Enter Your Batch Name or send Zx for grabing from text filename.**")  
input1: Message = await bot.listen(editable.chat.id)  
raw_text0 = input1.text  
await input1.delete(True)  
if raw_text0 == 'd':  
    b_name = file_name  
else:  
    b_name = raw_text0  

    await editable.edit("**Enter resolution.\n Eg : 480 or 720**")  
input2: Message = await bot.listen(editable.chat.id)  
raw_text2 = input2.text  
await input2.delete(True)  

try:  
    if raw_text2 == "144":  
        res = "256x144"  
    elif raw_text2 == "240":  
        res = "426x240"  
    elif raw_text2 == "360":  
        res = "640x360"  
    elif raw_text2 == "480":  
        res = "854x480"  
    elif raw_text2 == "720":  
        res = "1280x720"  
    elif raw_text2 == "1080":  
        res = "1920x1080"  
    else:  
        res = "UN"  
except Exception:  
    res = "UN"  

# ===== Watermark =====  
await editable.edit("**Enter Watermark Text\nSend /d for No Watermark**")  
input_wm: Message = await bot.listen(editable.chat.id)  
WM = input_wm.text  
await input_wm.delete(True)  
# =====================  

await editable.edit("**Enter Your Name or send 'Zx' for use default.\n Eg : @SumitTripathi **")  
input3: Message = await bot.listen(editable.chat.id)  
raw_text3 = input3.text  
await input3.delete(True)  

if raw_text3 == 'de':  
    CR = credit  
else:  
    CR = raw_text3  
await editable.edit("**Enter Your PW Token For 𝐌𝐏𝐃 𝐔𝐑𝐋 or send '/Zx' for use default**")  
input4: Message = await bot.listen(editable.chat.id)  
raw_text4 = input4.text  
await input4.delete(True)  

if raw_text4 == 'unknown':  
    access_token = token  
else:  
    access_token = raw_text4  

await editable.edit("Now send the **Thumb url**\n**Eg :** ``\n\nor Send `no`")  
input6 = message = await bot.listen(editable.chat.id)  
raw_text6 = input6.text  
await input6.delete(True)  
await editable.delete()  

thumb = input6.text  
if thumb.startswith("http://") or thumb.startswith("https://"):  
    getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")  
    thumb = "thumb.jpg"  
else:  
    thumb = "no"  

count = int(raw_text)      
try:  
    for i in range(arg-1, len(links)):  

        Vxy = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")  
        url = "https://" + Vxy  
        if "visionias" in url:  
            async with ClientSession() as session:  
                async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:  
                    text = await resp.text()  
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)  

        if "acecwply" in url:  
            cmd = f'yt-dlp -o "{name}.%(ext)s" -f "bestvideo[height<={raw_text2}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'  
              

        if "visionias" in url:  
            async with ClientSession() as session:  
                async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:  
                    text = await resp.text()  
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)  

        elif 'https://contentId=' in url or 'contentHashIdl=' in url:  
            content_id = extract_content_id(url)  
            cpurl = get_jw_signed_url(content_id, access_token)  
            print(f"Fetched URL: {cpurl}") # Debugging ke liye  
            url = cpurl  
            print(f"CP Url: {url}")  
              

        elif "/index_6.m3u8?" in url:  
            url = f"https://ankitshakyaxapi.vercel.app//api/pwlive/download?url={url}"  
            print(url)  
        elif '/master.mpd' in url or "/dash/" in url or ".mp4?" in url or "?Signature=" in url or "d1d34p8vz63oiq.cloudfront.net" in url or "parentId=" in url or "childId=" in url:  
            if "parentId=" in url or "childId=" in url:  
                url = f"https://ankitshakyaxapi.vercel.app/download?mpd_url={url}&token={raw_text4}&quality={raw_text2}"  
            if "p01--streamthorr--8zqnnv98yzb8.code.run" in url:  
                if "/dash/" in url:  
                    new_url = re.sub(r'/dash/[^?]*?(?:\?.*)?$', '/master.m3u8', url)  
                    print(new_url)  
                    url = new_url  
                    print(url)  
            else:  
                url = f"https://ankitshakyaxapi.vercel.app/download?mpd_url={url}&quality={raw_text2}"  
                                                       
        name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()  
        name = f'{str(count).zfill(3)}) {name1[:60]} {my_name}'  
                    
          
        if "edge.api.brightcove.com" in url:  
            bcov = 'bcov_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MjQyMzg3OTEsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiJVMFZ6TkdGU2NuQlZjR3h5TkZwV09FYzBURGxOZHowOSIsImlkIjoiZEUxbmNuZFBNblJqVEROVmFWTlFWbXhRTkhoS2R6MDkiLCJmaXJzdF9uYW1lIjoiYVcxV05ITjVSemR6Vm10ak1WUlBSRkF5ZVNzM1VUMDkiLCJlbWFpbCI6Ik5Ga3hNVWhxUXpRNFJ6VlhiR0ppWTJoUk0wMVdNR0pVTlU5clJXSkRWbXRMTTBSU2FHRnhURTFTUlQwPSIsInBob25lIjoiVUhVMFZrOWFTbmQ1ZVcwd1pqUTViRzVSYVc5aGR6MDkiLCJhdmF0YXIiOiJLM1ZzY1M4elMwcDBRbmxrYms4M1JEbHZla05pVVQwOSIsInJlZmVycmFsX2NvZGUiOiJOalZFYzBkM1IyNTBSM3B3VUZWbVRtbHFRVXAwVVQwOSIsImRldmljZV90eXBlIjoiYW5kcm9pZCIsImRldmljZV92ZXJzaW9uIjoiUShBbmRyb2lkIDEwLjApIiwiZGV2aWNlX21vZGVsIjoiU2Ftc3VuZyBTTS1TOTE4QiIsInJlbW90ZV9hZGRyIjoiNTQuMjI2LjI1NS4xNjMsIDU0LjIyNi4yNTUuMTYzIn19.snDdd-PbaoC42OUhn5SJaEGxq0VzfdzO49WTmYgTx8ra_Lz66GySZykpd2SxIZCnrKR6-R10F5sUSrKATv1CDk9ruj_ltCjEkcRq8mAqAytDcEBp72-W0Z7DtGi8LdnY7Vd9Kpaf499P-y3-godolS_7ixClcYOnWxe2nSVD5C9c5HkyisrHTvf6NFAuQC_FD3TzByldbPVKK0ag1UnHRavX8MtttjshnRhv5gJs5DQWj4Ir_dkMcJ4JaVZO3z8j0OxVLjnmuaRBujT-1pavsr1CCzjTbAcBvdjUfvzEhObWfA1-Vl5Y4bUgRHhl1U-0hne4-5fF0aouyu71Y6W0eg'  
            url = url.split("bcov_auth")[0]+bcov  
              
        if "youtu" in url:  
            ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"  
        else:  
            ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"  
          
        if "jw-prod" in url:  
            cmd = f'yt-dlp -o "{name}.mp4" "{url}"'  

        elif "youtube.com" in url or "youtu.be" in url:  
            cmd = f'yt-dlp --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}".mp4'  

        else:  
            cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'  

        try:    
              
            cc = f"""**➭ Index » {str(count).zfill(3)}

➭ Title » {name1} {res}.mkv
➭ 𝐁𝐚𝐭𝐜𝐡 » {b_name}
➭ Quality » {res}

➭ 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐄𝐃 𝐁𝐘 : {CR}\n\n<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>"""
cc1 = f"""➭ Index » {str(count).zfill(3)}
➭ Title » {name1}.pdf
➭ 𝐁𝐚𝐭𝐜𝐡 » {b_name}

➭ 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐄𝐃 𝐁𝐘 : {CR}\n\n<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>**"""

if "drive" in url:  
                try:  
                    ka = await helper.download(url, name)  
                    copy = await bot.send_document(chat_id=m.chat.id,document=ka, caption=cc1)  
                    count+=1  
                    os.remove(ka)  
                    time.sleep(1)  
                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    time.sleep(e.x)  
                    continue  


            elif ".pdf?" in url or ".pdf?URLPrefix=" in url:  
                try:  
                    await asyncio.sleep(2)  
                    downloaded_pdf = await helper.download_secure_pdf(url, name)  
                    if downloaded_pdf and os.path.exists(downloaded_pdf):  
                        copy = await bot.send_document(  
                            chat_id=m.chat.id,  
                            document=downloaded_pdf,  
                            caption=cc1  
                        )  
                        count += 1  
                        os.remove(downloaded_pdf)  
                        print(f"[Bot Success] Successfully uploaded bypassed PDF: {downloaded_pdf}", flush=True)  
                    else:  
                        await m.reply_text(f"❌ Appx PDF download fail ho gaya.")  
                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    await asyncio.sleep(e.x)  
                    continue  
                          
            elif ".pdf" in url:  
                try:  
                    await asyncio.sleep(4)  
    # Replace spaces with %20 in the URL  
                    url = url.replace(" ", "%20")  

    # Create a cloudscraper session  
                    scraper = cloudscraper.create_scraper()  

    # Send a GET request to download the PDF  
                    response = scraper.get(url)  

    # Check if the response status is OK  
                    if response.status_code == 200:  
        # Write the PDF content to a file  
                        with open(f'{name}.pdf', 'wb') as file:  
                            file.write(response.content)  

        # Send the PDF document  
                        await asyncio.sleep(4)  
                        copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)  
                        count += 1  

        # Remove the PDF file after sending  
                        os.remove(f'{name}.pdf')  
                    else:  
                        await m.reply_text(f"Failed to download PDF: {response.status_code} {response.reason}")  

                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    time.sleep(e.x)  
                    continue  

            elif ".pdf" in url:  
                try:  
                    cmd = f'yt-dlp -o "{name}.pdf" "{url}"'  
                    download_cmd = f"{cmd} -R 25 --fragment-retries 25"  
                    os.system(download_cmd)  
                    copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)  
                    count += 1  
                    os.remove(f'{name}.pdf')  
                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    time.sleep(e.x)  
                    continue  
                      
            elif ".pdf*" in url:  
                try:  
                    # URL se key split karein (URL*KEY format check)  
                    enc_key = ""  
                    if "*" in url:  
                        url, enc_key = url.split("*", 1)  
                        url = url.strip()  
                        enc_key = enc_key.strip()  

                    # Clean single line call method  
                    downloaded_file = await helper.download_appxpdf(url, name, enc_key)  

                    if downloaded_file and os.path.exists(downloaded_file):  
                        copy = await bot.send_document(chat_id=m.chat.id, document=downloaded_file, caption=cc1)  
                        count += 1  
                        os.remove(downloaded_file)  
                    else:  
                        await m.reply_text(f"❌ **Decryption Failed:**")  
                        count += 1  
                      
                    time.sleep(1)  
                    continue  

                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    await asyncio.sleep(e.x)  
                    count += 1  
                    continue  
                except Exception as e:  
                    await m.reply_text(f"⚠️ **Error** {str(e)}")  
                    count += 1  
                    continue  
                      
              
                  
            elif "transcoded-videos.classx.co.in" in url.lower() or "classx.co.in" in url.lower():  
                Show = f"<pre><code></code></pre>\n\n🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢𝐭𝐥𝐞 » `{name}\n\n`⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2} \n **Url »** ᴜʀʟ ᴅᴇᴋʜ ᴋᴀʀ ᴋʏᴀ ᴋᴀʀᴏɢᴇ  \n🤗😎 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐌𝐲 𝐁𝐨𝐬𝐬 » @jaat_mk \n\n<code><pre>━━━━━━━✦जाटⁱˢß𝐚𝐜𝐤ツ✦━━━━━━━</pre></code>"  
                prog = await m.reply_text(Show)  
                res_file = await helper.download_secure_video(url, name)  
                filename = res_file  
                await prog.delete(True)  
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)  
                count += 1  
                time.sleep(1)  
                continue  


            elif 'akamai-cdn.classplusapp.com' in url:  
                Show = f"<pre><code>Class Plus</code></pre>\n\n🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢𝐭𝐥𝐞 » `{name}\n\n`⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2} \n **Url »** ᴜʀʟ ᴅᴇᴋʜ ᴋᴀʀ ᴋʏᴀ ᴋᴀʀᴏɢᴇ  \n🤗😎 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐌𝐲 𝐁𝐨𝐬𝐬 » @jaat_mk \n\n<code><pre>━━━━━━━✦जाटⁱˢß𝐚𝐜𝐤ツ✦━━━━━━━</pre></code>"  
                prog = await m.reply_text(Show)  
                output_filename = f"{name}.mp4"  
                res_file = new_classplus_cdn(url, raw_text2, output_filename)  
                filename = res_file  
                if WM != "/d":  
                    wm_file = f"wm_{filename}"  

                    os.system(  
                        f'''ffmpeg -y -i "{filename}" -vf "drawtext=text='{WM}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black:x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))" -codec:a copy "{wm_file}"'''  
                    )  

                    print("Watermark file exists:", os.path.exists(wm_file))  

                    if os.path.exists(wm_file):  
                        os.remove(filename)  
                        filename = wm_file  
                          
                await prog.delete(True)  
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)  
                count += 1  
                time.sleep(1)  
                continue  

            elif '/master.mpd' in url or "code.run" in url or "/dash/" in url or ".mp4?" in url or "?Signature=" in url or "d1d34p8vz63oiq.cloudfront.net" in url or "parentId=" in url or "childId=" in url:  
                Show = f"<pre><code>Physics Wallah</code></pre>\n\n🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢𝐭𝐥𝐞 » `{name}\n\n`⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2} \n **Url »** ᴜʀʟ ᴅᴇᴋʜ ᴋᴀʀ ᴋʏᴀ ᴋᴀʀᴏɢᴇ  \n🤗😎 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐌𝐲 𝐁𝐨𝐬𝐬 » @jaat_mk \n\n<code><pre>━━━━━━━✦जाटⁱˢß𝐚𝐜𝐤ツ✦━━━━━━━</pre></code>"  
                prog = await m.reply_text(Show)  
                output_filename = f"{name}.mp4"  
                res_file = pwdlx_video(url, output_filename)  
                filename = res_file  
                if WM != "/d":  
                    wm_file = f"wm_{filename}"  

                    os.system(  
                        f'''ffmpeg -y -i "{filename}" -vf "drawtext=text='{WM}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black:x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))" -codec:a copy "{wm_file}"'''  
                    )  

                    print("Watermark file exists:", os.path.exists(wm_file))  

                    if os.path.exists(wm_file):  
                        os.remove(filename)  
                        filename = wm_file  
                          
                await prog.delete(True)  
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)  
                count += 1  
                time.sleep(1)  
                continue  
                  
            else:  
                Show = f"❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢𝐭𝐥𝐞 » `{name}\n\n`⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2} \n **Url »** ᴜʀʟ ᴅᴇᴋʜ ᴋᴀʀ ᴋʏᴀ ᴋᴀʀᴏɢᴇ  \n🤗😎 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐌𝐲 𝐁𝐨𝐬𝐬 » @jaat_mk \n\n<code><pre>━━━━━━━✦जाटⁱˢß𝐚𝐜𝐤ツ✦━━━━━━━</pre></code>"  
                prog = await m.reply_text(Show)  
                res_file = await helper.download_video(url, cmd, name)  
                filename = res_file  
                print("Input file:", filename)  

                if WM != "/d":  
                    wm_file = f"wm_{filename}"  

                    os.system(  
                        f'''ffmpeg -y -i "{filename}" -vf "drawtext=text='{WM}':fontcolor=white:fontsize=30:borderw=2:bordercolor=black:x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))" -codec:a copy "{wm_file}"'''  
                    )  

                    print("Watermark file exists:", os.path.exists(wm_file))  

                    if os.path.exists(wm_file):  
                        os.remove(filename)  
                        filename = wm_file  

                await prog.delete(True)  
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)  
                count += 1  
                time.sleep(1)  
        except Exception as e:  
            await m.reply_text(  
                f"⌘ 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠 𝐈𝐧𝐭𝐞𝐫𝐮𝐩𝐭𝐞𝐝\n\n⌘ 𝐍𝐚𝐦𝐞 » {name}\n⌘ 𝐋𝐢𝐧𝐤 » `{url}`"  
            )  
            continue  

except Exception as e:  
    await m.reply_text(e)  

await m.reply_text("𝐄𝐕𝐄𝐑𝐘𝐓𝐇𝐈𝐍𝐆 𝐈𝐒 𝐃𝐎𝐍𝐄 ☑️ ")

Advance

@bot.on_message(filters.command(["/baby"]) )
async def txt_handler(bot: Client, m: Message):
editable = await m.reply_text(f"🔹Hi I am Poweful TXT Downloader📥 Bot.\n🔹Send me the TXT file and wait.")
input: Message = await bot.listen(editable.chat.id)
x = await input.download()
await input.delete(True)
file_name, ext = os.path.splitext(os.path.basename(x))
credit = f"@jaat_mk"
token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MzYxNTE3MzAuMTI2LCJkYXRhIjp7Il9pZCI6IjYzMDRjMmY3Yzc5NjBlMDAxODAwNDQ4NyIsInVzZXJuYW1lIjoiNzc2MTAxNzc3MCIsImZpcnN0TmFtZSI6IkplZXYgbmFyYXlhbiIsImxhc3ROYW1lIjoic2FoIiwib3JnYW5pemF0aW9uIjp7Il9pZCI6IjVlYjM5M2VlOTVmYWI3NDY4YTc5ZDE4OSIsIndlYnNpdGUiOiJwaHlzaWNzd2FsbGFoLmNvbSIsIm5hbWUiOiJQaHlzaWNzd2FsbGFoIn0sImVtYWlsIjoiV1dXLkpFRVZOQVJBWUFOU0FIQEdNQUlMLkNPTSIsInJvbGVzIjpbIjViMjdiZDk2NTg0MmY5NTBhNzc4YzZlZiJdLCJjb3VudHJ5R3JvdXAiOiJJTiIsInR5cGUiOiJVU0VSIn0sImlhdCI6MTczNTU0NjkzMH0.iImf90mFu_cI-xINBv4t0jVz-rWK1zeXOIwIFvkrS0M"
try:
with open(x, "r") as f:
content = f.read()
content = content.split("\n")
links = []
for i in content:
links.append(i.split("://", 1))
os.remove(x)
except:
await m.reply_text("Invalid file input.")
os.remove(x)
return

await editable.edit(f"Total links found are **{len(links)}**\n\nSend From where you want to download initial is **1**")  
input0: Message = await bot.listen(editable.chat.id)  
raw_text = input0.text  
await input0.delete(True)  
try:  
    arg = int(raw_text)  
except:  
    arg = 1  
await editable.edit("**Enter Your Batch Name or send 1 for grabing from text filename.**")  
input1: Message = await bot.listen(editable.chat.id)  
raw_text0 = input1.text  
await input1.delete(True)  
if raw_text0 == 'd':  
    b_name = file_name  
else:  
    b_name = raw_text0  

    await editable.edit("**Enter resolution.\n Eg : 480 or 720**")  
input2: Message = await bot.listen(editable.chat.id)  
raw_text2 = input2.text  
await input2.delete(True)  

try:  
    if raw_text2 == "144":  
        res = "256x144"  
    elif raw_text2 == "240":  
        res = "426x240"  
    elif raw_text2 == "360":  
        res = "640x360"  
    elif raw_text2 == "480":  
        res = "854x480"  
    elif raw_text2 == "720":  
        res = "1280x720"  
    elif raw_text2 == "1080":  
        res = "1920x1080"  
    else:  
        res = "UN"  
except Exception:  
    res = "UN"  

await editable.edit("**Enter Your Name or send '1' for use default.\n Eg : @SumitTripathi**")  
input3: Message = await bot.listen(editable.chat.id)  
raw_text3 = input3.text  
await input3.delete(True)  

if raw_text3 == 'de':  
    CR = credit  
else:  
    CR = raw_text3  

  
await editable.edit("**Enter Your PW Token For 𝐌𝐏𝐃 𝐔𝐑𝐋 or send '3' for use default**")  
input4: Message = await bot.listen(editable.chat.id)  
raw_text4 = input4.text  
await input4.delete(True)  

if raw_text4 == 'unknown':  
    access_token = token  
else:  
    access_token = raw_text4  
      
     
await editable.edit("Now send the **Thumb url**\n**Eg :** ``\n\nor Send `no`")  
input6 = message = await bot.listen(editable.chat.id)  
raw_text6 = input6.text  
await input6.delete(True)  
await editable.delete()  

thumb = input6.text  
if thumb.startswith("http://") or thumb.startswith("https://files.catbox.moe/mwhput.jpg"):  
    getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")  
    thumb = "thumb.jpg"  
else:  
    thumb == "no"  

count =int(raw_text)      
try:  
    for i in range(arg-1, len(links)):  

        Vxy = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")  
        url = "https://" + Vxy  
        if "visionias" in url:  
            async with ClientSession() as session:  
                async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:  
                    text = await resp.text()  
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)  

        if "acecwply" in url:  
            cmd = f'yt-dlp -o "{name}.%(ext)s" -f "bestvideo[height<={raw_text2}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'  
              

        if "visionias" in url:  
            async with ClientSession() as session:  
                async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:  
                    text = await resp.text()  
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)  

        elif 'https://contentId=' in url or 'contentHashIdl=' in url:  
            content_id = extract_content_id(url)  
            cpurl = get_jw_signed_url(content_id, access_token)  
            print(f"Fetched URL: {cpurl}") # Debugging ke liye  
            url = cpurl  
            print(f"CP Url: {url}")  
              
        elif '/master.mpd' in url:  
         vid_id =  url.split("/")[-2]  
         url =  f"https://pw-url-api-v1mf.onrender.com/process?v=https://sec1.pw.live/{vid_id}/master.mpd&quality={raw_text2}"  

        name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()  
        name = f'{str(count).zfill(3)}) {name1[:60]} {my_name}'  
        

        if "edge.api.brightcove.com" in url:  
            bcov = 'bcov_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MjQyMzg3OTEsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiJVMFZ6TkdGU2NuQlZjR3h5TkZwV09FYzBURGxOZHowOSIsImlkIjoiZEUxbmNuZFBNblJqVEROVmFWTlFWbXhRTkhoS2R6MDkiLCJmaXJzdF9uYW1lIjoiYVcxV05ITjVSemR6Vm10ak1WUlBSRkF5ZVNzM1VUMDkiLCJlbWFpbCI6Ik5Ga3hNVWhxUXpRNFJ6VlhiR0ppWTJoUk0wMVdNR0pVTlU5clJXSkRWbXRMTTBSU2FHRnhURTFTUlQwPSIsInBob25lIjoiVUhVMFZrOWFTbmQ1ZVcwd1pqUTViRzVSYVc5aGR6MDkiLCJhdmF0YXIiOiJLM1ZzY1M4elMwcDBRbmxrYms4M1JEbHZla05pVVQwOSIsInJlZmVycmFsX2NvZGUiOiJOalZFYzBkM1IyNTBSM3B3VUZWbVRtbHFRVXAwVVQwOSIsImRldmljZV90eXBlIjoiYW5kcm9pZCIsImRldmljZV92ZXJzaW9uIjoiUShBbmRyb2lkIDEwLjApIiwiZGV2aWNlX21vZGVsIjoiU2Ftc3VuZyBTTS1TOTE4QiIsInJlbW90ZV9hZGRyIjoiNTQuMjI2LjI1NS4xNjMsIDU0LjIyNi4yNTUuMTYzIn19.snDdd-PbaoC42OUhn5SJaEGxq0VzfdzO49WTmYgTx8ra_Lz66GySZykpd2SxIZCnrKR6-R10F5sUSrKATv1CDk9ruj_ltCjEkcRq8mAqAytDcEBp72-W0Z7DtGi8LdnY7Vd9Kpaf499P-y3-godolS_7ixClcYOnWxe2nSVD5C9c5HkyisrHTvf6NFAuQC_FD3TzByldbPVKK0ag1UnHRavX8MtttjshnRhv5gJs5DQWj4Ir_dkMcJ4JaVZO3z8j0OxVLjnmuaRBujT-1pavsr1CCzjTbAcBvdjUfvzEhObWfA1-Vl5Y4bUgRHhl1U-0hne4-5fF0aouyu71Y6W0eg'  
            url = url.split("bcov_auth")[0]+bcov  
              
        if "youtu" in url:  
            ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"  
        else:  
            ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"  
          
        if "jw-prod" in url:  
            cmd = f'yt-dlp -o "{name}.mp4" "{url}"'  

        elif "youtube.com" in url or "youtu.be" in url:  
            cmd = f'yt-dlp --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}".mp4'  

        else:  
            cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'  

        try:    
      
            cc = f'**🏷️ Iɴᴅᴇx ID: {str(count).zfill(3)}.\n\n🎞️Tɪᴛʟᴇ: {name1} {res}.mkv\n\n<pre><code>📚 𝗕ᴀᴛᴄʜ: {b_name}</code></pre>\n\n📥 Uᴘʟᴏᴀᴅ Bʏ : </b> {CR}\n\n<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>'  
            cc1 = f'**🏷️ Iɴᴅᴇx ID: {str(count).zfill(3)}.\n\n📑Tɪᴛʟᴇ: {name1} .pdf\n\n<pre><code>📚 𝗕ᴀᴛᴄʜ: {b_name}</code></pre>\n\n📥 Uᴘʟᴏᴀᴅ Bʏ : </b> {CR}\n\n<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>'  
                  
              
            if "drive" in url:  
                try:  
                    ka = await helper.download(url, name)  
                    copy = await bot.send_document(chat_id=m.chat.id,document=ka, caption=cc1)  
                    count+=1  
                    os.remove(ka)  
                    time.sleep(1)  
                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    time.sleep(e.x)  
                    continue  

            elif ".pdf" in url:  
                try:  
                    await asyncio.sleep(4)  
    # Replace spaces with %20 in the URL  
                    url = url.replace(" ", "%20")  

    # Create a cloudscraper session  
                    scraper = cloudscraper.create_scraper()  

    # Send a GET request to download the PDF  
                    response = scraper.get(url)  

    # Check if the response status is OK  
                    if response.status_code == 200:  
        # Write the PDF content to a file  
                        with open(f'{name}.pdf', 'wb') as file:  
                            file.write(response.content)  

        # Send the PDF document  
                        await asyncio.sleep(4)  
                        copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)  
                        count += 1  

        # Remove the PDF file after sending  
                        os.remove(f'{name}.pdf')  
                    else:  
                        await m.reply_text(f"Failed to download PDF: {response.status_code} {response.reason}")  

                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    time.sleep(e.x)  
                    continue  

            elif ".pdf" in url:  
                try:  
                    cmd = f'yt-dlp -o "{name}.pdf" "{url}"'  
                    download_cmd = f"{cmd} -R 25 --fragment-retries 25"  
                    os.system(download_cmd)  
                    copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)  
                    count += 1  
                    os.remove(f'{name}.pdf')  
                except FloodWait as e:  
                    await m.reply_text(str(e))  
                    time.sleep(e.x)  
                    continue                         

            elif 'akamai-cdn.classplusapp.com' in url:  
                Show = f"<pre><code>Class Plus</code></pre>\n\n🚀❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊\n\n 📄 𝐓𝐢𝐭𝐥𝐞 » `{name}\n\n`⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2} \n **Url »** ᴜʀʟ ᴅᴇᴋʜ ᴋᴀʀ ᴋʏᴀ ᴋᴀʀᴏɢᴇ  \n🤗😎 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐌𝐲 𝐁𝐨𝐬𝐬 » @jaat_mk \n\n<code><pre>━━━━━━━✦जाटⁱˢß𝐚𝐜𝐤ツ✦━━━━━━━</pre></code>"  
                prog = await m.reply_text(Show)  
                output_filename = f"{name}.mp4"  
                res_file = new_classplus_cdn(url, raw_text2, output_filename)  
                filename = res_file  
                await prog.delete(True)  
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)  
                count += 1  
                time.sleep(1)  
                continue  

              
            else:  
                Show = f"""❊━━━⟱ 🚀𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠🚀 ⟱━━━❊

📄 𝐓𝐢𝐭𝐥𝐞 » {name}

⌨ 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2}

🤖 Hello: ᴜʀʟ ᴅᴇᴋʜ ᴋᴀʀ ᴋʏᴀ ᴋᴀʀᴏɢᴇ 🤗

😎 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐌𝐲 𝐁𝐨𝐬𝐬 » @jaat_mk
"""
prog = await m.reply_text(Show)
res_file = await helper.download_video(url, cmd, name)
filename = res_file
await prog.delete(True)
await helper.send_vid(bot, m, cc, filename, thumb, name, prog)
count += 1
time.sleep(1)

except Exception as e:  
            await m.reply_text(  
                f"⌘ 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠 𝐈𝐧𝐭𝐞𝐫𝐮𝐩𝐭𝐞𝐝\n\n⌘ 𝐍𝐚𝐦𝐞 » {name}\n⌘ 𝐋𝐢𝐧𝐤 » `{url}`"  
            )  
            continue  

except Exception as e:  
    await m.reply_text(e)  
await m.reply_text("𝐀𝐋𝐋 𝐃𝐎𝐍𝐄 ✅ 𝐓𝐈𝐋𝐋 𝐍𝐎𝐖 ")

if name == "main":
bot.run()
