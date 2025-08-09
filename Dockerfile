FROM python:3.12

WORKDIR /app

# Install python3.12-venv package as requested
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

COPY scraper/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY scraper/ .

CMD ["python", "main.py"]
