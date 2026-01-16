# FastAPI Web Application - Project Structure

## Directory Structure

```
forecast-webapp/
├── alembic/                          # Database migrations
│   ├── versions/                     # Migration scripts
│   ├── env.py                        # Alembic config
│   └── script.py                     # Alembic runner
│
├── api/                              # API layer
│   ├── __init__.py
│   ├── dependencies.py               # Dependency injection
│   └── routes/                       # API endpoints
│       ├── __init__.py
│       ├── auth.py                   # Authentication endpoints
│       ├── items.py                  # Items & catalog
│       ├── inventory.py              # Inventory status
│       ├── pricing.py                # Pricing & margins
│       ├── sales.py                  # Sales orders
│       ├── purchasing.py             # Purchase orders
│       ├── forecasts.py              # Forecasting
│       ├── analytics.py              # Analytics & reports
│       └── sync.py                   # SAP sync control
│
├── core/                             # Core configuration
│   ├── __init__.py
│   ├── config.py                     # Settings (Pydantic)
│   ├── security.py                   # Auth & security
│   ├── database.py                   # DB connection
│   └── exceptions.py                 # Custom exceptions
│
├── models/                           # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── base.py                       # Base model
│   ├── user.py                       # User model
│   ├── item.py                       # Item master
│   ├── warehouse.py                  # Warehouse
│   ├── vendor.py                     # Vendor
│   ├── inventory.py                  # Inventory & transactions
│   ├── pricing.py                    # Pricing & costs
│   ├── sales_order.py                # Sales orders
│   ├── purchase_order.py             # Purchase orders
│   ├── forecast.py                   # Forecasts & accuracy
│   └── optimization.py               # Stock recommendations
│
├── repositories/                     # Data access layer
│   ├── __init__.py
│   ├── base.py                       # Base repository
│   ├── item_repository.py
│   ├── inventory_repository.py
│   ├── pricing_repository.py
│   ├── sales_repository.py
│   ├── purchase_repository.py
│   └── forecast_repository.py
│
├── services/                         # Business logic
│   ├── __init__.py
│   ├── auth_service.py               # Authentication
│   ├── sap_sync.py                   # SAP B1 sync
│   ├── forecast_service.py           # Forecast generation
│   ├── margin_service.py             # Margin calculations
│   ├── inventory_service.py          # Inventory status
│   └── notification_service.py       # Alerts & notifications
│
├── schemas/                          # Pydantic schemas (API I/O)
│   ├── __init__.py
│   ├── user.py                       # User DTOs
│   ├── item.py                       # Item DTOs
│   ├── inventory.py                  # Inventory DTOs
│   ├── pricing.py                    # Pricing DTOs
│   ├── forecast.py                   # Forecast DTOs
│   └── common.py                     # Common schemas (pagination, etc.)
│
├── tasks/                            # Background tasks (Celery)
│   ├── __init__.py
│   ├── celery_app.py                 # Celery instance
│   ├── forecasting.py                # Forecast generation jobs
│   ├── sync.py                       # SAP sync jobs
│   └── reports.py                    # Report generation
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures
│   ├── test_api/                     # API tests
│   ├── test_services/                # Service tests
│   ├── test_repositories/            # Repository tests
│   └── test_tasks/                   # Background job tests
│
├── scripts/                          # Utility scripts
│   ├── migrate_data.py               # Data migration from TSV
│   ├── init_db.py                    # Initialize database
│   ├── sync_sap.py                   # Manual SAP sync
│   └── generate_forecasts.py         # Manual forecast generation
│
├── frontend/                         # Frontend (if using Vue/React)
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── .env.example                      # Environment variables template
├── .gitignore
├── alembic.ini                       # Alembic config
├── docker-compose.yml                # Local development
├── Dockerfile
├── pyproject.toml                    # Python dependencies
├── requirements.txt
└── main.py                           # FastAPI app entry point
```

---

## Key Files Overview

### `core/config.py`
Configuration management using Pydantic Settings

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "SAP B1 Forecast Analyzer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # SAP B1
    SAP_SERVICE_LAYER_URL: str
    SAP_COMPANY_DB: str
    SAP_USERNAME: str
    SAP_PASSWORD: str

    # Railway
    RAILWAY_PROJECT_ID: str = ""
    RAILWAY_SERVICE_NAME: str = ""

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
```

### `core/database.py`
Async database connection

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### `models/base.py`
Base model with common fields

```python
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### `repositories/base.py`
Base repository with common CRUD operations

```python
from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: Any) -> Optional[ModelType]:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        query = select(self.model)
        for key, value in filters.items():
            if value is not None:
                query = query.where(getattr(self.model, key) == value)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create(self, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def update(self, id: Any, obj_in: dict) -> Optional[ModelType]:
        await self.db.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**obj_in)
        )
        return await self.get(id)

    async def delete(self, id: Any) -> bool:
        result = await self.db.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
```

### `api/routes/items.py`
Example API endpoint

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.database import get_db
from repositories.item_repository import ItemRepository
from schemas.item import ItemResponse, ItemListResponse
from models.item import Item

router = APIRouter(prefix="/api/v1/items", tags=["items"])

@router.get("/", response_model=ItemListResponse)
async def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    product_group: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db)
):
    """List items with pagination and filtering"""
    repo = ItemRepository(db)
    filters = {"is_active": is_active}
    if product_group:
        filters["product_group"] = product_group

    items = await repo.get_all(skip=skip, limit=limit, **filters)
    total = await repo.count(**filters)

    return ItemListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{item_code}", response_model=ItemResponse)
async def get_item(
    item_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get item details with pricing, costs, and margins"""
    repo = ItemRepository(db)
    item = await repo.get_with_details(item_code)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/{item_code}/inventory", response_model=InventoryResponse)
async def get_item_inventory(
    item_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get current inventory status: On Hand, On Order, Committed"""
    repo = InventoryRepository(db)
    inventory = await repo.get_by_item(item_code)
    return inventory
```

### `schemas/common.py`
Common schemas for pagination, filtering

```python
from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    skip: int
    limit: int

    @property
    def pages(self) -> int:
        return (self.total + self.limit - 1) // self.limit

class MessageResponse(BaseModel):
    """Simple message response"""
    message: str
    detail: Optional[str] = None

class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    status_code: int = 400
```

### `main.py`
FastAPI application entry point

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from core.config import get_settings
from core.database import engine
from models.base import Base
from api.routes import auth, items, inventory, pricing, forecasts

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SAP B1 Inventory & Forecast Analyzer API",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(items.router, tags=["items"])
app.include_router(inventory.router, tags=["inventory"])
app.include_router(pricing.router, tags=["pricing"])
app.include_router(forecasts.router, tags=["forecasts"])

@app.on_event("startup")
async def startup():
    """Initialize database connection"""
    async with engine.begin() as conn:
        # Create tables (use Alembic in production)
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("shutdown")
async def shutdown():
    """Close database connection"""
    await engine.dispose()

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

### `tasks/celery_app.py`
Celery configuration

```python
from celery import Celery
from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forecast_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.forecasting", "tasks.sync", "tasks.reports"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    "sync-sap-hourly": {
        "task": "tasks.sync.incremental_sync",
        "schedule": 3600,  # Every hour
    },
    "generate-forecasts-daily": {
        "task": "tasks.forecasting.generate_all_forecasts",
        "schedule": 86400,  # Every day at midnight
        "options": {"queue": "forecasting"},
    },
}
```

### `tasks/forecasting.py`
Background forecast generation

```python
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import async_session
from services.forecast_service import ForecastService
from repositories.item_repository import ItemRepository
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="tasks.forecasting.generate_all_forecasts")
def generate_all_forecasts(self, item_codes: list = None, n_samples: int = None):
    """Generate forecasts for all items (background task)"""
    with async_session() as db:
        try:
            service = ForecastService(db)

            if item_codes:
                # Forecast specific items
                items = item_codes
            else:
                # Get all active items
                repo = ItemRepository(db)
                items = repo.get_all_active_codes()

            logger.info(f"Starting forecast generation for {len(items)} items")

            # Generate forecasts
            results = service.generate_forecasts_batch(
                item_codes=items,
                n_samples=n_samples
            )

            logger.info(f"Completed forecast generation: {len(results)} forecasts")
            return {"status": "success", "count": len(results)}

        except Exception as exc:
            logger.error(f"Forecast generation failed: {exc}")
            self.retry(exc=exc, countdown=60, max_retries=3)

@shared_task(name="tasks.forecasting.calculate_accuracy")
def calculate_forecast_accuracy(snapshot_id: str):
    """Calculate forecast accuracy vs actuals"""
    with async_session() as db:
        try:
            service = ForecastService(db)
            accuracy = service.calculate_accuracy(snapshot_id)
            return {"status": "success", "accuracy": accuracy}
        except Exception as exc:
            logger.error(f"Accuracy calculation failed: {exc}")
            raise
```

### `docker-compose.yml`
Local development environment

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: forecast_user
      POSTGRES_PASSWORD: forecast_pass
      POSTGRES_DB: forecast_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U forecast_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://forecast_user:forecast_pass@postgres:5432/forecast_db
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  celery_worker:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://forecast_user:forecast_pass@postgres:5432/forecast_db
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
    command: celery -A tasks.celery_app worker --loglevel=info

  celery_beat:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://forecast_user:forecast_pass@postgres:5432/forecast_db
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - .:/app
    command: celery -A tasks.celery_app beat --loglevel=info

volumes:
  postgres_data:
  redis_data:
```

### `.env.example`
Environment variables template

```bash
# Application
APP_NAME=SAP B1 Forecast Analyzer
APP_VERSION=1.0.0
DEBUG=False

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# SAP B1 Service Layer
SAP_SERVICE_LAYER_URL=https://your-sap-server:50000/b1s/v1
SAP_COMPANY_DB=YourCompanyDB
SAP_USERNAME=your-sap-username
SAP_PASSWORD=your-sap-password

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Railway (optional)
RAILWAY_PROJECT_ID=
RAILWAY_SERVICE_NAME=
```

### `requirements.txt`
Python dependencies

```txt
# FastAPI
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Database
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
alembic==1.12.1
psycopg2-binary==2.9.9

# Redis
redis==5.0.1
hiredis==2.2.3

# Celery
celery==5.3.4
flower==2.0.1

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6

# Pydantic
pydantic==2.5.0
pydantic-settings==2.1.0
email-validator==2.1.0

# Data Processing
pandas==2.1.3
numpy==1.26.2
pyarrow==14.0.1

# Forecasting
prophet==1.1.5
statsmodels==0.14.0
scikit-learn==1.3.2
scipy==1.11.4

# Utilities
python-dateutil==2.8.2
pyyaml==6.0.1
tqdm==4.66.1
httpx==0.25.2
aiofiles==23.2.1

# Monitoring
sentry-sdk==1.39.1

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2
```

---

## Quick Start Commands

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your settings

# 4. Start local services
docker-compose up -d postgres redis

# 5. Run database migrations
alembic upgrade head

# 6. Start API server
uvicorn main:app --reload

# 7. Start Celery worker (separate terminal)
celery -A tasks.celery_app worker --loglevel=info

# 8. Start Celery beat (separate terminal)
celery -A tasks.celery_app beat --loglevel=info

# 9. Access API
# API docs: http://localhost:8000/api/docs
# ReDoc: http://localhost:8000/api/redoc
```

---

## API Documentation Examples

### OpenAPI Schema
FastAPI automatically generates OpenAPI documentation at `/api/docs`

### Example API Calls

```bash
# List items
curl "http://localhost:8000/api/v1/items?skip=0&limit=10&product_group=Chemicals"

# Get item with inventory
curl "http://localhost:8000/api/v1/items/30555C-DEL/inventory"

# Generate forecasts (async task)
curl -X POST "http://localhost:8000/api/v1/forecasts/generate" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get forecast accuracy
curl "http://localhost:8000/api/v1/forecasts/accuracy?item_code=30555C-DEL"

# Margin analysis
curl "http://localhost:8000/api/v1/analytics/margins?category=High"
```

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=api --cov=services --cov=repositories --cov-report=html

# Run specific test
pytest tests/test_api/test_items.py::test_list_items

# Run async tests
pytest -xvs tests/test_api/test_forecasts.py
```

---

## Deployment to Railway

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
railway init

# 4. Add services
railway add postgresql
railway add redis
railway add --template python

# 5. Configure environment variables
railway variables set DATABASE_URL=$DATABASE_URL
railway variables set SECRET_KEY=$SECRET_KEY
# ... etc

# 6. Deploy
railway up

# 7. Get domain
railway domain
```

---

## Monitoring & Logging

```python
# Logging setup (core/logging.py)
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/app.log')
        ]
    )

# Sentry integration
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
)
```

---

This structure provides a solid foundation for scaling to a production web application with proper separation of concerns, testability, and maintainability.
