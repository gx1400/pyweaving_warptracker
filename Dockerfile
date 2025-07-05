FROM python:3.11-slim
LABEL org.opencontainers.image.source=https://github.com/gx1400/nicegui-weaving

# Set environment vars to avoid interactive prompts
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create app directory
WORKDIR /app
RUN mkdir -p /app/db
RUN mkdir -p /app/uploads

# Install system dependencies (for nicegui to run properly)
RUN apt-get update && apt-get install -y git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source code
COPY . .

# Expose the port NiceGUI will use
EXPOSE 8080

# Run your NiceGUI app
CMD ["python", "liftplanview.py"]
