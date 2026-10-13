// Every UI string in en.ts must exist in hi, ta and vi (plural keys only for the plural forms a
// language uses, e.g. Vietnamese has only "_other"). Run: npm run check:i18n
import { readFileSync } from "node:fs";

const dir = new URL("../src/i18n/", import.meta.url);
const load = (name) => {
  let src = readFileSync(new URL(`${name}.ts`, dir), "utf8");
  src = src.replace(/^export default .*$/m, "").replace(/^export type .*$/m, "").replace(`const ${name} = `, "return ");
  return new Function(src)();
};
const flat = (o, p = "", out = {}) => {
  for (const [k, v] of Object.entries(o)) {
    const key = p ? `${p}.${k}` : k;
    if (v && typeof v === "object") flat(v, key, out);
    else out[key] = v;
  }
  return out;
};
const en = flat(load("en"));
let bad = 0;
for (const lang of ["hi", "ta", "vi"]) {
  const x = flat(load(lang));
  const forms = new Intl.PluralRules(lang).resolvedOptions().pluralCategories;
  const needed = Object.keys(en).filter((k) => {
    const m = k.match(/_(zero|one|two|few|many|other)$/);
    return !m || forms.includes(m[1]);
  });
  const missing = needed.filter((k) => !(k in x));
  const extra = Object.keys(x).filter((k) => !(k in en));
  if (missing.length || extra.length) {
    bad++;
    console.error(`${lang}: missing ${missing.join(", ") || "-"}; unknown ${extra.join(", ") || "-"}`);
  }
}
// index.html carries a static first-paint copy of the landing headline and lead: keep it in step
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8").replace(/&amp;/g, "&");
for (const key of ["landing.title", "landing.lead", "landing.eyebrow"]) {
  if (!html.includes(en[key])) {
    bad++;
    console.error(`index.html first-paint shell is out of date: ${key} = ${JSON.stringify(en[key])}`);
  }
}
if (bad) process.exit(1);
console.log("i18n: hi, ta, vi cover every English key; the first-paint shell matches");
