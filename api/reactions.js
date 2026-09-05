const { getPool, ensureSchema } = require("./_db");

const VALID_REACTIONS = new Set(["support", "oppose", "neutral"]);
const EMPTY_REACTIONS = { support: 0, oppose: 0, neutral: 0 };

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const body = req.body || {};
  const permitId = String(body.permitId || "").trim();
  const voterId = String(body.voterId || "").trim();
  const reaction = body.reaction;

  if (!permitId) {
    res.status(400).json({ error: "permitId is required." });
    return;
  }
  if (!voterId) {
    res.status(400).json({ error: "voterId is required." });
    return;
  }
  if (!VALID_REACTIONS.has(reaction)) {
    res.status(400).json({ error: "reaction must be one of support, oppose, neutral." });
    return;
  }

  try {
    await ensureSchema();
    const pool = getPool();

    await pool.query(
      `INSERT INTO reactions (permit_id, voter_id, reaction, updated_at)
       VALUES ($1, $2, $3, now())
       ON CONFLICT (permit_id, voter_id) DO UPDATE SET
         reaction = EXCLUDED.reaction,
         updated_at = now()`,
      [permitId, voterId, reaction]
    );

    const countsResult = await pool.query(
      "SELECT reaction, COUNT(*)::int AS count FROM reactions WHERE permit_id = $1 GROUP BY reaction",
      [permitId]
    );
    const reactions = { ...EMPTY_REACTIONS };
    for (const row of countsResult.rows) {
      reactions[row.reaction] = row.count;
    }

    res.status(200).json({ reactions, myReaction: reaction });
  } catch (err) {
    console.error("Failed to save reaction:", err);
    res.status(500).json({ error: "Something went wrong saving your vote. Please try again." });
  }
};
