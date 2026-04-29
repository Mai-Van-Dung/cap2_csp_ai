import express from "express";

const router = express.Router();

router.get("/health", (req, res) => {
  res.json({ status: "ok", service: "auth" });
});

router.post("/login", (req, res) => {
  res.status(501).json({
    message: "Auth login is not implemented in this backend yet.",
  });
});

export default router;
