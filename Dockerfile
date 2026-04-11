# -- Stage 1: Build frontend --
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# -- Stage 2: Python app --
FROM python:3.12-slim
WORKDIR /app

# Copy source first, then install (hatch needs src/ to build the package)
COPY pyproject.toml ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN pip install --no-cache-dir .

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist frontend/dist

# Data directory for SQLite
RUN mkdir -p /app/data
VOLUME /app/data

ENV FPL_DB_PATH=/app/data/fpl.db

EXPOSE 3001

CMD ["uvicorn", "fpl.api.app:app", "--host", "0.0.0.0", "--port", "3001"]
