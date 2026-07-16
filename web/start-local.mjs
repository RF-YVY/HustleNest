import path from "node:path";

// vinext 0.0.50 stores production asset-cache keys using path.relative().
// Windows returns backslashes there, while browser URLs always use slashes,
// so every compiled stylesheet and script otherwise misses the cache.
if (process.platform === "win32") {
  const relative = path.relative;
  path.relative = (...args) => relative(...args).replaceAll("\\", "/");
}

const args = process.argv.slice(2);
const option = (shortName, longName, fallback) => {
  const index = args.findIndex((arg) => arg === shortName || arg === longName);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const port = Number(option("-p", "--port", process.env.PORT ?? "3000"));
const host = option("-H", "--hostname", "0.0.0.0");

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`Invalid frontend port: ${port}`);
}

const { startProdServer } = await import("./node_modules/vinext/dist/server/prod-server.js");
await startProdServer({ host, port, outDir: path.resolve("dist") });
