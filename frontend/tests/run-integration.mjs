import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { setTimeout } from "node:timers/promises";
const root = fileURLToPath(new URL("../../", import.meta.url));
const frontend = fileURLToPath(new URL("../", import.meta.url));
const children = [];
function start(command, args, cwd, env) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: "inherit",
  });
  children.push(child);
  return child;
}
async function ready(url) {
  for (let i = 0; i < 60; i++) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      /* wait for startup */
    }
    await setTimeout(500);
  }
  throw new Error(`Local service failed to start: ${url}`);
}
try {
  start(
    process.env.CLUTCH_TEST_PYTHON || "python",
    [
      "-m",
      "uvicorn",
      "backend.app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8026",
    ],
    root,
    {
      OPENAI_API_KEY: "",
      DATABASE_URL: "",
      REDIS_URL: "",
      CLUTCH_API_KEY: "",
      CLUTCH_REQUIRE_AUTH: "false",
      LANGFUSE_TRACING_ENABLED: "false",
    },
  );
  start(
    process.execPath,
    [
      "node_modules/next/dist/bin/next",
      "start",
      "--hostname",
      "127.0.0.1",
      "--port",
      "3026",
    ],
    frontend,
    {
      CLUTCH_API_BASE_URL: "http://127.0.0.1:8026",
      CLUTCH_API_KEY: "",
      CLUTCH_ALLOW_LOCAL_ANONYMOUS: "true",
      VERCEL: "",
    },
  );
  await Promise.all([
    ready("http://127.0.0.1:8026/health"),
    ready("http://127.0.0.1:3026"),
  ]);
  const tests = start(
    process.execPath,
    ["--import", "tsx", "--test", "tests/integration.test.ts"],
    frontend,
    { CLUTCH_TEST_URL: "http://127.0.0.1:3026" },
  );
  const result = await new Promise((resolve, reject) => {
    tests.on("exit", resolve);
    tests.on("error", reject);
  });
  if (result !== 0) process.exitCode = 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  for (const child of children)
    if (child.exitCode === null) child.kill("SIGTERM");
}
