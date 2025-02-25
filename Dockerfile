FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean

# Installing dependencies 
COPY requirements.txt /app

RUN python3.12 -m pip install -r requirements.txt
ENV PYTHONUNBUFFERED=1

#Install main program
COPY /src /app/src

LABEL org.opencontainers.image.source=https://github.com/SolaceLabs/solace-ai-connector

# Run app.py when the container launches
ENTRYPOINT ["python", "src/main.py"]
