FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirments.txt /app/
RUN pip install --no-cache-dir -r requirments.txt

# Copy backend code
COPY . /app/

EXPOSE 8000

# Run ASGI dev server via Daphne
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
