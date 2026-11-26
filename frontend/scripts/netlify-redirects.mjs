// Gera dist/_redirects no build do Netlify: /api/* vai para a API (proxy, sem CORS)
// e as demais rotas caem no index.html (aplicação de página única).
import { writeFileSync } from "node:fs";

const raw = (process.env.API_URL || "").trim();
let origin;
try {
  const url = new URL(raw);
  if (url.protocol !== "https:") throw new Error("a URL deve começar com https://");
  origin = url.origin; // só o domínio: ignora /api, /api/health, barras etc.
  if (url.pathname.replace(/\/+$/, "") !== "") {
    console.warn(`API_URL tinha um caminho extra ("${url.pathname}"); usando só ${origin}`);
  }
} catch (err) {
  console.error(
    `API_URL inválida (${raw ? `"${raw}": ${err.message}` : "não definida"}). ` +
      "Defina no Netlify a URL da API, ex.: https://personal-trader-api.onrender.com",
  );
  process.exit(1);
}

const rules = [`/api/*  ${origin}/api/:splat  200`, `/*  /index.html  200`];
writeFileSync("dist/_redirects", rules.join("\n") + "\n");
console.log("dist/_redirects:\n" + rules.join("\n"));
