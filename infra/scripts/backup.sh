#!/bin/sh
# Бэкап прода: pg_dump (custom format) + архив загруженных файлов, хранение BACKUP_KEEP_DAYS дней.
# Запускается сервисом backup из infra/docker-compose.yml: без аргументов — цикл раз в BACKUP_INTERVAL_HOURS,
# `once` — один бэкап сейчас, `list` — список. Восстановление — docs/deploy.md, раздел «Бэкапы».
set -eu

DIR="${BACKUP_DIR:-/backups}"
UPLOADS="${BACKUP_UPLOADS_DIR:-/uploads}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
INTERVAL=$(( ${BACKUP_INTERVAL_HOURS:-24} * 3600 ))
export PGPASSWORD="${POSTGRES_PASSWORD}"

backup() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  dump="${DIR}/db-${stamp}.dump"
  pg_dump -h "${PGHOST:-db}" -p "${PGPORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -f "${dump}.tmp"
  mv "${dump}.tmp" "${dump}"
  if [ -d "${UPLOADS}" ]; then
    tar -czf "${DIR}/uploads-${stamp}.tar.gz.tmp" -C "${UPLOADS}" .
    mv "${DIR}/uploads-${stamp}.tar.gz.tmp" "${DIR}/uploads-${stamp}.tar.gz"
  fi
  find "${DIR}" -name 'db-*.dump' -mtime +"${KEEP_DAYS}" -delete
  find "${DIR}" -name 'uploads-*.tar.gz' -mtime +"${KEEP_DAYS}" -delete
  echo "backup ok: ${dump} ($(du -h "${dump}" | cut -f1))"
}

case "${1:-loop}" in
  once) backup ;;
  list) ls -lh "${DIR}" ;;
  loop)
    while true; do
      backup || echo "backup failed" >&2
      sleep "${INTERVAL}"
    done ;;
  *) echo "usage: backup.sh [loop|once|list]" >&2; exit 2 ;;
esac
