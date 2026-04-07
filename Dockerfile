FROM python:3.10-slim

WORKDIR /app

# system dependencies (safe minimal)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# upgrade pip tools
RUN pip install --upgrade pip setuptools wheel

# copy project files
COPY requirements.txt .

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# run app (change if needed)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
