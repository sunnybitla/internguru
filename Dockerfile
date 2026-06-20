# Use official lightweight Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000
ENV DATA_DIR=/data

# Create directory for data persistence
RUN mkdir -p /data

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 10000

# Start command (runs on 0.0.0.0 and references $PORT)
CMD uvicorn server:app --host 0.0.0.0 --port 10000
