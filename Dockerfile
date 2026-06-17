FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Interactive bot: menu + background scraper in one process.
CMD ["python", "-m", "bot.app"]
