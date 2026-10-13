// Number entry: what a person types becomes the quantity the API stores, never a misread one
// ("15,4" is 15.4, not 154; a minus sign or letters are refused). Run: npm run check:format
import { readFileSync } from "node:fs";
import { transformSync } from "esbuild";

const ts = readFileSync(new URL("../src/lib/format.ts", import.meta.url), "utf8");
const { code } = transformSync(ts, { loader: "ts", format: "esm" });
const { parseQuantity } = await import("data:text/javascript," + encodeURIComponent(code));

const cases = [
  ["15.4", "en", "15.4"],
  ["15,4", "en", "15.4"],
  ["15,90", "en", "15.90"],
  ["1,234", "en", "1234"],
  ["1,23,456.78", "en", "123456.78"],
  ["12,345,678", "en", "12345678"],
  ["15.4 t", "en", "15.4"],
  ["₹ 21,192", "en", "21192"],
  ["120,000 kg", "en", "120000"],
  [" 70.0 ", "en", "70.0"],
  ["1.234,5", "vi", "1234.5"],
  ["1.234", "vi", "1234"],
  ["15,4", "vi", "15.4"],
  ["abc", "en", null],
  ["", "en", null],
  [".", "en", null],
  ["1.2.3", "en", null],
  ["-5", "en", null],
  ["−5", "en", null],
  ["1e5", "en", null],
  ["1.234,5", "en", null],
];
const bad = cases.filter(([input, lang, want]) => parseQuantity(input, lang) !== want);
for (const [input, lang, want] of bad) console.error(`parseQuantity(${JSON.stringify(input)}, ${lang}) = ${JSON.stringify(parseQuantity(input, lang))}, expected ${JSON.stringify(want)}`);
if (bad.length) process.exit(1);
console.log(`format: ${cases.length} number-entry cases read as intended`);
