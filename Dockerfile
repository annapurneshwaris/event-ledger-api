FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# Use an on-disk SQLite file inside the container by default.
ENV LEDGER_DATABASE_URL=sqlite:///./ledger.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
