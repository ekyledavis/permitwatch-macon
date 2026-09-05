const { getPool, ensureSchema } = require("./_db");

const VALID_SENTIMENTS = new Set(["support", "oppose", "neutral"]);
const MAX_TEXT_LENGTH = 2000;
const MAX_AUTHOR_LENGTH = 60;

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const body = req.body || {};
  const permitId = String(body.permitId || "").trim();
  const text = String(body.text || "").trim();
  const author = String(body.author || "").trim().slice(0, MAX_AUTHOR_LENGTH) || "Neighbor";
  const sentiment = VALID_SENTIMENTS.has(body.sentiment) ? body.sentiment : "neutral";

  if (!permitId) {
    res.status(400).json({ error: "permitId is required." });
    return;
  }
  if (!text) {
    res.status(400).json({ error: "Comment text can't be empty." });
    return;
  }
  if (text.length > MAX_TEXT_LENGTH) {
    res.status(400).json({ error: `Comments are limited to ${MAX_TEXT_LENGTH} characters.` });
    return;
  }

  try {
    await ensureSchema();
    const result = await getPool().query(
      `INSERT INTO comments (permit_id, author, text, sentiment)
       VALUES ($1, $2, $3, $4)
       RETURNING id, author, text, sentiment, created_at`,
      [permitId, author, text, sentiment]
    );
    res.status(200).json(result.rows[0]);
  } catch (err) {
    console.error("Failed to save comment:", err);
    res.status(500).json({ error: "Something went wrong posting your comment. Please try again." });
  }
};
