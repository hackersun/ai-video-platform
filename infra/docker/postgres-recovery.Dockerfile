FROM postgres:15.13-alpine

RUN apk add --no-cache python3 \
    && adduser -D -u 10001 recovery

WORKDIR /app

COPY backend/app/__init__.py /app/app/__init__.py
COPY backend/app/features/__init__.py /app/app/features/__init__.py
COPY backend/app/features/operations /app/app/features/operations
COPY backend/scripts/backup_postgres.py /app/scripts/backup_postgres.py
COPY backend/scripts/restore_postgres.py /app/scripts/restore_postgres.py

RUN chown -R recovery:recovery /app

USER recovery

ENTRYPOINT ["python3"]
