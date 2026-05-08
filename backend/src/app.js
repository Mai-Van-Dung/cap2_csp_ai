import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import dotenv from "dotenv";
import { createServer } from "http";
import { Server as SocketIOServer } from "socket.io";
import { testConnection } from "./config/database.js";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5001;
const httpServer = createServer(app);
const io = new SocketIOServer(httpServer, {
  cors: {
    origin: process.env.CORS_ORIGIN || "*",
    credentials: true,
  },
});

// Middleware
app.use(
  cors({
    origin: process.env.CORS_ORIGIN || "*",
    credentials: true,
  }),
);
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

io.on("connection", (socket) => {
  console.log("[SOCKET] client connected", socket.id);

  socket.on("disconnect", () => {
    console.log("[SOCKET] client disconnected", socket.id);
  });
});

// Health check route
app.get("/api/health", (req, res) => {
  res.json({ status: "OK", timestamp: new Date() });
});

// Internal alert notification endpoint used by the Python camera service.
app.post("/api/alerts/notify", (req, res) => {
  const {
    object_type,
    camera_name,
    confidence,
    image_path,
    image_url,
    message,
    secret,
    source,
  } = req.body || {};

  if (!object_type || !camera_name) {
    return res.status(400).json({
      status: "error",
      message: "object_type and camera_name are required",
    });
  }

  const expectedSecret = (process.env.INTERNAL_SECRET || "").trim();
  if (expectedSecret && secret && String(secret).trim() !== expectedSecret) {
    return res.status(401).json({
      status: "error",
      message: "invalid secret",
    });
  }

  const normalizedImagePath =
    typeof image_path === "string" ? image_path.trim() : "";
  const normalizedImageUrl = (() => {
    if (typeof image_url === "string" && image_url.trim()) {
      return image_url.trim();
    }

    if (!normalizedImagePath) {
      return "";
    }

    const publicBase = (
      process.env.ALERT_IMAGE_PUBLIC_BASE_URL ||
      process.env.PUBLIC_BASE_URL ||
      ""
    ).replace(/\/+$/, "");
    return publicBase
      ? `${publicBase}/${normalizedImagePath.replace(/^\/+/, "")}`
      : normalizedImagePath;
  })();

  const alertPayload = {
    object_type,
    camera_name,
    confidence,
    image_path: normalizedImagePath,
    image_url: normalizedImageUrl,
    message: message || "ALERT",
    source: source || "node-relay",
    created_at: new Date().toISOString(),
  };

  console.log("[ALERT] notify", {
    ...alertPayload,
  });

  io.emit("new_alert", alertPayload);

  return res.json({
    status: "success",
    message: "Alert notification accepted",
    socket_emitted: true,
    telegram: false,
    alert: alertPayload,
  });
});

// API routes
import authRoutes from "./routes/authRoutes.js";
import userRoutes from "./routes/userRoutes.js";
app.use("/api/auth", authRoutes);
app.use("/api/users", userRoutes);

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: "Something went wrong!" });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: "Route not found" });
});

// Start server
async function startServer() {
  try {
    // Test kết nối MySQL
    await testConnection();

    httpServer.listen(PORT, () => {
      console.log(`🚀 Server running on http://localhost:${PORT}`);
      console.log(`📝 Environment: ${process.env.NODE_ENV}`);
    });
  } catch (error) {
    console.error("Failed to start server:", error);
    process.exit(1);
  }
}

startServer();

export default app;
