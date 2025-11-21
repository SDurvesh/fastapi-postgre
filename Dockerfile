# Use a lightweight official Python image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first (to leverage Docker caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app.py .

# Expose FastAPI port
EXPOSE 8000

# Environment variables for the app (can be overridden in docker-compose)
ENV POSTGRES_HOST=postgres
ENV POSTGRES_DB=appdb
ENV POSTGRES_USER=appuser
ENV POSTGRES_PASSWORD=apppass
ENV POSTGRES_PORT=5432
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

# Start the FastAPI server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


