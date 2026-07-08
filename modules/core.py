import os
import time
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures

from utils import progress_bar

from pyrogram import Client, filters
from pyrogram.types import Message

from pytube import Playlist  #Youtube Playlist Extractor
from yt_dlp import YoutubeDL
import yt_dlp as youtube_dl


def duration(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)

def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka



def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])

                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 

                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info



async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'



def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"

def get_playlist_videos(playlist_url):
    try:
        # Create a Playlist object
        playlist = Playlist(playlist_url)

        # Get the playlist title
        playlist_title = playlist.title

        # Initialize an empty dictionary to store video names and links
        videos = {}

        # Iterate through the videos in the playlist
        for video in playlist.videos:
            try:
                video_title = video.title
                video_url = video.watch_url
                videos[video_title] = video_url
            except Exception as e:
                logging.error(f"Could not retrieve video details: {e}")

        return playlist_title, videos
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None, None

def get_all_videos(channel_url):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True
    }

    all_videos = []
    with YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(channel_url, download=False)

        if 'entries' in result:
            channel_name = result['title']
            all_videos.extend(result['entries'])

            while 'entries' in result and '_next' in result:
                next_page_url = result['_next']
                result = ydl.extract_info(next_page_url, download=False)
                all_videos.extend(result['entries'])

            video_links = {index+1: (video['title'], video['url']) for index, video in enumerate(all_videos)}
            return video_links, channel_name
        else:
            return None, None

def save_to_file(video_links, channel_name):
    # Sanitize the channel name to be a valid filename
    sanitized_channel_name = re.sub(r'[^\w\s-]', '', channel_name).strip().replace(' ', '_')
    filename = f"{sanitized_channel_name}.txt"    
    with open(filename, 'w', encoding='utf-8') as file:
        for number, (title, url) in video_links.items():
            # Ensure the URL is formatted correctly
            if url.startswith("https://"):
                formatted_url = url
            elif "shorts" in url:
                formatted_url = f"https://www.youtube.com{url}"
            else:
                formatted_url = f"https://www.youtube.com/watch?v={url}"
            file.write(f"{number}. {title}: {formatted_url}\n")
    return filename

async def download_appxpdf(url, name, enc_key=""):
    """
    Bhai yeh function background thread me silent download aur decryption handle karta hai.
    Success hone par final file ka path return karega, fail hone par None.
    """
    import os
    import hashlib
    import shutil
    import subprocess
    import urllib.request
    import asyncio

    pid = os.getpid()
    temp_enc_file = f"temp_enc_{pid}.pdf"
    final_pdf_file = f"{name}.pdf"

    # Silent Background Download Engine
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36")
    req.add_header("Referer", "https://appx-play.akamai.net.in/")
    
    try:
        def _download():
            with urllib.request.urlopen(req, timeout=60) as response:
                with open(temp_enc_file, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
                    
        await asyncio.get_event_loop().run_in_executor(None, _download)
    except Exception:
        if os.path.exists(temp_enc_file): os.remove(temp_enc_file)
        return None

    # Silent Decryption Engine (OpenSSL)
    def _decrypt():
        if not os.path.exists(temp_enc_file):
            return False

        # Agar already plain PDF hai
        with open(temp_enc_file, 'rb') as f:
            if f.read(4) == b'%PDF':
                shutil.copy(temp_enc_file, final_pdf_file)
                return True

        with open(temp_enc_file, 'rb') as f:
            file_bytes = f.read()

        if len(file_bytes) < 32:
            return False

        iv_bytes = file_bytes[:16]
        ciphertext_bytes = file_bytes[16:]
        temp_cipher = f"temp_cipher_{pid}.bin"
        temp_plain = f"temp_plain_{pid}.pdf"

        with open(temp_cipher, 'wb') as f:
            f.write(ciphertext_bytes)

        hex_iv = iv_bytes.hex()
        candidates = [
            enc_key.encode('utf-8')[:16].ljust(16, b'\x00'),
            hashlib.md5(enc_key.encode('utf-8')).digest(),
            hashlib.sha256(enc_key.encode('utf-8')).digest()[:16]
        ]

        success = False
        for cand_bytes in candidates:
            hex_key = cand_bytes.hex()
            
            # Method 1: Standard Padded
            cmd = ["openssl", "aes-128-cbc", "-d", "-K", hex_key, "-iv", hex_iv, "-in", temp_cipher, "-out", temp_plain]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(temp_plain):
                with open(temp_plain, 'rb') as f:
                    if f.read(4) == b'%PDF':
                        shutil.move(temp_plain, final_pdf_file)
                        success = True
                        break
                os.remove(temp_plain)

            # Method 2: Zero IV Fallback
            cmd_zero = ["openssl", "aes-128-cbc", "-d", "-K", hex_key, "-iv", "00000000000000000000000000000000", "-in", temp_enc_file, "-out", temp_plain]
            subprocess.run(cmd_zero, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(temp_plain):
                with open(temp_plain, 'rb') as f:
                    if f.read(4) == b'%PDF':
                        shutil.move(temp_plain, final_pdf_file)
                        success = True
                        break
                os.remove(temp_plain)

        if os.path.exists(temp_cipher): os.remove(temp_cipher)
        return success

    decryption_success = await asyncio.get_event_loop().run_in_executor(None, _decrypt)
    
    # Clean temporary raw file
    if os.path.exists(temp_enc_file): 
        os.remove(temp_enc_file)

    if decryption_success and os.path.exists(final_pdf_file):
        return final_pdf_file
    else:
        if os.path.exists(final_pdf_file): os.remove(final_pdf_file)
        return None
        
async def download_secure_pdf(url, name):
    """
    Termux bypass headers ke sath secure PDF download karne ka working function.
    """
    clean_name = f"{name}.pdf"
    print(f"[Secure PDF] Download suru ho raha hai: {clean_name}", flush=True)
    
    cmd = [
        "curl", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
        "-H", "Referer: https://appx-play.akamai.net.in/",
        "-o", clean_name,
        url
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            stdout=asyncio.subprocess.DEVNULL, 
            stderr=asyncio.subprocess.PIPE
        )
        
        _, stderr_data = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(clean_name):
            print(f"[Secure PDF] Download safal raha: {clean_name}", flush=True)
            return clean_name
        else:
            err_msg = stderr_data.decode(errors='ignore').strip() if stderr_data else "Unknown"
            print(f"[Secure PDF] Error: Curl download process fail ho gaya. Log: {err_msg}", flush=True)
            return None
    except Exception as e:
        print(f"[Secure PDF] Exception error: {str(e)}", flush=True)
        return None

# =====================================================================
#  ✅ Appx VIDEO DOWNLOAD (Working version - no duplicates)
# =====================================================================
async def download_secure_video(url, name):
    """
    Normal HLS (.m3u8) video streams ko bypass headers ke sath download aur copy karne ka working function.
    """
    clean_name = f"{name}.mp4" if not name.endswith(".mp4") else name
    print(f"[Secure Video] Stream compile hona suru ho gaya hai: {clean_name}", flush=True)
    
    cmd = [
        "ffmpeg", "-y",
        "-user_agent", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
        "-headers", "Referer: https://appx-play.akamai.net.in/\r\n",
        "-i", url,
        "-c", "copy",
        clean_name
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            stdout=asyncio.subprocess.DEVNULL, 
            stderr=asyncio.subprocess.PIPE
        )
        
        while True:
            line_bytes = await process.stderr.readline()
            if not line_bytes:
                break
            line = line_bytes.decode(errors='ignore').strip()
            if "frame=" in line or "time=" in line or "speed=" in line:
                print(f"[Secure Video Process] {line}", flush=True)
            
        await process.wait()
        
        if process.returncode == 0 and os.path.exists(clean_name):
            print(f"[Secure Video] Conversion complete ho gaya: {clean_name}", flush=True)
            return clean_name
        else:
            print("[Secure Video] Error: FFmpeg run completed with failure.", flush=True)
            return None
    except Exception as e:
        print(f"[Secure Video] Exception error: {str(e)}", flush=True)
        return None


async def download_video(url, cmd, name):
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    global failed_counter
    print(download_cmd)
    logging.info(download_cmd)
    k = subprocess.run(download_cmd, shell=True)

    # Check if the URL is of type 'visionias' or 'penpencilvod'
    if "visionias" in cmd:
        return await download_visionias(url, cmd, name)
    elif "penpencilvod" in cmd:
        return await download_penpencilvod(url, cmd, name)
    else:
        # Default handling for other types of URLs
        return await default_download(url, cmd, name)

async def download_visionias(url, cmd, name):
    global failed_counter
    # Retry logic for 'visionias' URLs
    if failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        return await download_video(url, cmd, name)
    else:
        # Reset failed_counter if the download succeeds
        failed_counter = 0
        return await default_download(url, cmd, name)

async def download_penpencilvod(url, cmd, name):
    global failed_counter
    # Retry logic for 'penpencilvod' URLs
    if failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        return await download_video(url, cmd, name)
    else:
        # Reset failed_counter if the download succeeds
        failed_counter = 0
        return await default_download(url, cmd, name)

async def download_video(url,cmd, name):
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    global failed_counter
    print(download_cmd)
    logging.info(download_cmd)
    k = subprocess.run(download_cmd, shell=True)
    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        await download_video(url, cmd, name)
    failed_counter = 0
    try:
        if os.path.isfile(name):
            return name
        elif os.path.isfile(f"{name}.webm"):
            return f"{name}.webm"
        name = name.split(".")[0]
        if os.path.isfile(f"{name}.mkv"):
            return f"{name}.mkv"
        elif os.path.isfile(f"{name}.mp4"):
            return f"{name}.mp4"
        elif os.path.isfile(f"{name}.mp4.webm"):
            return f"{name}.mp4.webm"

        return name
    except FileNotFoundError as exc:
        return os.path.isfile.splitext[0] + "." + "mp4"


async def send_doc(bot: Client, m: Message,cc,ka,cc1,prog,count,name):
    reply = await m.reply_text(f"Uploading » `{name}`")
    time.sleep(1)
    start_time = time.time()
    await m.reply_document(ka,caption=cc1)
    count+=1
    await reply.delete (True)
    time.sleep(1)
    os.remove(ka)
    time.sleep(3) 


async def send_vid(bot: Client, m: Message,cc,filename,thumb,name,prog):
    subprocess.run(f'ffmpeg -i "{filename}" -ss 00:01:00 -vframes 1 "{filename}.jpg"', shell=True)
    await prog.delete (True)
    reply = await m.reply_text(f"**⥣ Uploading ...** » `{name}`")
    try:
        if thumb == "no":
            thumbnail = f"{filename}.jpg"
        else:
            thumbnail = thumb
    except Exception as e:
        await m.reply_text(str(e))

    dur = int(duration(filename))

    start_time = time.time()

    try:
        await m.reply_video(filename,caption=cc, supports_streaming=True,height=720,width=1280,thumb=thumbnail,duration=dur, progress=progress_bar,progress_args=(reply,start_time))
    except Exception:
        await m.reply_document(filename,caption=cc, progress=progress_bar,progress_args=(reply,start_time))
    os.remove(filename)

    os.remove(f"{filename}.jpg")
    await reply.delete (True)
