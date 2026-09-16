# Servidor — Sistema de Processamento de Áudio

Servidor FastAPI + FFmpeg + PostgreSQL do sistema cliente/servidor em camadas para processamento de áudio.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r server/requirements.txt
```

## Configuração

```bash
cp server/.env.example server/.env
# Edite server/.env se necessário (DATABASE_URL, portas etc.)
```

## Banco de dados

```bash
docker compose up -d
```

## Execução

```bash
uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API: http://localhost:8000/api/docs (Swagger)
- Interface web: http://localhost:8000/web/index.html
- Health: http://localhost:8000/api/health
