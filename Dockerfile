FROM python:3.13.0
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc libffi-dev musl-dev ffmpeg aria2 python3-pip \
    openssl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/

RUN pip install --upgrade pip setuptools wheel -r Installer

ENV COOKIES_FILE_PATH="/modules/youtube_cookies.txt"

CMD gunicorn app:app & python3 modules/main.py
