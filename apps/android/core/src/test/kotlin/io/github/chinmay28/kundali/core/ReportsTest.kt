package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReportsTest {
    private val on = AppConfig(serverAddress = "pi.local")
    private val off = on.copy(openReports = false)

    @Test
    fun theTwoReportsAreRecognisedByType() {
        assertEquals(Reports.Kind.PDF, Reports.kindOf("Asha_kundali.pdf", "application/pdf"))
        assertEquals(Reports.Kind.HTML, Reports.kindOf("Asha_kundali.html", "text/html; charset=utf-8"))
        assertEquals(Reports.Kind.PDF, Reports.kindOf("report", "APPLICATION/PDF"))
    }

    @Test
    fun aMissingOrGenericTypeFallsBackToTheName() {
        assertEquals(Reports.Kind.PDF, Reports.kindOf("kundali.pdf", ""))
        assertEquals(Reports.Kind.HTML, Reports.kindOf("kundali.HTM", "application/octet-stream"))
        assertEquals(Reports.Kind.PDF, Reports.kindOf("kundali.pdf", null))
    }

    @Test
    fun backupsAndTablesAreNotReports() {
        assertNull(Reports.kindOf("kundali-charts.json", "application/json"))
        assertNull(Reports.kindOf("positions.csv", "text/csv; charset=utf-8"))
        assertNull(Reports.kindOf("kundali.sqlite", "application/vnd.sqlite3"))
        // A real type wins over a misleading name.
        assertNull(Reports.kindOf("looks-like.pdf", "text/csv"))
    }

    @Test
    fun reportsOpenAfterSavingUnlessTurnedOff() {
        assertTrue(Reports.openAfterSaving("kundali.pdf", "application/pdf", on))
        assertTrue(Reports.openAfterSaving("kundali.html", "text/html", on))
        assertFalse(Reports.openAfterSaving("kundali.pdf", "application/pdf", off))
        assertFalse(Reports.openAfterSaving("dasha.csv", "text/csv", on))
    }
}
