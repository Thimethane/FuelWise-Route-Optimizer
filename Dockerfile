# Use a stable Python slim image for a smaller footprint
FROM python:3.11-slim

# 1. Environment variables
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE 1
# Ensures console output is exported in real-time
ENV PYTHONUNBUFFERED 1

# 2. Set work directory
WORKDIR /app

# 3. Install system dependencies
# We need build-essential and libpq-dev for PostgreSQL support (psycopg2)
# and curl for health checking the API
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Python dependencies
# We copy requirements.txt first to leverage Docker's layer caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the project files
COPY . /app/

# 6. Expose the Django port
EXPOSE 8000

# 7. Default execution
# Note: We use 0.0.0.0 so the server is accessible from outside the container
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
