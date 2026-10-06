#!/bin/sh
# Бэкап прода: pg_dump (custom format) + архив загруженных файлов, хранение BACKUP_KEEP_DAYS дней.
# Запускается сервисом backup из infra/docker-compose.yml: без аргументов — цикл раз в BACKUP_INTERVAL_HOURS,
# `once` — один бэкап сейчас, `list` — список. Восстановление — docs/deploy.md, раздел «Бэкапы».
set -eu

DIR="${BACKUP_DIR:-/backups}"
UPLOADS="${BACKUP_UPLOADS_DIR:-/uploads}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
INTERVAL=$(( ${BACKUP_INTERVAL_HOURS:-24} * 3600 ))
# Запросы внеочередного бэкапа от backend (reseed из кабинета): файл <id>.request → <id>.ok | <id>.failed
REQUESTS="${BACKUP_REQUESTS_DIR:-/requests}"
export PGPASSWORD="${POSTGRES_PASSWORD}"

# Внутри `backup || ...` set -e не действует, поэтому каждый шаг проверяется явно: при любой ошибке
# временные файлы удаляются, а ротация старых копий не выполняется
fail() {
  echo "backup failed: $1" >&2
  rm -f "${dump}.tmp" "${archive}.tmp"
  return 1
}

backup() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ) || return 1
  dump="${DIR}/db-${stamp}.dump"
  archive="${DIR}/uploads-${stamp}.tar.gz"
  pg_dump -h "${PGHOST:-db}" -p "${PGPORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -f "${dump}.tmp" \
    || { fail "pg_dump"; return 1; }
  # Дамп проверяется до ротации: pg_restore -l читает оглавление архива custom-формата
  [ -s "${dump}.tmp" ] || { fail "empty dump"; return 1; }
  pg_restore -l "${dump}.tmp" >/dev/null || { fail "dump is not readable by pg_restore"; return 1; }
  mv "${dump}.tmp" "${dump}" || { fail "mv dump"; return 1; }
  if [ -d "${UPLOADS}" ]; then
    tar -czf "${archive}.tmp" -C "${UPLOADS}" . || { fail "tar uploads"; return 1; }
    tar -tzf "${archive}.tmp" >/dev/null || { fail "uploads archive is not readable"; return 1; }
    mv "${archive}.tmp" "${archive}" || { fail "mv uploads archive"; return 1; }
  fi
  # Ротация — только после проверенного свежего дампа
  find "${DIR}" -name 'db-*.dump' -mtime +"${KEEP_DAYS}" -delete || { fail "rotate dumps"; return 1; }
  find "${DIR}" -name 'uploads-*.tar.gz' -mtime +"${KEEP_DAYS}" -delete || { fail "rotate uploads"; return 1; }
  echo "backup ok: ${dump} ($(du -h "${dump}" | cut -f1))"
}

case "${1:-loop}" in
  once) backup ;;
  list) ls -lh "${DIR}" ;;
  loop)
    next=0
    while true; do
      if [ "$(date +%s)" -ge "${next}" ]; then
        backup || echo "backup failed" >&2
        next=$(( $(date +%s) + INTERVAL ))
      fi
      if [ -d "${REQUESTS}" ]; then
        for request in "${REQUESTS}"/*.request; do
          [ -e "${request}" ] || continue
          if backup; then
            mv "${request}" "${request%.request}.ok"
          else
            mv "${request}" "${request%.request}.failed"
          fi
        done
      fi
      sleep 5
    done ;;
  *) echo "usage: backup.sh [loop|once|list]" >&2; exit 2 ;;
esac
