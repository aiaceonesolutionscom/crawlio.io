FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pip install alone only installs the playwright Python package — the actual
# browser binary + its OS-level libraries (needed for the Pro-tier contact
# scraper) have to be fetched separately.
RUN playwright install --with-deps chromium

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
