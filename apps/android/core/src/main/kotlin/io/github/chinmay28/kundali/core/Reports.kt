package io.github.chinmay28.kundali.core

import java.util.Locale

/**
 * What a file the page saved is, and what the app does once it is in
 * Downloads.
 *
 * On a phone a report is downloaded to be read: the PDF report and the
 * single-file HTML report are opened in the phone's own viewer as soon as
 * they land (unless the person turned that off). Backups and CSVs are not
 * documents to read on the spot, so they are only saved.
 */
object Reports {
    enum class Kind(val mime: String) {
        PDF("application/pdf"),
        HTML("text/html"),
    }

    /** A report the phone can show, judged by type first and name second; null for anything else. */
    fun kindOf(name: String, mime: String?): Kind? {
        val type = mime?.substringBefore(';')?.trim()?.lowercase(Locale.ROOT).orEmpty()
        Kind.entries.firstOrNull { it.mime == type }?.let { return it }
        if (type.isNotEmpty() && type != "application/octet-stream") return null
        return when (name.substringAfterLast('.', "").lowercase(Locale.ROOT)) {
            "pdf" -> Kind.PDF
            "html", "htm" -> Kind.HTML
            else -> null
        }
    }

    /** Whether to open [name] in a viewer right after saving it. */
    fun openAfterSaving(name: String, mime: String?, config: AppConfig): Boolean =
        config.openReports && kindOf(name, mime) != null
}
