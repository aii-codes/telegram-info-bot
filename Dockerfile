# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy dependency list and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose no port (Telegram bots don't need it, but kept for flexibility)
EXPOSE 8080

# Set environment variable for Python
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "app.py"]
