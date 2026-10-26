// Usage: node run.js <rules.js> <file.pdf>...   prints name and fields
const fs = require("fs"), vm = require("vm"), path = require("path");
const dir = __dirname;
globalThis.window = globalThis; globalThis.self = globalThis;
const rulesFile = process.argv[2];
window.TS_RULES = JSON.parse(fs.readFileSync(rulesFile, "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(process.env.MERLE_JS || dir, "worker.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(process.env.MERLE_JS || dir, "pdf.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(process.env.MERLE_JS || dir, "tsn.js"), "utf8") + "\nglobalThis.TSN = TSN;");
const dump = process.env.DUMP;
(async () => {
  for (const f of process.argv.slice(3)) {
    const text = await TSN.pdfText(new Uint8Array(fs.readFileSync(f)));
    if (dump) { fs.writeFileSync(path.join(dump, path.basename(f) + ".txt"), text); }
    const ts = TSN.extractFields(text);
    const name = TSN.buildName(TSN.valuesOf(ts));
    const expected = path.basename(f).replace(/\.pdf$/i, "").replace(/ {2,}/g, " ");
    console.log((name === expected ? "OK   " : "DIFF ") + name + "\n     expected: " + expected);
    if (process.env.V) for (const [k, v] of Object.entries(ts)) console.log(`   ${k.padEnd(18)} ${JSON.stringify(v.value)}  ${v.warning ? "!! " + v.warning : ""}  <${(v.source||"").slice(0,90)}>`);
  }
})().catch((e) => { console.error(e); process.exit(1); });
