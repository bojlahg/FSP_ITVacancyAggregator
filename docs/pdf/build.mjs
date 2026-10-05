// Собирает сопроводительную документацию в один PDF: docs/ITScout-docs.pdf.
// Markdown → HTML (marked), диаграммы Mermaid и печать — в Chromium (playwright-core).
// Запуск: cd docs/pdf && npm ci && npm run build. Chromium: CHROMIUM_PATH или браузер Playwright.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Marked } from "marked";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../..");
const docs = resolve(root, "docs");
const fonts = resolve(root, "backend/app/modules/resume/assets/fonts");
const out = resolve(docs, "ITScout-docs.pdf");

// Порядок — по пунктам 3.4 ТЗ; README идёт обзором
const PARTS = [
  ["README.md", "overview", root],
  ["architecture.md", "architecture"],
  ["testing.md", "testing"],
  ["matching.md", "matching"],
  ["validation.md", "validation"],
  ["fsp-integration.md", "fsp-integration"],
  ["api.md", "api"],
  ["api-endpoints.md", "api-endpoints"],
  ["versions.md", "versions"],
  ["deploy.md", "deploy"],
  ["security.md", "security"],
  ["performance.md", "performance"],
  ["anti-fraud-ats.md", "anti-fraud-ats"],
  ["limitations.md", "limitations"],
];
const anchorOf = new Map(PARTS.map(([file, id]) => [file, id]));

const escape = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function render(file, id, base) {
  const markdown = readFileSync(resolve(base ?? docs, file), "utf8").replace(/<!--[\s\S]*?-->/g, "");
  const dir = base ?? docs;
  const marked = new Marked({
    gfm: true,
    renderer: {
      code({ text, lang }) {
        // На книжной A4 горизонтальные схемы ужимаются до нечитаемых — в PDF разворачиваем их вертикально
        if (lang === "mermaid") return `<div class="mermaid">${escape(text.replace(/^flowchart LR/m, "flowchart TB"))}</div>`;
        return `<pre><code>${escape(text)}</code></pre>`;
      },
      link({ href, tokens }) {
        const label = this.parser.parseInline(tokens);
        const name = href.split("/").pop().split("#")[0];
        if (anchorOf.has(name)) return `<a href="#${anchorOf.get(name)}">${label}</a>`;
        if (/^https?:/.test(href)) return `<a href="${href}">${label}</a>`;
        // Файлы репозитория (код, отчёт валидации): в PDF — просто имя
        return `<span class="file">${label}</span>`;
      },
      image({ href, text }) {
        const src = /^https?:/.test(href) ? href : pathToFileURL(resolve(dir, href)).href;
        return `<figure><img src="${src}" alt="${escape(text)}"><figcaption>${escape(text)}</figcaption></figure>`;
      },
    },
  });
  return `<section class="part" id="${id}">${marked.parse(markdown)}</section>`;
}

function toc() {
  const items = PARTS.map(([file, id, base]) => {
    const title = readFileSync(resolve(base ?? docs, file), "utf8")
      .replace(/<!--[\s\S]*?-->/g, "")
      .match(/^#\s+(.+)$/m)[1];
    return `<li><a href="#${id}">${escape(id === "overview" ? "Обзор решения" : title)}</a></li>`;
  });
  return `<section class="toc"><h2>Содержание</h2><ol>${items.join("")}</ol></section>`;
}

const font = (family, file, weight) =>
  `@font-face{font-family:"${family}";src:url("${pathToFileURL(resolve(fonts, file)).href}") format("woff2");font-weight:${weight};}`;

const css = `
${font("JetBrains Mono", "JetBrainsMono-Regular.woff2", 400)}
${font("JetBrains Mono", "JetBrainsMono-Bold.woff2", 700)}
${font("Inter", "inter-latin-400-normal.woff2", 400)}
${font("Inter", "inter-cyrillic-400-normal.woff2", 400)}
${font("Inter", "inter-latin-600-normal.woff2", 600)}
${font("Inter", "inter-cyrillic-600-normal.woff2", 600)}
:root{--blue:#402FFF;--red:#EC1D35;--dark:#1B1C21;--gray:#EDEDED;--line:#C8C9CA;}
@page{size:A4;margin:18mm 16mm 18mm 16mm;}
html{font-family:"Inter",sans-serif;font-size:10pt;color:var(--dark);line-height:1.5;}
body{margin:0;}
h1,h2,h3,h4{font-family:"JetBrains Mono",monospace;line-height:1.25;color:var(--dark);break-after:avoid;}
h1{font-size:20pt;margin:0 0 6mm;padding-bottom:3mm;border-bottom:2px solid var(--blue);}
h2{font-size:13pt;margin:7mm 0 3mm;color:var(--blue);}
h3{font-size:11pt;margin:5mm 0 2mm;}
.part{break-before:page;}
a{color:var(--blue);text-decoration:none;}
code,pre,.file{font-family:"JetBrains Mono",monospace;font-size:8.5pt;}
code{background:var(--gray);padding:0 3px;border-radius:3px;}
pre{background:var(--gray);padding:3mm;border-radius:4px;white-space:pre-wrap;break-inside:avoid;}
pre code{background:none;padding:0;}
table{border-collapse:collapse;width:100%;margin:3mm 0;font-size:8.5pt;break-inside:auto;}
th,td{border:1px solid var(--line);padding:1.5mm 2mm;vertical-align:top;text-align:left;}
th{background:var(--gray);font-family:"JetBrains Mono",monospace;font-weight:700;}
tr{break-inside:avoid;}
blockquote{margin:3mm 0;padding:2mm 4mm;border-left:3px solid var(--blue);background:#F4F3FF;}
figure{margin:4mm 0;text-align:center;break-inside:avoid;}
figure img{max-width:100%;max-height:105mm;}
figcaption{font-size:8pt;color:#555;}
.mermaid{margin:4mm 0;text-align:center;break-inside:avoid;}
.mermaid svg{max-width:100%;height:auto;max-height:200mm;}
.cover{height:250mm;display:flex;flex-direction:column;justify-content:space-between;}
.cover .logo{height:16mm;}
.cover h1{font-size:44pt;border:none;margin:0;}
.cover h1 b{color:var(--blue);}
.cover .sub{font-family:"JetBrains Mono",monospace;font-size:14pt;margin-top:4mm;}
.cover .meta{font-size:10pt;color:#555;line-height:1.8;}
.cover .trace{border-top:2px solid var(--blue);width:60%;margin-top:6mm;}
.toc{break-before:page;}
.toc ol{font-size:11pt;line-height:2;}
`;

const cover = `
<section class="cover">
  <img class="logo" src="${pathToFileURL(resolve(docs, "brandook/logo_01.svg")).href}">
  <div>
    <h1><b>IT</b>Scout</h1>
    <div class="sub">Сопроводительная документация</div>
    <div class="trace"></div>
    <p>Платформа ИТ-подбора с обратной механикой: кандидат подтверждает уровень адаптивным тестом,
    работодатель сам находит его по категории «специализация × грейд» и приходит с предложением и вилкой зарплаты.</p>
  </div>
  <div class="meta">
    Спецтрек ФСП · Лидеры цифровой трансформации 2026<br>
    Прототип: https://itscout.ru · API: https://itscout.ru/api/docs<br>
    Репозиторий: https://github.com/bojlahg/FSP_ITVacancyAggregator<br>
    Сборка: ${new Date().toISOString().slice(0, 10)}
  </div>
</section>`;

const mermaidJs = pathToFileURL(resolve(here, "node_modules/mermaid/dist/mermaid.min.js")).href;
const html = `<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>ITScout — документация</title>
<style>${css}</style><script src="${mermaidJs}"></script></head><body>
${cover}${toc()}${PARTS.map(([file, id, base]) => render(file, id, base)).join("\n")}
<script>
mermaid.initialize({startOnLoad:false,securityLevel:"loose",theme:"base",fontFamily:"Inter",
  flowchart:{htmlLabels:true,useMaxWidth:true},
  themeVariables:{primaryColor:"#EFEDFF",primaryBorderColor:"#402FFF",primaryTextColor:"#1B1C21",
    lineColor:"#402FFF",secondaryColor:"#EDEDED",tertiaryColor:"#FFFFFF",fontFamily:"Inter",fontSize:"13px"}});
mermaid.run({querySelector:".mermaid"}).then(()=>{document.body.dataset.ready="1"},
  (e)=>{document.body.dataset.ready="error";document.body.dataset.error=(e && (e.message || e.str)) || JSON.stringify(e)});
</script></body></html>`;

const htmlPath = resolve(here, "docs.html");
writeFileSync(htmlPath, html);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage();
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
await page.waitForFunction(() => document.body.dataset.ready, null, { timeout: 120_000 });
const state = await page.evaluate(() => [document.body.dataset.ready, document.body.dataset.error]);
if (state[0] !== "1") throw new Error(`Mermaid: ${state[1]}`);
await page.evaluate(() => document.fonts.ready);
await page.pdf({
  path: out,
  format: "A4",
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate:
    '<div style="width:100%;font-family:monospace;font-size:7pt;color:#888;padding:0 16mm;display:flex;justify-content:space-between">' +
    '<span>ITScout · сопроводительная документация</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
  margin: { top: "16mm", bottom: "18mm", left: "16mm", right: "16mm" },
});
await browser.close();
console.log(`PDF: ${out}`);
