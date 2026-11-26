// Gera dist/_redirects no build do Netlify: /api/* vai para a API (proxy, sem CORS)
// e as demais rotas caem no index.html (aplicação de página única).
import { writeFileSync } from "node:fs";

const api = (process.env.API_URL || "").trim().replace(/\/+$/, "");
if (!/^https:\/\/[^/]+/.test(api)) {
  console.error("Defina a variável API_URL no Netlify com a URL https da API (ex.: https://personal-trader-api.onrender.com).");
  process.exit(1);
}
const rules = [`/api/*  ${api}/api/:splat  200`, `/*  /index.html  200`];
writeFileSync("dist/_redirects", rules.join("\n") + "\n");
console.log("dist/_redirects:\n" + rules.join("\n"));
