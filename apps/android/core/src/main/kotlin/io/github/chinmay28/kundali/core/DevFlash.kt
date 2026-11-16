package io.github.chinmay28.kundali.core

/**
 * The developer badge thrown up full screen, on one 3-second clock — the same
 * keyframes as the web app's `.dev-flash` (and SandHarbor's `sand-dev-veil` /
 * `sand-dev-badge`): the veil fades in, holds and fades out; the lockup lands
 * with a small overshoot and drifts out as the veil clears.
 *
 * Pure numbers, so the app's animator only asks "how far along are we" and
 * the shape of the animation is tested here.
 */
object DevFlash {
    const val DURATION_MS = 3000L

    /** The handle printed under the badge. */
    const val HANDLE = "github.com/chinmay28"

    private val veil = listOf(0f to 0f, 0.07f to 1f, 0.82f to 1f, 1f to 0f)
    private val badge = listOf(0f to 0.82f, 0.14f to 1.02f, 0.22f to 1f, 0.82f to 1f, 1f to 1.06f)

    /** The veil's opacity at [fraction] (0–1) of the way through. */
    fun veilAlpha(fraction: Float): Float = at(veil, fraction)

    /** The lockup's scale at [fraction] (0–1) of the way through. */
    fun badgeScale(fraction: Float): Float = at(badge, fraction)

    private fun at(keys: List<Pair<Float, Float>>, fraction: Float): Float {
        val f = fraction.coerceIn(0f, 1f)
        for (i in 1 until keys.size) {
            val (t0, v0) = keys[i - 1]
            val (t1, v1) = keys[i]
            if (f <= t1) return v0 + (v1 - v0) * ((f - t0) / (t1 - t0))
        }
        return keys.last().second
    }
}
