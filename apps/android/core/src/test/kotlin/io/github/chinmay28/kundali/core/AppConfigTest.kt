package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppConfigTest {
    @Test
    fun nothingIsConfiguredUntilThereIsAnAddress() {
        assertFalse(AppConfig().configured)
        assertFalse(AppConfig(serverAddress = "  ").configured)
        assertTrue(AppConfig().origin().isFailure)
    }

    @Test
    fun theOriginIsTheParsedAddress() {
        val c = AppConfig(serverAddress = "pi.local")
        assertTrue(c.configured)
        assertEquals("http://pi.local:8777", c.origin().getOrThrow().toString())
    }

    @Test
    fun aBadAddressHasAReason() {
        val failure = AppConfig(serverAddress = "ftp://pi.local").origin().exceptionOrNull()
        assertTrue(failure!!.message!!.isNotBlank())
    }

    @Test
    fun reportsOpenByDefault() {
        assertTrue(AppConfig().openReports)
    }
}
