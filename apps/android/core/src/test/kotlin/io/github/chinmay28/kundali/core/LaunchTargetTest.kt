package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LaunchTargetTest {
    private val origin = Origin.parse("pi.local").getOrThrow()

    @Test
    fun theNewChartShortcutOpensTheForm() {
        // app.js routes "#/new" to the new-chart form.
        assertEquals("http://pi.local:8777/#/new", LaunchTarget.url(origin, LaunchTarget.ACTION_NEW_CHART))
        assertTrue(LaunchTarget.isDeepLink(LaunchTarget.ACTION_NEW_CHART))
    }

    @Test
    fun anyOtherLaunchOpensTheChartsList() {
        assertEquals("http://pi.local:8777/", LaunchTarget.url(origin, "android.intent.action.MAIN"))
        assertEquals("/", LaunchTarget.path(null))
        assertFalse(LaunchTarget.isDeepLink("android.intent.action.MAIN"))
    }

    @Test
    fun theTargetIsAlwaysOnTheServersOrigin() {
        assertTrue(origin.contains(LaunchTarget.url(origin, LaunchTarget.ACTION_NEW_CHART)))
    }
}
