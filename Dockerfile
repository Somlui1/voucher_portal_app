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

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-privileged user to run the application for improved security
RUN useradd -u 10001 -m appuser \
    && chown -R appuser:appuser /app

# Copy application source code
COPY --chown=appuser:appuser app/ /app/app/
COPY --chown=appuser:appuser helper/ /app/helper/

# Switch to the non-root user
USER appuser

# Expose port
EXPOSE 8000

# Use tini as entrypoint to manage zombie processes cleanly
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the Uvicorn server via python startup script
CMD ["python", "app/server.py"]
