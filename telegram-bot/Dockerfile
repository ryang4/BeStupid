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

# Copy bot code
COPY bot.py .

# Configure git to trust the mounted repo directory
RUN git config --global --add safe.directory /project

# Environment
ENV PYTHONUNBUFFERED=1
ENV PROJECT_ROOT=/project
ENV SKIP_PERMISSIONS=true

# Bot runs from /app, operates on /project
CMD ["python", "/app/bot.py"]
