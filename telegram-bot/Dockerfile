FROM python:3.12-slim

# Install dependencies (no Node.js/npm needed)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    openssh-client \
    cron \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory for bot code
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code and entrypoint
COPY bot.py claude_client.py tools.py restore_cron.py ./
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Create non-root user and ensure home dir is accessible for entrypoint setup
RUN useradd -m -u 501 botuser && \
    chown -R botuser:botuser /home/botuser && \
    chmod 755 /home/botuser

# Environment
ENV PYTHONUNBUFFERED=1
ENV PROJECT_ROOT=/project
ENV GIT_CONFIG_GLOBAL=/home/botuser/.gitconfig

# Entrypoint runs as root to start cron, then drops to botuser
ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "/app/bot.py"]
