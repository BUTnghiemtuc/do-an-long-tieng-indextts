# Ảnh chạy được cả API lẫn worker GPU.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common git ffmpeg rubberband-cli \
    && add-apt-repository ppa:deadsnakes/ppa && apt-get update \
    && apt-get install -y --no-install-recommends python3.11 python3.11-venv python3.11-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python3.11 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
# Mã suy luận IndexTTS (bao gồm IndexTTS2; đổi sang nhánh/fork có IndexTTS 2.5 khi dùng 2.5)
RUN git clone --depth 1 https://github.com/index-tts/index-tts.git /opt/index-tts \
    && pip install -e /opt/index-tts

WORKDIR /app
COPY pyproject.toml ./
COPY vidub ./vidub
COPY server ./server
COPY data_prep ./data_prep
COPY eval ./eval
COPY configs ./configs
RUN pip install -e ".[gpu,llm,server]"

EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
