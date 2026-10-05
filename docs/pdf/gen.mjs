// Генерирует docs/versions.md (из lock-файлов) и docs/api-endpoints.md (из backend/openapi.json).
// Руками эти два файла не правятся: `cd docs/pdf && npm run gen`.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseToml } from "smol-toml";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const read = (p) => readFileSync(resolve(root, p), "utf8");
const json = (p) => JSON.parse(read(p));
const header = (cmd) =>
  `<!-- Сгенерировано \`${cmd}\` (docs/pdf/gen.mjs). Не править руками. -->\n\n`;

// --- версии ---------------------------------------------------------------

const normalize = (name) => name.toLowerCase().replace(/[-_.]+/g, "-");
const depName = (spec) => spec.split(/[<>=!~;\[ ]/)[0].trim();

function pythonRows(project) {
  const pyproject = parseToml(read(`${project}/pyproject.toml`));
  const lock = parseToml(read(`${project}/uv.lock`));
  const locked = new Map(lock.package.map((p) => [normalize(p.name), p.version]));
  const rows = [];
  const add = (specs, scope) => {
    for (const spec of specs ?? []) {
      const name = depName(spec);
      rows.push([name, locked.get(normalize(name)) ?? "—", scope]);
    }
  };
  add(pyproject.project.dependencies, "runtime");
  add(pyproject["dependency-groups"]?.dev, "dev");
  return rows;
}

function nodeRows(project) {
  const pkg = json(`${project}/package.json`);
  const lock = json(`${project}/package-lock.json`);
  const rows = [];
  for (const [deps, scope] of [
    [pkg.dependencies, "runtime"],
    [pkg.devDependencies, "dev"],
  ]) {
    for (const name of Object.keys(deps ?? {})) {
      rows.push([name, lock.packages[`node_modules/${name}`]?.version ?? "—", scope]);
    }
  }
  return rows;
}

function imageRows() {
  const rows = [];
  const files = [
    ["infra/docker-compose.yml", /^\s*image:\s*(\S+)/gm, "compose"],
    ["infra/docker-compose.dev.yml", /^\s*image:\s*(\S+)/gm, "compose (dev)"],
    ["backend/Dockerfile", /^FROM\s+(\S+)/gm, "backend"],
    ["fsp-mock/Dockerfile", /^FROM\s+(\S+)/gm, "fsp-mock"],
    ["frontend/Dockerfile", /^FROM\s+(\S+)/gm, "frontend + Caddy"],
    ["infra/keycloak/Dockerfile", /^FROM\s+(\S+)/gm, "мок ФСП ID"],
  ];
  for (const [file, re, where] of files) {
    for (const m of read(file).matchAll(re)) rows.push([m[1], where]);
  }
  return rows;
}

const table = (head, rows) =>
  [`| ${head.join(" | ")} |`, `|${head.map(() => "---").join("|")}|`, ...rows.map((r) => `| ${r.join(" | ")} |`)].join(
    "\n",
  );

function versionsMd() {
  const uvPin = read("backend/Dockerfile").match(/uv[>=<,.\d]+/)?.[0] ?? "uv";
  const sections = [
    ["Backend (Python 3.12, `backend/uv.lock`)", pythonRows("backend")],
    ["Мок реестра ФСП (`fsp-mock/uv.lock`)", pythonRows("fsp-mock")],
    ["Frontend (`frontend/package-lock.json`)", nodeRows("frontend")],
    ["e2e (`e2e/package-lock.json`)", nodeRows("e2e")],
    ["Сборка PDF документации (`docs/pdf/package-lock.json`)", nodeRows("docs/pdf")],
  ];
  let md = header("cd docs/pdf && npm run gen");
  md += "# Библиотеки и компоненты с версиями\n\n";
  md +=
    "Прямые зависимости каждой части и версии, зафиксированные в lock-файлах (транзитивные зависимости — в самих lock-файлах). " +
    "Сборки воспроизводимы: `uv sync --frozen` и `npm ci` ставят ровно эти версии. Лицензия проекта — MIT.\n\n";
  md += "## Платформа и образы\n\n";
  md += table(
    ["Компонент", "Где используется"],
    [
      ["Python 3.12", "backend, fsp-mock, validation"],
      [`${uvPin.replace(/"/g, "")} (менеджер пакетов Python)`, "backend/Dockerfile, CI"],
      ["Node.js 22", "сборка frontend, e2e, PDF документации"],
      ["PostgreSQL 16", "основная БД"],
      ...imageRows().map(([image, where]) => [`\`${image}\``, where]),
    ],
  );
  md += "\n\n";
  for (const [title, rows] of sections) {
    md += `## ${title}\n\n${table(["Пакет", "Версия", "Тип"], rows.map(([n, v, s]) => [`\`${n}\``, v, s]))}\n\n`;
  }
  return md;
}

// --- эндпоинты --------------------------------------------------------------

function apiMd() {
  const spec = json("backend/openapi.json");
  const byTag = new Map((spec.tags ?? []).map((t) => [t.name, []]));
  let total = 0;
  for (const [path, ops] of Object.entries(spec.paths)) {
    for (const [method, op] of Object.entries(ops)) {
      if (!["get", "post", "put", "patch", "delete"].includes(method)) continue;
      total += 1;
      const tag = op.tags?.[0] ?? "other";
      if (!byTag.has(tag)) byTag.set(tag, []);
      const codes = Object.keys(op.responses ?? {}).filter((c) => !c.startsWith("2"));
      const ok = Object.keys(op.responses ?? {}).find((c) => c.startsWith("2")) ?? "";
      const auth = op.security ? "JWT" : "—";
      byTag
        .get(tag)
        .push([`\`${method.toUpperCase()}\``, `\`${path.replace(/^\/api\/v1/, "")}\``, op.summary ?? "", auth, ok, codes.join(", ")]);
    }
  }
  let md = header("cd docs/pdf && npm run gen");
  md += "# Справочник эндпоинтов\n\n";
  md += `${spec.info.title} ${spec.info.version}: ${total} операций. Префикс \`/api/v1\`; схемы запросов и ответов — в \`backend/openapi.json\` и Swagger UI (\`/api/docs\`). `;
  md += "Колонка «Ошибки» — описанные коды ответов, тело ошибки всегда `{error: {code, message, details}}`.\n\n";
  for (const [tag, rows] of byTag) {
    if (!rows.length) continue;
    md += `## ${tag}\n\n${table(["Метод", "Путь", "Назначение", "Доступ", "Успех", "Ошибки"], rows)}\n\n`;
  }
  return md;
}

if (!existsSync(resolve(root, "backend/openapi.json"))) throw new Error("нет backend/openapi.json");
writeFileSync(resolve(root, "docs/versions.md"), versionsMd());
writeFileSync(resolve(root, "docs/api-endpoints.md"), apiMd());
console.log("docs/versions.md, docs/api-endpoints.md обновлены");
