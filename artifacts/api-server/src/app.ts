import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import router from "./routes";
import { logger } from "./lib/logger";

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());
app.use(express.json({ limit: "160mb" }));
app.use(express.urlencoded({ extended: true }));

// Keep the shared /api routing contract while running the Python/FastAPI
// analytics service as a local sidecar behind this stable public path.
app.use("/api/electricity", async (req, res): Promise<void> => {
  const backendPort = process.env["ELECTRICITY_BACKEND_PORT"] ?? "8765";
  const backendPath = req.originalUrl.replace(/^\/api/, "");
  const requestBody =
    req.method === "GET" || req.method === "HEAD"
      ? undefined
      : JSON.stringify(req.body ?? {});

  try {
    const response = await fetch(
      `http://127.0.0.1:${backendPort}${backendPath}`,
      {
        method: req.method,
        headers: { "content-type": "application/json" },
        body: requestBody,
      },
    );
    const contentType = response.headers.get("content-type");
    if (contentType) {
      res.setHeader("content-type", contentType);
    }
    res.status(response.status).send(Buffer.from(await response.arrayBuffer()));
  } catch (err) {
    req.log.warn({ err }, "Electricity analytics backend is unavailable");
    res.status(503).json({
      detail: "The FastAPI analytics service is starting or unavailable. Retry shortly.",
    });
  }
});

app.use("/api", router);

export default app;
