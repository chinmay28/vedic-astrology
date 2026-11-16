package io.github.chinmay28.kundali

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.webkit.CookieManager
import android.webkit.MimeTypeMap
import android.widget.Toast
import io.github.chinmay28.kundali.core.FileNames
import io.github.chinmay28.kundali.core.Origin
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** A file now in Downloads: the name Android gave it, and where it is. */
data class SavedFile(val name: String, val uri: Uri, val mime: String)

/** Putting files into the phone's Downloads, in a "Janma Kundali" folder. */
object Downloads {
    private const val FOLDER = "Janma Kundali"
    private val pool = Executors.newFixedThreadPool(2)

    /**
     * Copies [source] into Downloads as [name] and returns what it became
     * there (Android adds " (1)" to a name already taken). Blocks.
     */
    fun save(context: Context, source: InputStream, name: String, mime: String?): SavedFile {
        val resolver = context.contentResolver
        val safe = FileNames.sanitize(name)
        val type = mimeFor(safe, mime)
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, safe)
            put(MediaStore.Downloads.MIME_TYPE, type)
            put(MediaStore.Downloads.RELATIVE_PATH, "${Environment.DIRECTORY_DOWNLOADS}/$FOLDER")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Downloads refused the file")
        try {
            (resolver.openOutputStream(uri) ?: throw IOException("cannot write to Downloads")).use { out ->
                source.copyTo(out, 256 * 1024)
            }
            resolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            throw e
        }
        val saved = resolver.query(uri, arrayOf(MediaStore.Downloads.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        } ?: safe
        return SavedFile(saved, uri, type)
    }

    private fun mimeFor(name: String, given: String?): String {
        val g = given?.substringBefore(';')?.trim()
        if (!g.isNullOrEmpty() && g != "application/octet-stream") return g
        val ext = name.substringAfterLast('.', "").lowercase()
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "application/octet-stream"
    }

    /**
     * Downloads [url] — on the server's own [origin], never anywhere else —
     * with the web view's cookies, in the background, then hands the result
     * to [done] on a background thread. Redirects are followed only within
     * the origin, so a cookie never leaves it.
     */
    fun fetch(context: Context, origin: Origin, url: String, suggestedName: String?, mime: String? = null, done: (SavedFile) -> Unit) {
        val app = context.applicationContext
        if (!origin.contains(url)) {
            toast(app, app.getString(R.string.save_failed, suggestedName ?: url, "not on the Janma Kundali server"))
            return
        }
        pool.execute {
            var name = FileNames.sanitize(suggestedName)
            try {
                val conn = open(origin, url)
                try {
                    name = FileNames.forDownload(suggestedName, conn.getHeaderField("Content-Disposition"), conn.url.toString())
                    toast(app, app.getString(R.string.downloading, name))
                    done(conn.inputStream.use { save(app, it, name, mime ?: conn.contentType) })
                } finally {
                    conn.disconnect()
                }
            } catch (e: Exception) {
                toast(app, app.getString(R.string.save_failed, name, e.message ?: e.javaClass.simpleName))
            }
        }
    }

    private fun open(origin: Origin, start: String): HttpURLConnection {
        var url = start
        repeat(5) {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.instanceFollowRedirects = false
            conn.connectTimeout = 15_000
            // A full report with several varsha years takes a few seconds.
            conn.readTimeout = 120_000
            CookieManager.getInstance().getCookie(url)?.let { conn.setRequestProperty("Cookie", it) }
            val code = conn.responseCode
            if (code in 300..399) {
                val next = conn.getHeaderField("Location")?.let { URL(URL(url), it).toString() }
                conn.disconnect()
                if (next == null || !origin.contains(next)) throw IOException("the server sent the download elsewhere")
                url = next
                return@repeat
            }
            if (code !in 200..299) {
                conn.disconnect()
                throw IOException("the server answered $code")
            }
            return conn
        }
        throw IOException("too many redirects")
    }

    fun toast(context: Context, text: String) {
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            Toast.makeText(context, text, Toast.LENGTH_LONG).show()
        }
    }
}
