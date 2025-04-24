# Use an official Python runtime as a parent image
# Using bookworm (Debian 12) which has recent Chromium versions
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# - wget: sometimes needed for downloading things (though not strictly needed here)
# - chromium: The browser itself
# - chromium-driver: The WebDriver binary compatible with the installed chromium
# - Necessary libraries for headless chrome operation
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wget \
        chromium \
        chromium-driver \
        # Add common libs needed by Chrome/Chromium headless - dependencies should handle most, but these can help
        libglib2.0-0 \
        libnss3 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libfontconfig1 \
        libxss1 \
    # Clean up APT cache to reduce image size
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd --system appgroup && useradd --system --gid appgroup --create-home appuser

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
# Make sure 'scrape_fuel.py' is in the same directory as the Dockerfile
COPY fuel_scraper.py .

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Command to run the application
CMD ["python", "main.py"]