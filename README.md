# GenHealth AI — Generational Health Intelligence Platform

A full-stack AI-powered health platform that uses multi-generational family health data to predict, prevent, and personalize healthcare journeys.

## Architecture Overview

```
genhealth-ai/
├── backend/          # FastAPI Python backend
├── frontend/         # Vanilla HTML/CSS/JS frontend
└── docker-compose.yml
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI (Python 3.11) |
| Primary DB | PostgreSQL 16 (SQLAlchemy 2.0 async) |
| Document DB | MongoDB 7 (Motor async driver) |
| Cache / Queue | Redis 7 (sessions, rate limits, Celery broker) |
| Task Queue | Celery 5 (async OCR/ML processing) |
| File Storage | MinIO (dev) / AWS S3 (prod) |
| Auth | JWT (access + refresh) + bcrypt |
| Email | SendGrid |
| Migrations | Alembic |

## Prerequisites

- Python 3.11+
- Docker & Docker Compose v2
- Node.js 18+ (optional, for frontend tooling)
- Git

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/genhealth-ai.git
cd genhealth-ai
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials
```

### 2. Start All Services with Docker

```bash
docker-compose up --build -d
```

This starts:
- `api` on http://localhost:8000
- `worker` (Celery)
- `postgres` on localhost:5432
- `mongodb` on localhost:27017
- `redis` on localhost:6379
- `minio` on http://localhost:9000 (console: 9001)

### 3. Run Database Migrations

```bash
docker-compose exec api alembic upgrade head
```

### 4. Access API Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

### 5. Run the Frontend

```bash
# Serve locally
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

## Development Setup (without Docker)

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env

# Run migrations (requires running PostgreSQL)
alembic upgrade head

# Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker (separate terminal)
celery -A app.celery_app worker --loglevel=info
```

## Running Tests

```bash
cd backend
pytest tests/ -v --asyncio-mode=auto
# With coverage
pytest tests/ -v --cov=app --cov-report=html
```

## API Endpoint Groups

| Router | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/v1/auth` | Registration, login, JWT, OTP |
| Users | `/api/v1/users` | Profile management |
| Family | `/api/v1/family` | Family members, tree, invites |
| Records | `/api/v1/records` | Health record CRUD + timeline |
| Upload | `/api/v1/upload` | File upload, OCR pipeline trigger |
| Risk | `/api/v1/risk` | Risk predictions, watchlist |
| Insights | `/api/v1/insights` | Health score, trends, summary |
| Recommendations | `/api/v1/recommendations` | Personalized action plans |
| Doctor | `/api/v1/doctor` | Doctor-role endpoints |
| Invite | `/api/v1/invite` | Family invite link flow |

## Environment Variables

See `backend/.env.example` for the full list.

## Database Schema

Key tables: `users`, `family_members`, `health_records`, `extracted_entities`, `risk_predictions`, `family_invites`, `doctor_access`

See `backend/alembic/versions/001_initial_schema.py` for the complete DDL.

## Project Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app, CORS, middleware registration
│   ├── config.py        # Pydantic Settings
│   ├── database.py      # Async DB connections
│   ├── celery_app.py    # Celery configuration
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── routers/         # API route handlers
│   ├── services/        # Business logic layer
│   └── middleware/      # Auth, rate limiting
├── ml/
│   ├── ocr/             # OCR pipeline (Part 2)
│   ├── nlp/             # NLP extraction (Part 2)
│   ├── risk_models/     # Risk prediction models (Part 2)
│   └── generational/    # Hereditary pattern analysis (Part 2)
├── tests/               # pytest test suite
├── alembic/             # Database migrations
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Security Notes

- All passwords hashed with bcrypt (cost 12)
- JWTs signed with HS256
- Refresh tokens stored as hashed values in Redis
- File uploads scanned before storage
- Rate limiting: 100 req/min per IP (configurable)
- Doctor access requires explicit patient consent with expiry
- All data transfer via HTTPS in production

## License

MIT
