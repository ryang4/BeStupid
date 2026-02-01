FROM python:3.12-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    openssh-client \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Set up working directory for bot code
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code and entrypoint
COPY bot.py .
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Create non-root user (Claude CLI refuses --dangerously-skip-permissions as root)
RUN useradd -m -u 501 botuser

# Environment
ENV PYTHONUNBUFFERED=1
ENV PROJECT_ROOT=/project
ENV SKIP_PERMISSIONS=true
ENV GIT_CONFIG_GLOBAL=/home/botuser/.gitconfig

USER botuser
ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "/app/bot.py"]
