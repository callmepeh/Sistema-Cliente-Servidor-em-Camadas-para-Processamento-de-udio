# 🎧 Sistema Cliente/Servidor em Camadas para Processamento de Áudio

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PySide6](https://img.shields.io/badge/PySide6-6.10-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-8.x-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

> **Atividade 3** — Implementação de um sistema cliente/servidor em três camadas capaz de enviar, processar e armazenar arquivos de áudio de forma organizada.

---

## 📸 Demonstração Visual

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI OS PRINTS DA INTERFACE DO CLIENTE
     Sugestão: salve as imagens em docs/prints/ e referencie abaixo
════════════════════════════════════════════════════════════ -->

| Print | Descrição |
|:-----:|-----------|
| ![Tela principal do cliente](docs/prints/cliente-tela-principal.png) | Tela principal do cliente PySide6 com upload, player e histórico |
| ![Envio de arquivo](docs/prints/cliente-upload.png) | Seleção de arquivo e escolha do processamento |
| ![Resultado do processamento](docs/prints/cliente-processado.png) | Áudio processado com sucesso |

<!-- Adicione mais linhas conforme necessário:
| ![Descrição](docs/prints/nome-arquivo.png) | O que o print mostra |
-->

---

## 🎬 Vídeo Demonstrativo (opcional)

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI O VÍDEO DEMONSTRATIVO
     Dica: hospede no YouTube e substitua o link abaixo,
     ou salve o vídeo em docs/videos/ e referencie.
════════════════════════════════════════════════════════════ -->

[![Vídeo demonstrativo](docs/videos/thumbnail.png)](https://youtube.com/link-do-video)

> **Clique na imagem para assistir à demonstração completa do sistema.**

---

## 📋 Descrição do Projeto

Este projeto implementa um **sistema distribuído em três camadas** para processamento de áudio:

1. **Cliente (GUI com PySide6)** — aplicativo desktop que seleciona arquivos de áudio, envia via HTTP para o servidor, reproduz os áudios original/processado e exibe o histórico.
2. **Servidor (FastAPI + FFmpeg)** — API REST que recebe os áudios, aplica processamentos (normalização, mono, velocidade, bitrate, conversão), organiza em disco, registra metadados e serve uma interface web.
3. **Banco de Dados (PostgreSQL)** — armazena os metadados de todos os áudios processados em uma tabela `audios`.

### Funcionalidades do Cliente

- ✅ Selecionar arquivo de áudio do computador
- ✅ Enviar via HTTP indicando o processamento desejado
- ✅ Reproduzir áudio original e processado (player com waveform)
- ✅ Exibir histórico de arquivos enviados e processados
- ✅ Exibir informações do áudio: duração, formato, tamanho

### Funcionalidades do Servidor

- ✅ Receber arquivos de áudio via upload HTTP
- ✅ Aplicar operações de processamento via FFmpeg
- ✅ Armazenar arquivos em pastas organizadas por data + UUID
- ✅ Registrar metadados no PostgreSQL
- ✅ Interface web para listar e reproduzir os áudios no navegador
- ✅ Geração automática de waveform (imagem da forma de onda)
- ✅ meta.json com checksums e parâmetros de processamento
- ✅ Diretório trash/ para exclusão temporária

### Funcionalidades do Banco de Dados

- ✅ Tabela `audios` com todos os metadados
- ✅ UUID como chave primária
- ✅ Índices por data e tipo de processamento

---

## 🏗️ Arquitetura

```
┌─────────────────────┐         HTTP (multipart)        ┌──────────────────────────┐
│   CLIENTE (GUI)     │ ─────────────────────────────►  │      SERVIDOR            │
│   PySide6           │                                 │      FastAPI             │
│                     │  ◄─────────────────────────     │                          │
│  • Seleção arquivo  │      JSON + Streaming média     │  • POST /api/audios      │
│  • Player áudio     │                                 │  • GET  /api/audios      │
│  • Histórico        │                                 │  • GET  /api/media/*     │
│  • Info do áudio    │                                 │  • DELETE /api/audios/id │
└─────────────────────┘                                 │  • Interface web         │
                                                        └────────┬────────┬────────┘
                                                                 │        │
                                                    FFmpeg ──────┘        └────── SQLAlchemy
                                                 (processamento +                │
                                                  waveform)                      ▼
                                                                        ┌──────────────────┐
                                                                        │   POSTGRESQL     │
                                                                        │   (metadados)    │
                                                                        └──────────────────┘
```

### Fluxo de Funcionamento

```
 Cliente                    Servidor                     FFmpeg            PostgreSQL
    │                          │                           │                  │
    │  1. Seleciona arquivo    │                           │                  │
    │  2. Escolhe processam.   │                           │                  │
    │                          │                           │                  │
    │──── POST /api/audios ───►│                           │                  │
    │    (multipart/form-data) │                           │                  │
    │                          │  3. Gera UUID             │                  │
    │                          │  4. Salva audio.{ext}     │                  │
    │                          │───── probe + process ────►│                  │
    │                          │◄───── arquivo pronto ─────│                  │
    │                          │  5. Gera waveform.png     │                  │
    │                          │  6. Grava meta.json       │                  │
    │                          │────── INSERT audios ─────────────────────────►│
    │◄─── 201 + metadados ─────│                           │                  │
    │                          │                           │                  │
    │──── GET /api/audios ────►│ (histórico)               │                  │
    │──── GET .../original ───►│ (streaming de áudio)      │                  │
    │──── GET .../processed ──►│ (streaming de áudio)      │                  │
```

### Estrutura de Armazenamento no Servidor

```
server/storage/
└── 2026/                          ← ano
    └── 09/                        ← mês
        └── 16/                    ← dia
            └── 3fa85f64-5717-4562-b3fc-2c963f66afa6/   ← UUID do áudio
                ├── audio.wav              ← arquivo original (sempre audio.{ext})
                ├── audio_processed.mp3    ← arquivo processado
                ├── meta.json              ← checksums, parâmetros, tamanhos
                └── waveform.png           ← forma de onda gerada pelo FFmpeg
server/storage/trash/              ← arquivos marcados para exclusão
```

### Estrutura do Repositório

```
.
├── client/                  # Cliente gráfico (PySide6)
│   ├── main.py              # Janela principal
│   ├── api_client.py        # Cliente HTTP (httpx)
│   ├── audio_player.py      # Player com waveform
│   ├── env_utils.py         # Leitor de .env
│   └── requirements.txt
├── server/                  # Servidor (FastAPI)
│   ├── app/
│   │   ├── main.py          # Entry point do FastAPI
│   │   ├── routers.py       # Rotas da API
│   │   ├── service.py       # Orquestração do fluxo
│   │   ├── processing.py    # Tipos de processamento FFmpeg
│   │   ├── ffmpeg_utils.py  # Probe, waveform, checksum
│   │   ├── storage.py       # Pastas data/UUID, meta.json, trash
│   │   ├── models.py        # Modelo SQLAlchemy (tabela audios)
│   │   ├── database.py      # Conexão PostgreSQL
│   │   ├── config.py        # Settings (.env)
│   │   ├── schemas.py       # Schemas Pydantic
│   │   └── web/
│   │       └── index.html   # Interface web do servidor
│   ├── tests/               # Testes automatizados (pytest)
│   └── requirements.txt
├── database/
│   └── init.sql             # DDL da tabela audios
├── docs/
│   ├── prints/              # 📸 Adicione aqui os prints
│   └── videos/              # 🎬 Adicione aqui os vídeos
├── docker-compose.yml       # PostgreSQL via Docker
└── README.md
```

---

## 🛠️ Tecnologias

| Camada | Tecnologia | Versão | Função |
|--------|-----------|--------|--------|
| Cliente | Python | 3.11+ | Linguagem |
| Cliente | PySide6 | 6.10 | Interface gráfica (Qt) |
| Cliente | httpx | 0.28 | Comunicação HTTP |
| Servidor | FastAPI | 0.121 | API REST |
| Servidor | uvicorn | 0.41 | Servidor ASGI |
| Servidor | FFmpeg | 6.x+ | Processamento de áudio |
| Banco | PostgreSQL | 17 | Armazenamento de metadados |
| Banco | SQLAlchemy | 2.0 | ORM |
| Banco | psycopg 3 | 3.2 | Driver PostgreSQL |

---

## 📦 Instalação

### Pré-requisitos

- **Python 3.11+**
- **FFmpeg** instalado e no PATH ([download](https://ffmpeg.org/download.html))
- **Docker** (para o PostgreSQL) — ou um PostgreSQL 14+ próprio
- Dois computadores na mesma rede (para a demonstração cliente/servidor) — ou uma única máquina

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU-USUARIO/audio-client-server.git
cd audio-client-server
```

### 2. Criar ambiente virtual (cliente e servidor)

```bash
# Servidor
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
pip install -r server/requirements.txt

# Cliente (pode ser na mesma venv ou em outra máquina)
pip install -r client/requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
# Servidor
cp server/.env.example server/.env

# Cliente (aponte para o IP do servidor)
cp client/.env.example client/.env
```

> Em duas máquinas distintas, edite `client/.env` com o IP do computador servidor,
> ex.: `BASE_URL=http://192.168.0.42:8000`. No servidor, mantenha `HOST=0.0.0.0`.

---

## 🗄️ Configuração do Banco de Dados

### Opção A — Docker (recomendada)

```bash
docker compose up -d
```

Isso sobe um PostgreSQL 17 com usuário `audio`, senha `audio123` e banco `audiodb`,
executando automaticamente `database/init.sql`.

Verifique:

```bash
docker compose ps
docker compose logs db | tail -5
```

### Opção B — PostgreSQL local

1. Crie o banco e o usuário:

```sql
CREATE USER audio WITH PASSWORD 'audio123';
CREATE DATABASE audiodb OWNER audio;
```

2. Execute o script de criação:

```bash
psql -U audio -d audiodb -f database/init.sql
```

3. Ajuste `DATABASE_URL` em `server/.env` se necessário.

> O servidor também cria as tabelas automaticamente ao iniciar
> (`Base.metadata.create_all`), caso o usuário tenha permissão.

### Verificar o banco

```bash
docker exec -it audio_db psql -U audio -d audiodb -c "\d audios"
```

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI UM PRINT DA TABELA NO BANCO
     Ex.: saída do \d audios ou de um SELECT * FROM audios;
════════════════════════════════════════════════════════════ -->

![Metadados no PostgreSQL](docs/prints/banco-tabela-audios.png)

---

## ▶️ Execução do Servidor

```bash
# Ative a venv
source .venv/bin/activate

uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Ou:

```bash
python -m server.app.main
```

| URL | Descrição |
|-----|-----------|
| http://localhost:8000/ | Interface web (redireciona para a lista de áudios) |
| http://localhost:8000/api/docs | Documentação interativa (Swagger UI) |
| http://localhost:8000/api/health | Health check (servidor + banco + FFmpeg) |

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI PRINTS DO SERVIDOR
════════════════════════════════════════════════════════════ -->

| Print | Descrição |
|:-----:|-----------|
| ![Swagger](docs/prints/servidor-swagger.png) | Documentação interativa da API (Swagger) |
| ![Interface web](docs/prints/servidor-web.png) | Interface web com os áudios armazenados |
| ![Health](docs/prints/servidor-health.png) | Health check com status do banco e FFmpeg |

---

## 🖥️ Execução do Cliente

```bash
# Ative a venv
source .venv/bin/activate

# Na máquina cliente
python -m client.main
# ou
python client/main.py
```

Na primeira execução, o cliente conecta automaticamente à URL definida em
`client/.env` (`BASE_URL`). Use o menu **Servidor → Conectar a outro servidor...**
para trocar em tempo de execução.

### Passo a passo da demonstração

1. **Selecionar um arquivo de áudio** — botão *"Procurar..."*
2. **Escolher o processamento** — ex.: *"Normalização de volume"*
3. **Enviar para o servidor** — botão *"Enviar para o servidor"* (com barra de progresso)
4. **Reproduzir o áudio original** — botão *"Reproduzir original"*
5. **Reproduzir o áudio processado** — botão *"Reproduzir processado"*
6. **Consultar o histórico** — tabela à direita (atualiza após cada envio)
7. **Consultar o banco** — `SELECT * FROM audios;` no PostgreSQL
8. **Ver organização dos arquivos** — `tree server/storage`
9. **Interface web do servidor** — acesse `http://IP-DO-SERVIDOR:8000/`

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI PRINTS DO FLUXO DE DEMONSTRAÇÃO
════════════════════════════════════════════════════════════ -->

| Print | Descrição |
|:-----:|-----------|
| ![Sequência 1](docs/prints/demo-1-selecao.png) | Arquivo selecionado com informações do áudio |
| ![Sequência 2](docs/prints/demo-2-envio.png) | Upload em andamento com barra de progresso |
| ![Sequência 3](docs/prints/demo-3-historico.png) | Histórico com o novo áudio processado |
| ![Sequência 4](docs/prints/demo-4-banco.png) | Registro no banco (SELECT no PostgreSQL) |
| ![Sequência 5](docs/prints/demo-5-arvore.png) | Organização de arquivos no servidor (tree) |

---

## 🎛️ Exemplos de Processamento Disponíveis

| Chave | Nome | Parâmetros (JSON) | Filtro FFmpeg |
|-------|------|--------------------|---------------|
| `normalize` | Normalização de volume | `{"target_i": -16.0, "target_tp": -1.5}` | `loudnorm` (EBU R128) |
| `mono` | Conversão para mono | `{}` | `-ac 1` |
| `speed` | Alteração de velocidade | `{"factor": 1.5, "preserving_pitch": true}` | `atempo` |
| `bitrate` | Redução da taxa de bits | `{"bitrate": "64k"}` | `-b:a 64k` |
| `convert` | Conversão de formato | `{"target_format": "mp3", "bitrate": "192k"}` | re-encode |

### Exemplos via curl

```bash
# Normalizar um WAV
curl -X POST http://localhost:8000/api/audios \
  -F "file=@musica.wav" \
  -F "processing_type=normalize"

# Alterar velocidade para 1.5x
curl -X POST http://localhost:8000/api/audios \
  -F "file=@musica.mp3" \
  -F "processing_type=speed" \
  -F 'processing_params={"factor": 1.5}'

# Converter para mono
curl -X POST http://localhost:8000/api/audios \
  -F "file=@musica.flac" \
  -F "processing_type=mono"

# Reduzir bitrate para 64k
curl -X POST http://localhost:8000/api/audios \
  -F "file=@musica.wav" \
  -F "processing_type=bitrate" \
  -F 'processing_params={"bitrate": "64k"}'

# Converter WAV → MP3 192k
curl -X POST http://localhost:8000/api/audios \
  -F "file=@musica.wav" \
  -F "processing_type=convert" \
  -F 'processing_params={"target_format": "mp3", "bitrate": "192k"}'

# Listar histórico
curl http://localhost:8000/api/audios

# Excluir (move para trash/)
curl -X DELETE http://localhost:8000/api/audios/<UUID>
```

---

## 📡 Referência da API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/health` | Status do servidor, banco e FFmpeg |
| `GET` | `/api/processing-types` | Tipos de processamento disponíveis |
| `GET` | `/api/supported-formats` | Extensões aceitas no upload |
| `POST` | `/api/audios` | Upload + processamento (multipart) |
| `GET` | `/api/audios` | Histórico paginado |
| `GET` | `/api/audios/{id}` | Detalhes de um áudio |
| `GET` | `/api/audios/{id}/original` | Streaming/download do original |
| `GET` | `/api/audios/{id}/processed` | Streaming/download do processado |
| `GET` | `/api/audios/{id}/waveform` | Imagem PNG da forma de onda |
| `GET` | `/api/audios/{id}/meta` | Conteúdo do meta.json |
| `DELETE` | `/api/audios/{id}` | Move para trash/ e remove do banco |
| `POST` | `/api/trash/purge` | Remove itens antigos da trash/ |

### Exemplo de resposta do upload

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "original_name": "musica.wav",
  "original_ext": "wav",
  "mime_type": "audio/wav",
  "size_bytes": 352844,
  "duration_sec": 2.0,
  "sample_rate": 44100,
  "channels": 2,
  "bitrate": 1411000,
  "processing_type": "normalize",
  "processing_params": {},
  "created_at": "2026-09-16T14:32:01.123456+00:00",
  "path_original": "server/storage/2026/09/16/3fa85f64.../audio.wav",
  "path_processed": "server/storage/2026/09/16/3fa85f64.../audio_processed.wav",
  "original_url": "/api/audios/3fa85f64.../original",
  "processed_url": "/api/audios/3fa85f64.../processed",
  "waveform_url": "/api/audios/3fa85f64.../waveform"
}
```

### Tabela `audios` (PostgreSQL)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID (PK) | Identificador único do áudio |
| `original_name` | VARCHAR(255) | Nome original do arquivo |
| `original_ext` | VARCHAR(10) | Extensão original |
| `mime_type` | VARCHAR(100) | MIME type |
| `size_bytes` | BIGINT | Tamanho do original |
| `duration_sec` | NUMERIC(10,3) | Duração em segundos |
| `sample_rate` | INTEGER | Taxa de amostragem (Hz) |
| `channels` | INTEGER | Número de canais |
| `bitrate` | INTEGER | Taxa de bits (bps) |
| `processing_type` | VARCHAR(50) | Tipo de processamento aplicado |
| `processing_params` | JSONB | Parâmetros usados |
| `created_at` | TIMESTAMPTZ | Data/hora do envio |
| `path_original` | TEXT | Caminho do original |
| `path_processed` | TEXT | Caminho do processado |

---

## 🧪 Testes

Os testes usam **SQLite em memória** (não exigem PostgreSQL rodando) e geram
áudios sintéticos com FFmpeg.

```bash
# Instale o pytest (se ainda não tiver)
pip install pytest httpx

# Execute os testes do servidor
cd server
python -m pytest tests/ -v
```

### Cobertura dos testes

- ✅ Health check (servidor, banco, FFmpeg)
- ✅ Listagem de tipos de processamento e formatos suportados
- ✅ Upload com **todos os 5 processamentos** (gera áudio real com FFmpeg)
- ✅ Validações: processamento inválido, extensão não suportada, arquivo vazio
- ✅ Histórico, busca por ID, erros 400/404
- ✅ Download de original, processado, waveform e meta.json
- ✅ Exclusão com verificação do diretório trash/

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI UM PRINT DA SAÍDA DOS TESTES
     Ex.: python -m pytest tests/ -v
════════════════════════════════════════════════════════════ -->

![Testes passando](docs/prints/testes-pytest.png)

---

## 📁 Organização dos Arquivos (Exemplo Real)

Após alguns envios, a estrutura no servidor fica assim:

```
server/storage/
├── 2026/
│   └── 09/
│       └── 16/
│           ├── 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d/
│           │   ├── audio.wav
│           │   ├── audio_processed.wav
│           │   ├── meta.json
│           │   └── waveform.png
│           └── 9f8e7d6c-5b4a-3f2e-1d0c-9b8a7f6e5d4c/
│               ├── audio.mp3
│               ├── audio_processed.mp3
│               ├── meta.json
│               └── waveform.png
└── trash/                        ← exclusões temporárias
    └── ...
```

**Exemplo de `meta.json`:**

```json
{
  "uuid": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "original_name": "musica.wav",
  "original_ext": "wav",
  "processed_ext": "wav",
  "mime_type": "audio/wav",
  "size_bytes_original": 352844,
  "size_bytes_processed": 352844,
  "checksum_original_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
  "checksum_processed_sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456...",
  "duration_sec": 2.0,
  "sample_rate": 44100,
  "channels": 2,
  "bitrate": 1411000,
  "processing_type": "normalize",
  "processing_params": {},
  "created_at": "2026-09-16T14:32:01.123456"
}
```

<!-- ═══════════════════════════════════════════════════════════
     👉 ADICIONE AQUI PRINTS DA ORGANIZAÇÃO REAL DOS ARQUIVOS
     Ex.: saída do comando: tree server/storage
════════════════════════════════════════════════════════════ -->

| Print | Descrição |
|:-----:|-----------|
| ![Árvore de arquivos](docs/prints/storage-tree.png) | `tree server/storage` mostrando data/UUID |
| ![meta.json](docs/prints/storage-meta-json.png) | Conteúdo de um meta.json real |
| ![Waveform](docs/prints/storage-waveform.png) | Exemplo de waveform.png gerada |

---

## 🧰 Solução de Problemas

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `ffmpeg não encontrado` | FFmpeg fora do PATH | Instale o FFmpeg ou adicione ao PATH |
| `connection refused` no cliente | Servidor não está rodando / IP errado | Verifique `BASE_URL` no `client/.env` e se o uvicorn está no ar |
| `database: erro` no `/api/health` | PostgreSQL inacessível | Verifique `docker compose ps` e `DATABASE_URL` no `server/.env` |
| Cliente não conecta em outra máquina | Firewall bloqueando a porta 8000 | Libere a porta no firewall do servidor |
| Player não reproduz | Codec ausente no Qt | Use WAV/MP3 para a demonstração; demais formatos são convertidos no servidor |

---

## 📌 Roteiro de Demonstração (para apresentação)

1. `docker compose up -d` — subir o banco
2. `uvicorn server.app.main:app --reload` — subir o servidor
3. Abrir `http://localhost:8000/api/docs` — mostrar Swagger
4. `python -m client.main` — abrir o cliente
5. Selecionar um WAV → Normalização → Enviar
6. Reproduzir **original** e **processado** no player
7. Mostrar o **histórico** no cliente
8. `docker exec -it audio_db psql -U audio -d audiodb -c "SELECT id, original_name, processing_type, duration_sec, created_at FROM audios;"` — metadados no banco
9. `tree server/storage` — organização por data/UUID
10. Abrir um `meta.json` — checksums e parâmetros
11. Interface web `http://localhost:8000/` — listar e reproduzir no navegador
12. (Bônus) Excluir um áudio e mostrar a pasta `trash/`

---

## 👥 Autores

| Nome | Responsabilidade |
|------|------------------|
| *Seu Nome Aqui* | Cliente (PySide6), Servidor (FastAPI), Banco, Testes e Documentação |

<!-- 👉 Edite a tabela acima com os membros do grupo e suas partes -->

---

## 📄 Licença

Este projeto é acadêmico e foi desenvolvido para fins educacionais — disciplina de Sistemas Distribuídos / Redes de Computadores.

<!-- 👉 Ajuste a disciplina/nome da matéria conforme necessário -->
