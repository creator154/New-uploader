import os
import re
import sys
import asyncio
import subprocess
import logging
from urllib.parse import quote, urlparse

import requests
import cloudscraper
import yt_dlp

import core as helper
from vars import API_ID, API_HASH, BOT_TOKEN

from aiohttp import ClientSession, web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyromod import listen


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

MY_NAME = "Zx"
COOKIES_FILE_PATH = os.getenv(
    "COOKIES_FILE_PATH",
    "/modules/youtube_cookies.txt"
)

CREDIT = "@SumitTripathi"


# =========================================================
# BOT
# =========================================================

bot = Client(
    "bot",
    api_id=37721193,
    api_hash="ed5cbbc0e14a777e1b2deb0c3f763874",
    bot_token="8447894911:AAF6DVriwIb8J9WVewP3HFFSTMMvXaVXg2o"
)


# =========================================================
# WEB SERVER
# =========================================================

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root(request):
    return web.Response(text="Bot is Running!")


async def web_server():
    app = web.Application()
    app.add_routes(routes)
    return app


# =========================================================
# HELPERS
# =========================================================

def safe_filename(value: str) -> str:
    """Create a filesystem-safe filename."""
    value = value or "video"

    value = re.sub(r'[\\/:*?"<>|]+', "", value)
    value = value.replace("\t", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()[:100] or "video"


def safe_log_url(url: str) -> str:
    """Don't log query strings/tokens."""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return "<invalid-url>"


def get_resolution_label(resolution: str) -> str:
    return {
        "144": "256x144",
        "240": "426x240",
        "360": "640x360",
        "480": "854x480",
        "720": "1280x720",
        "1080": "1920x1080",
    }.get(resolution, "UN")


def apply_watermark(filename: str, watermark: str) -> str:
    """
    Apply watermark using ffmpeg.
    Returns original file if watermark is disabled.
    """

    if not watermark or watermark == "/d":
        return filename

    wm_file = f"wm_{os.path.basename(filename)}"

    # Escape characters for ffmpeg drawtext.
    wm = (
        watermark
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        filename,
        "-vf",
        (
            f"drawtext=text='{wm}':"
            "fontcolor=white:"
            "fontsize=30:"
            "borderw=2:"
            "bordercolor=black:"
            "x=mod(t*120\\,(w-text_w)):"
            "y=mod(t*70\\,(h-text_h))"
        ),
        "-codec:a",
        "copy",
        wm_file,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        if result.returncode != 0:
            logger.error(
                "Watermark failed:\n%s",
                result.stdout[-3000:]
            )
            return filename

        if os.path.exists(wm_file):
            try:
                os.remove(filename)
            except OSError:
                pass

            return wm_file

    except Exception:
        logger.exception("Watermark exception")

    return filename


def extract_content_id(url: str):
    """
    Extract ClassPlus contentId.
    """

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

        return content_id.strip() or None

    except Exception:
        logger.exception("contentId extraction failed")
        return None


def get_jw_signed_url(content_id, access_token):
    """
    Fetch authorized ClassPlus signed URL.
    """

    if not content_id:
        return None

    if not access_token:
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

    try:
        response = requests.get(
            content_api,
            headers=headers,
            timeout=15
        )

        logger.info(
            "ClassPlus content API status: %s",
            response.status_code
        )

        if response.ok:
            data = response.json()
            signed_url = data.get("url")

            if signed_url:
                hostname = (
                    urlparse(signed_url).hostname or ""
                ).lower()

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
            timeout=15
        )

        logger.info(
            "ClassPlus live API status: %s",
            response.status_code
        )

        response.raise_for_status()

        data = response.json()

        return data.get("url")

    except Exception:
        logger.exception("ClassPlus signed URL request failed")
        return None


def new_classplus_cdn(url, resolution, output_filename):
    """
    Download an authorized ClassPlus CDN URL.
    """

    format_selector = (
        f"bestvideo[height<={resolution}]"
        f"+bestaudio/"
        f"best[height<={resolution}]"
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

        "--add-header",
        "Origin: https://web.classplusapp.com",

        "--add-header",
        "Referer: https://web.classplusapp.com/",

        "-o",
        output_filename,
        url,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "ClassPlus download failed:\n"
            + result.stdout[-4000:]
        )

    if not os.path.exists(output_filename):
        raise FileNotFoundError(
            f"Output file not created: {output_filename}"
        )

    return output_filename


def download_with_ytdlp(url, output_filename, resolution):
    """
    Normal authorized media downloader.
    """

    format_selector = (
        f"bestvideo[height<={resolution}]"
        f"+bestaudio/"
        f"best[height<={resolution}]"
        if resolution.isdigit()
        else "bestvideo+bestaudio/best"
    )

    cmd = [
        "yt-dlp",
        "--newline",
        "--no-warnings",
        "-f",
        format_selector,
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "-o",
        output_filename,
        url,
    ]

    if "youtube.com" in url or "youtu.be" in url:
        if os.path.exists(COOKIES_FILE_PATH):
            cmd[1:1] = [
                "--cookies",
                COOKIES_FILE_PATH
            ]

    logger.info(
        "Downloading: %s",
        safe_log_url(url)
    )

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    logger.info(
        "yt-dlp return code: %s",
        result.returncode
    )

    if result.returncode != 0:
        raise RuntimeError(
            "yt-dlp failed:\n"
            + result.stdout[-5000:]
        )

    if not os.path.exists(output_filename):
        raise FileNotFoundError(
            f"Output file not created: {output_filename}"
        )

    return output_filename


async def download_pdf(url, filename):
    """
    Normal PDF downloader.
    """

    url = url.replace(" ", "%20")

    scraper = cloudscraper.create_scraper()

    response = await asyncio.to_thread(
        scraper.get,
        url,
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"PDF download failed: HTTP {response.status_code}"
        )

    output = f"{filename}.pdf"

    with open(output, "wb") as file:
        file.write(response.content)

    return output


async def resolve_visionias(url):
    """
    Resolve normal VisionIAS playlist URL.
    """

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "http://www.visionias.in/",
    }

    async with ClientSession() as session:
        async with session.get(
            url,
            headers=headers,
            timeout=30
        ) as response:

            text = await response.text()

    match = re.search(
        r'(https://.*?playlist\.m3u8.*?)"',
        text
    )

    if not match:
        raise RuntimeError(
            "VisionIAS playlist URL not found."
        )

    return match.group(1)


# =========================================================
# START MESSAGE
# =========================================================

class Data:
    START = (
        "🦋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ʙᴀʙʏ 🦋 {0}\n\n"
    )


@bot.on_message(filters.command("start"))
async def start(client: Client, msg: Message):

    start_message = await client.send_message(
        msg.chat.id,
        Data.START.format(msg.from_user.mention)
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(msg.from_user.mention)
        + "Initializing Uploader bot... 🤖\n\n"
        "Progress: [⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(msg.from_user.mention)
        + "Loading features... ⏳\n\n"
        "Progress: [🟥🟥🟥⬜⬜⬜⬜⬜⬜] 25%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(msg.from_user.mention)
        + "This may take a moment, sit back and relax! 😊\n\n"
        "Progress: [🟧🟧🟧🟧🟧⬜⬜⬜⬜] 50%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(msg.from_user.mention)
        + "Checking Bot Status... 🔍\n\n"
        "Progress: [🟨🟨🟨🟨🟨🟨🟨⬜⬜] 75%"
    )

    await asyncio.sleep(1)

    await start_message.edit_text(
        Data.START.format(msg.from_user.mention)
        + "ᴄʜᴇᴄᴋɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴀᴄᴛɪᴠᴇ... 🙃\n\n"
        "ᴄᴏɴᴛᴀᴄᴛ @SumitTripathi 🔍\n\n"
        "ᴘʀᴏɢʀᴇꜱꜱ: "
        "[🟩🟥🟩🟥🟩🟥🟩🟥🟩] 100%"
    )


# =========================================================
# STOP
# =========================================================

@bot.on_message(filters.command("stop"))
async def stop_handler(_, m):

    await m.reply_text("**STOPPED** 🛑", True)

    os.execl(
        sys.executable,
        sys.executable,
        *sys.argv
    )


# =========================================================
# BABY
# =========================================================

@bot.on_message(filters.command("baby"))
async def txt_handler(client: Client, m: Message):

    editable = await m.reply_text(
        "**🍁 ʜɪ, ɪ'ᴍ ᴘᴏᴡᴇʀꜰᴜʟ ᴛxᴛ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ.**\n\n"
        "🍁 **Send a TXT file and let the process begin...**"
    )

    # -----------------------------------------------------
    # TXT
    # -----------------------------------------------------

    input_file = await client.listen(editable.chat.id)

    x = await input_file.download()

    await input_file.delete(True)

    file_name, ext = os.path.splitext(
        os.path.basename(x)
    )

    try:
        with open(
            x,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:
            content = file.read()

        raw_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip()
        ]

        links = []

        for line in raw_lines:

            if "://" not in line:
                continue

            title, link = line.split(
                "://",
                1
            )

            links.append(
                [title, link]
            )

        os.remove(x)

    except Exception:
        logger.exception("TXT parsing failed")

        if os.path.exists(x):
            os.remove(x)

        await m.reply_text(
            "❌ Invalid TXT file input."
        )
        return

    if not links:
        await m.reply_text(
            "❌ TXT file me valid links nahi mile."
        )
        return

    # -----------------------------------------------------
    # START INDEX
    # -----------------------------------------------------

    await editable.edit(
        f"Total links found: **{len(links)}**\n\n"
        "Send starting index. Default: **1**"
    )

    input0 = await client.listen(
        editable.chat.id
    )

    try:
        arg = int(input0.text.strip())
    except Exception:
        arg = 1

    await input0.delete(True)

    if arg < 1:
        arg = 1

    # -----------------------------------------------------
    # BATCH NAME
    # -----------------------------------------------------

    await editable.edit(
        "**Enter Batch Name**\n"
        "Send `d` to use TXT filename."
    )

    input1 = await client.listen(
        editable.chat.id
    )

    raw_text0 = input1.text.strip()

    await input1.delete(True)

    if raw_text0.lower() == "d":
        b_name = file_name
    else:
        b_name = raw_text0 or file_name

    # -----------------------------------------------------
    # RESOLUTION
    # -----------------------------------------------------

    await editable.edit(
        "**Enter resolution:**\n"
        "`144 / 240 / 360 / 480 / 720 / 1080`"
    )

    input2 = await client.listen(
        editable.chat.id
    )

    raw_text2 = input2.text.strip()

    await input2.delete(True)

    if raw_text2 not in {
        "144",
        "240",
        "360",
        "480",
        "720",
        "1080",
    }:
        raw_text2 = "720"

    res = get_resolution_label(raw_text2)

    # -----------------------------------------------------
    # WATERMARK
    # -----------------------------------------------------

    await editable.edit(
        "**Enter Watermark Text**\n"
        "Send `/d` for no watermark."
    )

    input_wm = await client.listen(
        editable.chat.id
    )

    WM = input_wm.text.strip()

    await input_wm.delete(True)

    # -----------------------------------------------------
    # CREDIT
    # -----------------------------------------------------

    await editable.edit(
        "**Enter Your Name**\n"
        "Send `de` for default."
    )

    input3 = await client.listen(
        editable.chat.id
    )

    raw_text3 = input3.text.strip()

    await input3.delete(True)

    if raw_text3.lower() == "de":
        CR = CREDIT
    else:
        CR = raw_text3 or CREDIT

    # -----------------------------------------------------
    # CLASSPLUS TOKEN
    # -----------------------------------------------------

    await editable.edit(
        "**Enter authorized ClassPlus token**\n"
        "Send `unknown` if not required."
    )

    input4 = await client.listen(
        editable.chat.id
    )

    access_token = input4.text.strip()

    await input4.delete(True)

    if access_token.lower() == "unknown":
        access_token = ""

    # -----------------------------------------------------
    # THUMB
    # -----------------------------------------------------

    await editable.edit(
        "**Send Thumb URL**\n"
        "or send `no`"
    )

    input6 = await client.listen(
        editable.chat.id
    )

    thumb_input = input6.text.strip()

    await input6.delete(True)
    await editable.delete()

    thumb = "no"

    if thumb_input.startswith(
        ("http://", "https://")
    ):

        try:
            result = subprocess.run(
                [
                    "wget",
                    thumb_input,
                    "-O",
                    "thumb.jpg"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            if (
                result.returncode == 0
                and os.path.exists("thumb.jpg")
            ):
                thumb = "thumb.jpg"

        except Exception:
            logger.exception(
                "Thumbnail download failed"
            )

    # -----------------------------------------------------
    # COUNT
    # -----------------------------------------------------

    count = arg

    # =====================================================
    # PROCESS LINKS
    # =====================================================

    for i in range(
        arg - 1,
        len(links)
    ):

        url = None
        filename = None
        prog = None

        try:

            title_part = links[i][0].strip()
            url_part = links[i][1].strip()

            if not url_part:
                continue

            url = "https://" + url_part

            url = (
                url
                .replace(
                    "file/d/",
                    "uc?export=download&id="
                )
                .replace(
                    "www.youtube-nocookie.com/embed",
                    "youtu.be"
                )
                .replace(
                    "?modestbranding=1",
                    ""
                )
                .replace(
                    "/view?usp=sharing",
                    ""
                )
            )

            # ------------------------------------------------
            # NAME
            # ------------------------------------------------

            name1 = safe_filename(
                title_part
            )

            name = (
                f"{str(count).zfill(3)}) "
                f"{name1[:60]} "
                f"{MY_NAME}"
            )

            output_filename = (
                f"{name}.mp4"
            )

            # ------------------------------------------------
            # VISIONIAS
            # ------------------------------------------------

            if "visionias" in url.lower():

                url = await resolve_visionias(
                    url
                )

            # ------------------------------------------------
            # CLASSPLUS CONTENT ID
            # ------------------------------------------------

            if (
                "contentId=" in url
                or "contentHashIdl=" in url
            ):

                content_id = extract_content_id(
                    url
                )

                if not content_id:
                    raise RuntimeError(
                        "ClassPlus content ID not found."
                    )

                signed_url = get_jw_signed_url(
                    content_id,
                    access_token
                )

                if not signed_url:
                    raise RuntimeError(
                        "ClassPlus signed URL not found."
                    )

                url = signed_url

            # ------------------------------------------------
            # NORMAL DOWNLOAD FORMAT
            # ------------------------------------------------

            if "youtu" in url.lower():

                ytf = (
                    f"b[height<={raw_text2}]"
                    "[ext=mp4]/"
                    f"bv[height<={raw_text2}]"
                    "[ext=mp4]+ba[ext=m4a]/"
                    "b[ext=mp4]"
                )

            else:

                ytf = (
                    f"b[height<={raw_text2}]/"
                    f"bv[height<={raw_text2}]+ba/"
                    "b/bv+ba"
                )

            # ------------------------------------------------
            # CAPTIONS
            # ------------------------------------------------

            cc = (
                f"**🏷️ Iɴᴅᴇx ID: "
                f"{str(count).zfill(3)}\n\n"
                f"🎞️ Tɪᴛʟᴇ: {name1} {res}.mkv\n\n"
                f"📚 𝗕ᴀᴛᴄʜ: {b_name}\n\n"
                f"📥 Uᴘʟᴏᴀᴅ Bʏ: {CR}\n\n"
                f"<pre><code>"
                f"━━━━━✦𝗭𝗫✦━━━━━"
                f"</code></pre>**"
            )

            cc1 = (
                f"**🏷️ Iɴᴅᴇx ID: "
                f"{str(count).zfill(3)}\n\n"
                f"📑 Tɪᴛʟᴇ: {name1}.pdf\n\n"
                f"📚 𝗕ᴀᴛᴄʜ: {b_name}\n\n"
                f"📥 Uᴘʟᴏᴀᴅ Bʏ: {CR}\n\n"
                f"<pre><code>"
                f"━━━━━✦𝗭𝗫✦━━━━━"
                f"</code></pre>**"
            )

            # =================================================
            # GOOGLE DRIVE
            # =================================================

            if "drive" in url.lower():

                prog = await m.reply_text(
                    f"📥 Downloading...\n\n"
                    f"`{name}`"
                )

                downloaded = await helper.download(
                    url,
                    name
                )

                await client.send_document(
                    chat_id=m.chat.id,
                    document=downloaded,
                    caption=cc1
                )

                if os.path.exists(downloaded):
                    os.remove(downloaded)

                await prog.delete(True)

            # =================================================
            # PDF
            # =================================================

            elif ".pdf" in url.lower():

                prog = await m.reply_text(
                    f"📑 Downloading PDF...\n\n"
                    f"`{name1}`"
                )

                pdf_file = await download_pdf(
                    url,
                    name
                )

                await client.send_document(
                    chat_id=m.chat.id,
                    document=pdf_file,
                    caption=cc1
                )

                if os.path.exists(pdf_file):
                    os.remove(pdf_file)

                await prog.delete(True)

            # =================================================
            # CLASSPLUS CDN
            # =================================================

            elif (
                "akamai-cdn.classplusapp.com"
                in url.lower()
            ):

                prog = await m.reply_text(
                    "📥 Downloading ClassPlus video...\n\n"
                    f"`{name}`"
                )

                res_file = await asyncio.to_thread(
                    new_classplus_cdn,
                    url,
                    raw_text2,
                    output_filename
                )

                filename = apply_watermark(
                    res_file,
                    WM
                )

                await helper.send_vid(
                    client,
                    m,
                    cc,
                    filename,
                    thumb,
                    name,
                    prog
                )

                if (
                    os.path.exists(filename)
                    and filename != thumb
                ):
                    try:
                        os.remove(filename)
                    except OSError:
                        pass

                await prog.delete(True)

            # =================================================
            # NORMAL AUTHORIZED MEDIA
            # =================================================

            else:

                prog = await m.reply_text(
                    f"🚀 Downloading...\n\n"
                    f"📄 `{name}`\n"
                    f"⌨ Quality: `{raw_text2}`"
                )

                # Use helper if available in your core.py.
                # Otherwise fallback to yt-dlp directly.
                try:

                    res_file = await helper.download_video(
                        url,
                        (
                            f'yt-dlp -f '
                            f'"{ytf}" '
                            f'"{url}" '
                            f'-o "{name}.mp4"'
                        ),
                        name
                    )

                except Exception:

                    logger.exception(
                        "helper.download_video failed"
                    )

                    res_file = await asyncio.to_thread(
                        download_with_ytdlp,
                        url,
                        output_filename,
                        raw_text2
                    )

                filename = apply_watermark(
                    res_file,
                    WM
                )

                await helper.send_vid(
                    client,
                    m,
                    cc,
                    filename,
                    thumb,
                    name,
                    prog
                )

                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except OSError:
                        pass

                await prog.delete(True)

            count += 1

            # Don't block async event loop.
            await asyncio.sleep(1)

        # =====================================================
        # FLOOD WAIT
        # =====================================================

        except FloodWait as e:

            logger.warning(
                "FloodWait: %s seconds",
                e.value
            )

            await m.reply_text(
                f"⏳ FloodWait: "
                f"{e.value} seconds"
            )

            await asyncio.sleep(
                e.value
            )

            continue

        # =====================================================
        # DOWNLOAD ERROR
        # =====================================================

        except Exception as e:

            logger.exception(
                "Download failed for %s",
                name if "name" in locals() else "unknown"
            )

            if prog:

                try:
                    await prog.delete(True)
                except Exception:
                    pass

            error_text = str(e)

            if len(error_text) > 1500:
                error_text = error_text[-1500:]

            await m.reply_text(
                "⌘ **Downloading Interrupted**\n\n"
                f"⌘ **Name:** `{name if 'name' in locals() else 'Unknown'}`\n"
                f"⌘ **Error:**\n"
                f"`{error_text}`"
            )

            continue

    # =========================================================
    # CLEAN THUMB
    # =========================================================

    if (
        thumb != "no"
        and os.path.exists(thumb)
    ):
        try:
            os.remove(thumb)
        except OSError:
            pass

    await m.reply_text(
        "𝐄𝐕𝐄𝐑𝐘𝐓𝐇𝐈𝐍𝐆 𝐈𝐒 𝐃𝐎𝐍𝐄 ☑️"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    print("Starting bot...")
    bot.run()
