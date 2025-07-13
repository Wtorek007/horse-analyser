FROM python:3.12

WORKDIR /app

COPY scraper/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY scraper/ .

CMD ["python", "main.py"]
