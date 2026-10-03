import os
import re
import sys
import time
import asyncio
import logging
import subprocess
import requests
import cloudscraper

from urllib.parse import quote, urlparse
from aiohttp import ClientSession, web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyromod import listen

import yt_dlp
import core as helper

from vars import API_ID, API_HASH, BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

my_name = "Zx"
COOKIES_FILE_PATH = os.getenv(
    "COOKIES_FILE_PATH",
    "youtube_cookies.txt",
)

bot = Client(
    "bot",
    api_id=37721193,
    api_hash="ed5cbbc0e14a777e1b2deb0c3f763874",
    bot_token="8889799148:AAGA5Axh88UAiHEvpUPxX5leXQB9gKOHRIw",
)

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route(request):
    return web.json_response({"status": "Bot is Running!"})


async def web_server():
    app = web.Application(client_max_size=30000000)
    app.add_routes(routes)
    return app


async def download_signed_mp4(url: str, output_file: str):
    """
    Downloads an already-authorized signed CloudFront MP4 URL.
    No key extraction or DRM bypass is performed.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }

    timeout = __import__("aiohttp").ClientTimeout(
        total=None,
        connect=30,
        sock_read=120,
    )

    async with ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Signed MP4 download failed: HTTP {response.status}"
                )

            with open(output_file, "wb") as file:
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    if chunk:
                        file.write(chunk)

    if not os.path.exists(output_file):
        raise RuntimeError("Output file was not created.")

    if os.path.getsize(output_file) == 0:
        raise RuntimeError("Downloaded file is empty.")

    return output_file


def is_signed_cloudfront_mp4(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    return (
        host == "d1d34p8vz63oiq.cloudfront.net"
        and ".mp4" in parsed.path.lower()
        and "Signature=" in parsed.query
        and "Key-Pair-Id=" in parsed.query
        and "Policy=" in parsed.query
    )


def pwdlx_video(url: str, output_filename: str):
    """
    Normal yt-dlp/aria2c download for URLs that yt-dlp can access normally.
    """
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
    logger.info("extract_content_id called")

    try:
        if "contentId=" not in url:
            return None

        content_id = url.split("contentId=", 1)[1]

        for char in ("?", "&"):
            if char in content_id:
                content_id = content_id.split(char, 1)[0]

        if content_id.endswith(".m3u8"):
            content_id = content_id[:-5]
        elif ".m3u8" in content_id:
            content_id = content_id.split(".m3u8", 1)[0]

        return content_id or None

    except Exception:
        logger.exception("Could not extract content ID")
        return None


def get_jw_signed_url(content_id, access_token):
    if not content_id:
        return None

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

    response = requests.get(
        content_api,
        headers=headers,
        timeout=15,
    )

    if response.ok:
        data = response.json()
        signed_url = data.get("url")

        if signed_url:
            hostname = (urlparse(signed_url).hostname or "").lower()

            if hostname == "akamai-cdn.classplusapp.com":
                return signed_url

    live_api = (
        "https://api.classplusapp.com/cams/uploader/video/"
        f"jw-signed-url?liveSessionId={quote(content_id, safe='')}"
        "&isAgora=2"
    )

    response = requests.get(
        live_api,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()

    signed_url = response.json().get("url")
    return signed_url


def new_classplus_cdn(url, quality, output_filename):
    format_selector = (
        f"bestvideo[height<={quality}]"
        f"+bestaudio/best[height<={quality}]"
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


def safe_filename(value, max_len=60):
    value = re.sub(r"[\\/:*?\"<>|]+", "", value)
    value = value.replace("https", "").replace("http", "")
    value = value.strip()
    return value[:max_len] or "video"


def make_caption(index, title, batch, credit, resolution):
    return (
        f"**🏷️ Iɴᴅᴇx ID: {str(index).zfill(3)}.**\n\n"
        f"🎞️ **Tɪᴛʟᴇ:** {title} {resolution}\n\n"
        f"<pre><code>📚 𝗕ᴀᴛᴄʜ: {batch}</code></pre>\n\n"
        f"📥 **Uᴘʟᴏᴀᴅ Bʏ:** {credit}\n\n"
        f"<pre><code>━━━━━✦𝗭𝗫✦━━━━━</code></pre>"
    )


async def apply_watermark(filename, watermark):
    if not watermark or watermark == "/d":
        return filename

    output = f"wm_{os.path.basename(filename)}"

    vf = (
        "drawtext="
        f"text='{watermark.replace(chr(39), chr(92) + chr(39))}':"
        "fontcolor=white:fontsize=30:borderw=2:bordercolor=black:"
        "x=mod(t*120\\,(w-text_w)):y=mod(t*70\\,(h-text_h))"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        filename,
        "-vf",
        vf,
        "-codec:a",
        "copy",
        output,
    ]

    process = await asyncio.create_subprocess_exec(*cmd)
    return_code = await process.wait()

    if return_code != 0 or not os.path.exists(output):
        return filename

    try:
        os.remove(filename)
    except OSError:
        pass

    return output


class Data:
    START = "🦋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ʙᴀʙʏ 🦋 {0}\n\n"


@bot.on_message(filters.command("start"))
async def start_handler(client: Client, msg: Message):
    mention = msg.from_user.mention if msg.from_user else "User"

    start_message = await msg.reply_text(
        Data.START.format(mention) +
        "Initializing Uploader bot... 🤖\n\n"
        "Progress: [⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(mention) +
        "Loading features... ⏳\n\n"
        "Progress: [🟥🟥🟥⬜⬜⬜⬜⬜⬜] 25%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(mention) +
        "Checking Bot Status... 🔍\n\n"
        "Progress: [🟨🟨🟨🟨🟨🟨🟨⬜⬜] 75%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(mention) +
        "ᴄʜᴇᴄᴋɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴀᴄᴛɪᴠᴇ... ✅\n\n"
        "Progress: [🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%"
    )


@bot.on_message(filters.command("stop"))
async def stop_handler(_, msg: Message):
    await msg.reply_text("STOPPED 🛑")
    await bot.stop()


@bot.on_message(filters.command("baby"))
async def txt_handler(client: Client, m: Message):
    editable = await m.reply_text(
        "🍁 **I'm a powerful TXT downloader bot.**\n"
        "🍁 Send a TXT file and let the process begin..."
    )

    input_msg = await client.listen(editable.chat.id)
    x = await input_msg.download()
    await input_msg.delete(True)

    file_name, _ = os.path.splitext(os.path.basename(x))

    try:
        with open(x, "r", encoding="utf-8", errors="ignore") as file:
            lines = [
                line.strip()
                for line in file.read().splitlines()
                if line.strip()
            ]
    except Exception:
        await editable.edit("❌ Invalid TXT file.")
        try:
            os.remove(x)
        except OSError:
            pass
        return

    try:
        os.remove(x)
    except OSError:
        pass

    if not lines:
        await editable.edit("❌ No links found in TXT.")
        return

    await editable.edit(
        f"**Total links found:** `{len(lines)}`\n\n"
        "Send the starting index. Default: `1`"
    )
    input0 = await client.listen(editable.chat.id)
    start_text = (input0.text or "1").strip()
    await input0.delete(True)

    try:
        start_index = max(1, int(start_text))
    except ValueError:
        start_index = 1

    await editable.edit(
        "**Enter your Batch Name or send `d` to use TXT filename.**"
    )
    input1 = await client.listen(editable.chat.id)
    batch = (input1.text or "").strip()
    await input1.delete(True)

    if batch.lower() == "d" or not batch:
        batch = file_name

    await editable.edit("**Enter resolution:** `144 / 240 / 360 / 480 / 720 / 1080`")
    input2 = await client.listen(editable.chat.id)
    quality = (input2.text or "720").strip()
    await input2.delete(True)

    allowed_quality = {"144", "240", "360", "480", "720", "1080"}
    if quality not in allowed_quality:
        quality = "720"

    resolution_map = {
        "144": "256x144",
        "240": "426x240",
        "360": "640x360",
        "480": "854x480",
        "720": "1280x720",
        "1080": "1920x1080",
    }
    resolution = resolution_map[quality]

    await editable.edit("**Enter Watermark Text or send `/d` for no watermark.**")
    input_wm = await client.listen(editable.chat.id)
    watermark = (input_wm.text or "/d").strip()
    await input_wm.delete(True)

    await editable.edit(
        "**Enter your name/credit or send `d` for default `@jaat_mk`.**"
    )
    input3 = await client.listen(editable.chat.id)
    credit = (input3.text or "d").strip()
    await input3.delete(True)

    if credit.lower() == "d":
        credit = "@jaat_mk"

    # Optional ClassPlus access token supplied by the authorized user.
    await editable.edit(
        "**If you have an authorized ClassPlus access token, send it.**\n"
        "Otherwise send `no`."
    )
    input4 = await client.listen(editable.chat.id)
    access_token = (input4.text or "no").strip()
    await input4.delete(True)

    await editable.edit(
        "**Send thumbnail URL or `no`.**"
    )
    input_thumb = await client.listen(editable.chat.id)
    thumb_url = (input_thumb.text or "no").strip()
    await input_thumb.delete(True)
    await editable.delete()

    thumb = "no"

    if thumb_url.startswith(("http://", "https://")):
        try:
            response = requests.get(thumb_url, timeout=20)
            response.raise_for_status()

            with open("thumb.jpg", "wb") as file:
                file.write(response.content)

            thumb = "thumb.jpg"
        except Exception:
            thumb = "no"

    count = start_index

    for line_index in range(start_index - 1, len(lines)):
        raw_url = lines[line_index]

        # Accept either a normal URL or the old "title://url" format.
        if "://" in raw_url:
            title_part, url_part = raw_url.split("://", 1)
            url = "https://" + url_part
        else:
            title_part = f"Link {count}"
            url = raw_url

        url = (
            url.replace(
                "file/d/",
                "uc?export=download&id="
            )
            .replace(
                "www.youtube-nocookie.com/embed",
                "youtu.be"
            )
            .replace("?modestbranding=1", "")
            .replace("/view?usp=sharing", "")
        )

        name1 = safe_filename(title_part)
        name = f"{str(count).zfill(3)}) {name1} {my_name}"
        output_filename = f"{name}.mp4"

        try:
            # VisionIAS page -> playlist URL.
            if "visionias" in url.lower():
                async with ClientSession() as session:
                    async with session.get(url) as response:
                        text = await response.text()

                match = re.search(
                    r"(https://.*?playlist\.m3u8.*?)\"",
                    text,
                )

                if not match:
                    raise RuntimeError("VisionIAS playlist URL not found.")

                url = match.group(1)

            # ClassPlus signed URL flow.
            if "contentId=" in url:
                content_id = extract_content_id(url)

                if not content_id:
                    raise RuntimeError("ClassPlus content ID not found.")

                if access_token.lower() == "no":
                    raise RuntimeError(
                        "Authorized ClassPlus access token required."
                    )

                signed_url = get_jw_signed_url(
                    content_id,
                    access_token,
                )

                if not signed_url:
                    raise RuntimeError(
                        "ClassPlus signed URL was not returned."
                    )

                url = signed_url

            caption = make_caption(
                count,
                name1,
                batch,
                credit,
                resolution,
            )

            # Direct, already-authorized signed CloudFront MP4.
            if is_signed_cloudfront_mp4(url):
                prog = await m.reply_text(
                    f"⬇️ Downloading signed MP4...\n\n`{name}`"
                )

                filename = await download_signed_mp4(
                    url,
                    output_filename,
                )

                filename = await apply_watermark(
                    filename,
                    watermark,
                )

                await prog.delete()
                await helper.send_vid(
                    client,
                    m,
                    caption,
                    filename,
                    thumb,
                    name,
                    prog,
                )

                if os.path.exists(filename):
                    os.remove(filename)

                count += 1
                await asyncio.sleep(1)
                continue

            # ClassPlus Akamai.
            if "akamai-cdn.classplusapp.com" in url:
                prog = await m.reply_text(
                    f"⬇️ Downloading ClassPlus video...\n\n`{name}`"
                )

                filename = new_classplus_cdn(
                    url,
                    quality,
                    output_filename,
                )

                filename = await apply_watermark(
                    filename,
                    watermark,
                )

                await prog.delete()
                await helper.send_vid(
                    client,
                    m,
                    caption,
                    filename,
                    thumb,
                    name,
                    prog,
                )

                if os.path.exists(filename):
                    os.remove(filename)

                count += 1
                await asyncio.sleep(1)
                continue

            # Google Drive.
            if "drive" in url.lower():
                file_path = await helper.download(url, name)

                await client.send_document(
                    chat_id=m.chat.id,
                    document=file_path,
                    caption=caption,
                )

                if file_path and os.path.exists(file_path):
                    os.remove(file_path)

                count += 1
                await asyncio.sleep(1)
                continue

            # PDF.
            if ".pdf" in url.lower():
                pdf_path = f"{name}.pdf"

                scraper = cloudscraper.create_scraper()
                response = scraper.get(
                    url.replace(" ", "%20"),
                    timeout=60,
                )
                response.raise_for_status()

                with open(pdf_path, "wb") as file:
                    file.write(response.content)

                await client.send_document(
                    chat_id=m.chat.id,
                    document=pdf_path,
                    caption=caption,
                )

                if os.path.exists(pdf_path):
                    os.remove(pdf_path)

                count += 1
                await asyncio.sleep(1)
                continue

            # Normal yt-dlp download.
            prog = await m.reply_text(
                f"⬇️ Downloading...\n\n`{name}`\n\n"
                f"Quality: `{quality}p`"
            )

            if "youtube.com" in url or "youtu.be" in url:
                ytf = (
                    f"b[height<={quality}][ext=mp4]/"
                    f"bv[height<={quality}][ext=mp4]+ba[ext=m4a]/"
                    f"b[ext=mp4]"
                )

                cmd = (
                    f'yt-dlp --cookies "{COOKIES_FILE_PATH}" '
                    f'-f "{ytf}" "{url}" -o "{name}.mp4"'
                )
            else:
                ytf = (
                    f"b[height<={quality}]/"
                    f"bv[height<={quality}]+ba/b/bv+ba"
                )

                cmd = (
                    f'yt-dlp -f "{ytf}" '
                    f'"{url}" -o "{name}.mp4"'
                )

            filename = await helper.download_video(
                url,
                cmd,
                name,
            )

            if not filename or not os.path.exists(filename):
                raise RuntimeError("Downloader did not create a file.")

            filename = await apply_watermark(
                filename,
                watermark,
            )

            await prog.delete()

            await helper.send_vid(
                client,
                m,
                caption,
                filename,
                thumb,
                name,
                prog,
            )

            if os.path.exists(filename):
                os.remove(filename)

            count += 1
            await asyncio.sleep(1)

        except FloodWait as exc:
            await asyncio.sleep(exc.value)
            continue

        except Exception as exc:
            logger.exception("Download failed")
            await m.reply_text(
                "❌ Download interrupted.\n\n"
                f"**Name:** `{name}`\n"
                f"**Error:** `{str(exc)[:1000]}`"
            )
            count += 1
            continue

    if thumb != "no" and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except OSError:
            pass

    await m.reply_text("𝐀𝐋𝐋 𝐃𝐎𝐍𝐄 ✅")


async def main():
    await bot.start()

    me = await bot.get_me()
    print(
        f"Bot Started Successfully as "
        f"@{me.username or me.first_name}"
    )

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
