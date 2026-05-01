# Use the official lightweight Python 3.12 base image
FROM python:3.12-slim

# Set the working directory inside the container to /app
WORKDIR /app

# Copy requirements.txt from host into the container's /app directory
COPY requirements.txt .

# Install Python dependencies listed in requirements.txt
RUN pip install --root-user-action=ignore -r requirements.txt

# Copy the proto directory (likely generated gRPC code) into the container
COPY proto /app/proto

# Copy the frontend application code into the container
COPY frontend /app/frontend

# Add /app/proto/src to Python's module search path for imports
ENV PYTHONPATH=/app/proto/src

# Default command: run the server script when the container starts
CMD ["python", "frontend/server.py"]
