RUN pip install --upgrade pip setuptools wheel
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade pip setuptools wheel

COPY . .

CMD ["python", "app/main.py"]
