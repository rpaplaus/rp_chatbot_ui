# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for pdfplumber and other potential needs
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the memory directory to ensure it exists
RUN mkdir -p /app/memory

# Make port 7860 available to the world outside this container
EXPOSE 7860

# Define environment variable for Gradio to listen on all interfaces
ENV GRADIO_SERVER_NAME="0.0.0.0"

# Run app.py when the container launches
CMD ["python", "app.py"]
