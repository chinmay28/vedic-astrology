package io.github.chinmay28.kundali

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import io.github.chinmay28.kundali.core.AppConfig
import io.github.chinmay28.kundali.core.Reports

/**
 * What happens once a file is in Downloads: a report opens in the phone's
 * own viewer (a PDF reader, the browser for the HTML report); anything else,
 * or a report when the person turned that off, is only announced.
 * [Reports] makes the decision; this is the Android half.
 */
object Viewer {
    fun afterSaving(activity: Activity, saved: SavedFile, config: AppConfig) {
        val kind = Reports.kindOf(saved.name, saved.mime)
        if (kind == null || !Reports.openAfterSaving(saved.name, saved.mime, config)) {
            Downloads.toast(activity, activity.getString(R.string.saved_to_downloads, saved.name))
            return
        }
        activity.runOnUiThread {
            val view = Intent(Intent.ACTION_VIEW)
                .setDataAndType(saved.uri, kind.mime)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            try {
                activity.startActivity(view)
                Downloads.toast(activity, activity.getString(R.string.saved_to_downloads, saved.name))
            } catch (_: ActivityNotFoundException) {
                Downloads.toast(activity, activity.getString(R.string.no_viewer, saved.name))
            }
        }
    }
}
