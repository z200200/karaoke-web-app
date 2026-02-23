# Dockerfile
FROM python:3.10-slim

# install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# set working directory
WORKDIR /app

# copy requirements
COPY requirements.txt /app/

# install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# copy source code
COPY karaoke_backend.py /app/

# create workspace directory
RUN mkdir -p /app/audio_workspace

# expose port
EXPOSE 8000

# default command
CMD ["uvicorn", "karaoke_backend:app", "--host", "0.0.0.0", "--port", "8000"]
