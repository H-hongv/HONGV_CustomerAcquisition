"""Feedback module - re-exports from agents.feedback_agent (Sprint 3 unification).

All feedback functionality is now unified in agents/feedback_agent.py.
This module kept for backward compatibility.
"""

from agents.feedback_agent import FeedbackAgent, DEFAULT_WEIGHTS


# Backward-compat alias
class FeedbackTracker:
    """Backward-compat wrapper. Delegate to FeedbackAgent for email tracking."""

    def __init__(self, db_path=None):
        from agents.feedback_agent import FeedbackAgent
        if db_path:
            import sqlite3
            self._db_path = db_path
            self._conn = sqlite3.connect(db_path)
        self._agent = FeedbackAgent()
        if db_path:
            self._conn.execute("""CREATE TABLE IF NOT EXISTS email_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL, email TEXT NOT NULL, subject TEXT,
                status TEXT NOT NULL DEFAULT 'sent', bounce_reason TEXT,
                reply_received INTEGER DEFAULT 0, reply_text TEXT,
                score_at_send INTEGER, grade_at_send TEXT,
                sent_at REAL NOT NULL, updated_at REAL NOT NULL
            )""")
            self._conn.commit()

    def _use_custom_db(self):
        return hasattr(self, '_db_path')

    def record_send(self, company_name: str, email: str, subject: str = "",
                    score: int = 0, grade: str = ""):
        if self._use_custom_db():
            import time
            now = time.time()
            self._conn.execute(
                "INSERT INTO email_feedback (company_name, email, subject, status, score_at_send, grade_at_send, sent_at, updated_at) VALUES (?, ?, ?, 'sent', ?, ?, ?, ?)",
                (company_name, email, subject, score, grade, now, now)
            )
            self._conn.commit()
        else:
            self._agent.record_email_sent(company_name, email, subject, score, grade)

    def record_bounce(self, email: str, reason: str = ""):
        if self._use_custom_db():
            import time
            now = time.time()
            self._conn.execute(
                "UPDATE email_feedback SET status='bounced', bounce_reason=?, updated_at=? WHERE email=? AND status='sent'",
                (reason, now, email)
            )
            self._conn.commit()
        else:
            self._agent.record_bounce(email, reason)

    def record_reply(self, email: str, reply_text: str = ""):
        if self._use_custom_db():
            import time
            now = time.time()
            self._conn.execute(
                "UPDATE email_feedback SET reply_received=1, reply_text=?, updated_at=? WHERE email=?",
                (reply_text, now, email)
            )
            self._conn.commit()
        else:
            self._agent.record_reply(email, reply_text)

    def close(self):
        if hasattr(self, "_conn"):
            self._conn.close()

    def get_stats(self):
        if self._use_custom_db():
            total = self._conn.execute("SELECT COUNT(*) FROM email_feedback").fetchone()[0]
            bounced = self._conn.execute("SELECT COUNT(*) FROM email_feedback WHERE status='bounced'").fetchone()[0]
            replied = self._conn.execute("SELECT COUNT(*) FROM email_feedback WHERE reply_received=1").fetchone()[0]
            return {
                "total": total, "bounced": bounced, "replied": replied,
                "bounce_rate": round(bounced / max(total, 1), 3),
                "reply_rate": round(replied / max(total, 1), 3),
            }
        return self._agent.get_email_stats()

    def suggest_weight_adjustments(self):
        """Suggest dimension weight adjustments based on reply correlation."""
        stats = self.get_stats()
        suggestions = []
        if stats["bounce_rate"] > 0.3:
            suggestions.append({
                "dimension": "email_quality",
                "current_bias": -0.1,
                "reason": f"Bounce rate {stats['bounce_rate']:.0%} > 30%"
            })
        return suggestions


# Global singletons
feedback_tracker = FeedbackTracker()
