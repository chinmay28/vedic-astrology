package io.github.chinmay28.kundali.core

/**
 * Everything the person chose in the app's settings.
 *
 * The app is a thin client only: Janma Kundali's charts are computed by the
 * Swiss Ephemeris under CPython, with reportlab and cairo drawing the
 * reports, and none of that is worth carrying onto a phone. So the one thing
 * the app needs to know is where the server is.
 */
data class AppConfig(
    /** The server, as typed; [Origin.parse] reads it. Blank until set up. */
    val serverAddress: String = "",

    /**
     * Open a PDF or HTML report in the phone's viewer as soon as it is
     * saved, rather than only saying where it went.
     */
    val openReports: Boolean = true,
) {
    val configured: Boolean get() = serverAddress.isNotBlank()

    /** The origin the web view opens, or a reason it has none. */
    fun origin(): Result<Origin> =
        if (configured) Origin.parse(serverAddress) else Result.failure(IllegalStateException("Enter your server's address first."))
}
