#!/usr/bin/env bash
set -euo pipefail

# Nightly backup:
# 1) pg_dump -> gzip
# 2) export SectionTable -> .xlsx
# 3) optional upload to S3
# 4) retention cleanup, so disk doesn't fill up

PROJECT_DIR="${PROJECT_DIR:-$HOME/cnc_office_v2}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups/nightly}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TABLE_EXPORT_PREFIX="${TABLE_EXPORT_PREFIX:-section_table}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-cnc-office/nightly}"

cd "$PROJECT_DIR"
mkdir -p "$BACKUP_DIR"

if [[ -f "$PROJECT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

ts="$(date +%F_%H-%M-%S)"
db_file="$BACKUP_DIR/db_${ts}.sql.gz"
xlsx_file="$BACKUP_DIR/${TABLE_EXPORT_PREFIX}_${ts}.xlsx"

echo "[backup] start: $ts"
echo "[backup] directory: $BACKUP_DIR"

docker compose exec -T db sh -lc \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 > "$db_file"
echo "[backup] db dump saved: $db_file"

docker compose exec -T web python manage.py export_section_table_xlsx \
  --output "/app/backups/nightly/$(basename "$xlsx_file")"
echo "[backup] table export saved: $xlsx_file"

if [[ -n "$S3_BUCKET" ]] && command -v aws >/dev/null 2>&1; then
  aws s3 cp "$db_file" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "$db_file")"
  aws s3 cp "$xlsx_file" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "$xlsx_file")"
  echo "[backup] uploaded to s3://${S3_BUCKET}/${S3_PREFIX}/"
else
  echo "[backup] S3 upload skipped (set S3_BUCKET and install aws cli to enable)"
fi

# Rotate local backups to keep disk usage under control
find "$BACKUP_DIR" -type f -mtime +"$RETENTION_DAYS" -delete
echo "[backup] cleanup done (older than ${RETENTION_DAYS} days removed)"

echo "[backup] done"
