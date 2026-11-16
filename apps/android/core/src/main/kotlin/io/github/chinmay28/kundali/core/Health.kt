package io.github.chinmay28.kundali.core

import org.json.JSONObject

/**
 * Reading `GET /api/health`, which every kundali-web answers:
 * `{"ok": true, "version": "2026.11.31", "charts": 12, ...}`.
 *
 * It is how the setup screen tells a Janma Kundali server from anything else
 * that happens to answer on that address.
 */
object Health {
    /** The server's version when [body] is a healthy answer, else null. */
    fun version(body: String): String? = try {
        val json = JSONObject(body)
        if (json.optBoolean("ok", false)) json.optString("version").ifBlank { "unknown" } else null
    } catch (_: Exception) {
        null
    }
}
