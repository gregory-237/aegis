# Образ ingest-сервиса (gRPC+mTLS приём). Контекст сборки — корень репозитория.
FROM python:3.12-slim

WORKDIR /app

# Зависимости (grpc-tools нужен для кодогена proto на этапе сборки).
COPY server/ingest/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt grpcio-tools

# Контракт + код сервиса.
COPY proto ./proto
COPY server/ingest ./server/ingest

# Кодоген protobuf в proto/gen (server.py ожидает его в /app/proto/gen).
RUN mkdir -p proto/gen && \
    python -m grpc_tools.protoc -I proto \
      --python_out=proto/gen --grpc_python_out=proto/gen proto/monitor.proto

ENV PYTHONUNBUFFERED=1
EXPOSE 1222

# Сертификаты монтируются в /certs (см. docker-compose).
CMD ["python", "server/ingest/server.py"]
