package io.github.chinmay28.kundali.core

/**
 * Which page of the web app an intent opens.
 *
 * The web app routes on the hash (`#/new` is the new-chart form), so a
 * launcher shortcut is just a different address on the same origin — no
 * change to the page is needed for it.
 */
object LaunchTarget {
    /** The "New chart" launcher shortcut (res/xml/shortcuts.xml). */
    const val ACTION_NEW_CHART = "io.github.chinmay28.kundali.NEW_CHART"

    /** The path, with its hash route, that [action] opens. */
    fun path(action: String?): String = when (action) {
        ACTION_NEW_CHART -> "/#/new"
        else -> "/"
    }

    /** The full address [action] opens on [origin]. */
    fun url(origin: Origin, action: String?): String = origin.url(path(action))

    /** Whether [action] asks for a particular page rather than "wherever you were". */
    fun isDeepLink(action: String?): Boolean = path(action) != "/"
}
