const { getPool, ensureSchema } = require("./_db");

const EMPTY_REACTIONS = { support: 0, oppose: 0, neutral: 0 };

module.exports = async (req, res) => {
  if (req.method !== "GET") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const permitId = String(req.query.permitId || "").trim();
  const voterId = req.query.voterId ? String(req.query.voterId).trim() : null;
  if (!permitId) {
    res.status(400).json({ error: "permitId is required." });
    return;
  }

  try {
    await ensureSchema();
    const pool = getPool();

    const [commentsResult, reactionCountsResult, myReactionResult] = await Promise.all([
      pool.query(
        "SELECT id, author, text, sentiment, created_at FROM comments WHERE permit_id = $1 ORDER BY created_at ASC",
        [permitId]
      ),
      pool.query(
        "SELECT reaction, COUNT(*)::int AS count FROM reactions WHERE permit_id = $1 GROUP BY reaction",
        [permitId]
      ),
      voterId
        ? pool.query(
            "SELECT reaction FROM reactions WHERE permit_id = $1 AND voter_id = $2",
            [permitId, voterId]
          )
        : Promise.resolve({ rows: [] }),
    ]);

    const reactions = { ...EMPTY_REACTIONS };
    for (const row of reactionCountsResult.rows) {
      reactions[row.reaction] = row.count;
    }

    res.status(200).json({
      comments: commentsResult.rows,
      reactions,
      myReaction: myReactionResult.rows[0]?.reaction || null,
    });
  } catch (err) {
    console.error("Failed to load permit activity:", err);
    res.status(500).json({ error: "Something went wrong loading comments and reactions." });
  }
};
