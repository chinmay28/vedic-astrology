package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Test

class DevFlashTest {
    private fun near(want: Float, got: Float) = assertEquals(want, got, 0.0001f)

    @Test
    fun theVeilFadesInHoldsAndFadesOut() {
        near(0f, DevFlash.veilAlpha(0f))
        near(0.5f, DevFlash.veilAlpha(0.035f))
        near(1f, DevFlash.veilAlpha(0.07f))
        near(1f, DevFlash.veilAlpha(0.5f))
        near(1f, DevFlash.veilAlpha(0.82f))
        near(0.5f, DevFlash.veilAlpha(0.91f))
        near(0f, DevFlash.veilAlpha(1f))
    }

    @Test
    fun theBadgeOvershootsThenDriftsOut() {
        near(0.82f, DevFlash.badgeScale(0f))
        near(1.02f, DevFlash.badgeScale(0.14f))
        near(1f, DevFlash.badgeScale(0.22f))
        near(1f, DevFlash.badgeScale(0.6f))
        near(1.06f, DevFlash.badgeScale(1f))
    }

    @Test
    fun outOfRangeIsClamped() {
        near(0f, DevFlash.veilAlpha(-1f))
        near(1.06f, DevFlash.badgeScale(2f))
    }

    @Test
    fun itLastsThreeSeconds() {
        assertEquals(3000L, DevFlash.DURATION_MS)
    }
}
