# Build stage
FROM python:3.10-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
COPY . .

# Make sure scripts in .local are usable:
ENV PATH=/root/.local/bin:$PATH

CMD ["python", "main.py"]
