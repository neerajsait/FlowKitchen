FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if required (e.g., for mysqlclient or other python packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=app.py

# Create static folders if needed by app
RUN mkdir -p static/uploads/tickets

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:create_app()"]
