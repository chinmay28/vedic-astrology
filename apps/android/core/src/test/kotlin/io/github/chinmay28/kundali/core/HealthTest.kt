package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HealthTest {
    @Test
    fun readsTheVersion() {
        assertEquals(
            "2026.11.31",
            Health.version("""{"ok": true, "version": "2026.11.31", "db": "/data/kundali.sqlite", "charts": 3}"""),
        )
        assertEquals("unknown", Health.version("""{"ok":true}"""))
    }

    @Test
    fun anythingElseIsNotAKundaliServer() {
        assertNull(Health.version("""{"ok":false,"version":"2026.11.31"}"""))
        assertNull(Health.version("""{"status":"ok","version":"v2026.11.240"}"""))
        assertNull(Health.version("<html>nginx</html>"))
        assertNull(Health.version(""))
    }
}
