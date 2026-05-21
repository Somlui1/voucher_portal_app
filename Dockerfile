# Base image using official Python slim image for production efficiency
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
# - chromium: Required for converting HTML to PDF via headless Chromium
# - fonts-thai-tlwg: Required to render Thai fonts correctly in PDF output
# - tini: To handle PID 1 process signals and clean up zombie Chrome processes
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-thai-tlwg \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Enable OpenSSL legacy provider (required for NTLM MD4 authentication)
RUN sed -i '/\[provider_sect\]/a legacy = legacy_sect' /etc/ssl/openssl.cnf && \
    echo -e "\n[legacy_sect]\nactivate = 1" >> /etc/ssl/openssl.cnf

# Copy uv binary from official astral-sh uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python requirements using uv
COPY requirements.txt /app/
RUN uv pip install --system --no-cache -r requirements.txt

# Create a non-privileged user to run the application for improved security
RUN useradd -u 10001 -m appuser \
    && chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose port
EXPOSE 8000

# Use tini as entrypoint to manage zombie processes cleanly
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the Uvicorn server via python startup script
CMD ["python", "app/server.py"]
