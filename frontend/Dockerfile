# Контекст сборки — корень репозитория (нужен infra/Caddyfile). Итоговый образ: Caddy со статикой SPA.
FROM node:22-alpine AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/frontend/dist /srv/site
