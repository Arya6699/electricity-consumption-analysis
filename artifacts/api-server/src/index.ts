import app from "./app";
import { logger } from "./lib/logger";
import { spawn } from "node:child_process";
import path from "node:path";

const rawPort = process.env["PORT"];

if (!rawPort) {
  throw new Error(
    "PORT environment variable is required but was not provided.",
  );
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const workspaceRoot = path.resolve(process.cwd(), "../..");
const backendDirectory = path.resolve(
  process.cwd(),
  "../electricity-demand-prediction",
);
const analyticsPort = process.env["ELECTRICITY_BACKEND_PORT"] ?? "8765";
const pythonBackend = spawn(
  "uv",
  [
    "run",
    "--project",
    workspaceRoot,
    "python",
    "-m",
    "uvicorn",
    "backend.main:app",
    "--app-dir",
    backendDirectory,
    "--host",
    "127.0.0.1",
    "--port",
    analyticsPort,
  ],
  {
    cwd: process.cwd(),
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: "inherit",
  },
);

pythonBackend.on("error", (err) => {
  logger.error({ err }, "Could not start the FastAPI analytics service");
});
pythonBackend.on("exit", (code, signal) => {
  if (code !== 0 && code !== null) {
    logger.error({ code }, "FastAPI analytics service exited unexpectedly");
  } else if (signal) {
    logger.info({ signal }, "FastAPI analytics service stopped");
  }
});

const stopPythonBackend = () => {
  if (pythonBackend.exitCode === null && !pythonBackend.killed) {
    pythonBackend.kill("SIGTERM");
  }
};
process.on("SIGINT", () => {
  stopPythonBackend();
  process.exit(0);
});
process.on("SIGTERM", () => {
  stopPythonBackend();
  process.exit(0);
});
process.on("exit", stopPythonBackend);

app.listen(port, (err) => {
  if (err) {
    logger.error({ err }, "Error listening on port");
    process.exit(1);
  }

  logger.info({ port }, "Server listening");
});
