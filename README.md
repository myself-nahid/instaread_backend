# InstaRead Backend

A FastAPI-based backend for a book scanning, library, and payment management app.

## 🚀 Features

- User authentication with JWT (register/login)
- Profile management (profile picture upload via Cloudinary)
- Book scanning and OCR-style processing through AI service
- Payment integration (Stripe) for subscriptions or book-related purchases
- Admin endpoints for user and scan management
- DB-backed persistence with SQLAlchemy + Alembic migrations
- Clean folder structure: API, models, schemas, services, CRUD

## 📁 Project Structure

- `app/main.py`: FastAPI application factory and startup config
- `app/api/v1/endpoints`: REST endpoints (auth, users, scan, books, payment, settings, admin)
- `app/models`: SQLAlchemy ORM models (User, BookScan, Transaction, Policy)
- `app/schemas`: Pydantic request/response schemas
- `app/crud`: CRUD utility functions
- `app/services`: external integrations (AI, payments, etc.)
- `app/db`: database initialization and session handling
- `app/core`: config and security (password hashing, settings)
- `alembic`: DB migration management

## ⚙️ Requirements

- Python 3.10+
- PostgreSQL (or SQLite for dev) supported via SQLAlchemy connection URL
- Redis (optional in current tree? check env usage)

## 🛠️ Setup

1. Clone and enter:
   ```bash
   git clone <repo-url>
   cd instaread_backend
   ```
2. Create and activate virtual env:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   source .venv/bin/activate      # macOS/Linux
   ```
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `.env` (see below)
5. Apply migrations:
   ```bash
   alembic upgrade head
   ```
6. Start app:
   ```bash
   uvicorn app.main:app --reload
   ```

## 🧩 Environment Variables

Create a `.env` file in project root with:

```ini
DATABASE_URL=postgresql://user:password@localhost:5432/instaread
SECRET_KEY=your_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CLOUDINARY_URL=cloudinary://key:secret@cloudname
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
AI_API_KEY=your_ai_api_key
```

## 🧪 Running Tests (if added)

```bash
pytest
```

## ✅ API Docs

- Swagger UI: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`

## 🛡️ Security

- Passwords hashed with `bcrypt` via `app/core/security.py`
- JWT tokens via `login` endpoint and `auth` dependencies in `app/api/deps.py`

## 🔄 Database Migrations

- Migration scripts in `alembic/versions`
- To create migration:
  ```bash
  alembic revision --autogenerate -m "describe change"
  alembic upgrade head
  ```

## 🧾 Notes

- This repository is backend-only. Integrate with frontend app via API routes.
- Check `app/services` for business logic and third-party SDK use.