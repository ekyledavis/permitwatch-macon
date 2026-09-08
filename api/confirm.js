const { getPool, ensureSchema } = require("./_db");

// GET /api/confirm?token=... — the link a subscriber clicks in their
// confirmation email. Not JSON: it's opened directly in a browser, so it
// renders a small HTML page either way.
module.exports = async (req, res) => {
  if (req.method !== "GET") {
    res.status(405).send("Method not allowed");
    return;
  }

  const token = String(req.query.token || "").trim();
  res.setHeader("Content-Type", "text/html; charset=utf-8");

  if (!token) {
    res.status(400).send(page("⚠️ Missing confirmation link", "Please use the link from your confirmation email."));
    return;
  }

  try {
    await ensureSchema();
    const { rows } = await getPool().query(
      `UPDATE subscribers
         SET verified_at = now(), confirm_token = NULL, confirm_token_expires_at = NULL
       WHERE confirm_token = $1 AND confirm_token_expires_at > now()
       RETURNING email`,
      [token]
    );

    if (rows.length === 0) {
      res.status(400).send(page(
        "⚠️ Link invalid or expired",
        "This confirmation link is no longer valid. Please subscribe again from PermitWatch to get a fresh one."
      ));
      return;
    }

    res.status(200).send(page(
      "✅ You're confirmed!",
      `${rows[0].email} will now receive PermitWatch alerts.`
    ));
  } catch (err) {
    console.error("Failed to confirm subscriber:", err);
    res.status(500).send(page("⚠️ Something went wrong", "Please try again in a moment."));
  }
};

function page(heading, message) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PermitWatch</title>
</head>
<body style="font-family:-apple-system,'DM Sans',sans-serif;max-width:480px;margin:64px auto;padding:0 20px;text-align:center;color:#1a1a1a;">
  <h1 style="font-size:22px;">${heading}</h1>
  <p style="color:#555;font-size:15px;line-height:1.5;">${message}</p>
  <p style="margin-top:24px;"><a href="/" style="color:#4F6BFF;">Back to PermitWatch</a></p>
</body>
</html>`;
}
