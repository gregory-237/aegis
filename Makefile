.PHONY: help proto certs up down logs test agent ingest

help:
	@echo "  proto   — сгенерировать python-код из proto/monitor.proto"
	@echo "  certs   — сгенерировать mTLS-сертификаты (CA + server + client)"
	@echo "  up      — поднять весь стек в Docker"
	@echo "  down    — остановить стек"
	@echo "  logs    — хвост логов всех сервисов"
	@echo "  test    — прогнать pytest"
	@echo "  agent   — запустить агента локально (dev)"
	@echo "  ingest  — запустить приёмник локально (dev)"

proto:
	python -m grpc_tools.protoc -I proto \
	  --python_out=proto/gen --grpc_python_out=proto/gen --pyi_out=proto/gen \
	  proto/monitor.proto

certs:
	bash scripts/gen-certs.sh

up:
	docker compose -f deploy/docker-compose.yml up -d --build

down:
	docker compose -f deploy/docker-compose.yml down

logs:
	docker compose -f deploy/docker-compose.yml logs -f --tail=100

test:
	python -m pytest -q

agent:
	python agent/main.py

ingest:
	python server/ingest/server.py
