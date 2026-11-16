package io.github.chinmay28.kundali

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.os.Message
import android.view.View
import android.view.ViewGroup
import android.webkit.MimeTypeMap
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import io.github.chinmay28.kundali.core.AcceptTypes
import io.github.chinmay28.kundali.core.AppConfig
import io.github.chinmay28.kundali.core.FileNames
import io.github.chinmay28.kundali.core.LaunchTarget
import io.github.chinmay28.kundali.core.Navigation
import io.github.chinmay28.kundali.core.NavigationPolicy
import io.github.chinmay28.kundali.core.Origin

/**
 * The app: Janma Kundali's own web interface, in a web view, from the server
 * the settings name.
 *
 * Everything the web app does in a browser it does here, because it is the
 * same page: saved charts and places, the chart views, the reports, backups
 * and restore. The app supplies what a browser would have and a web view
 * does not — a file picker, Downloads, a viewer for the PDF, the share sheet,
 * a real browser for links that leave the server — and a launcher shortcut
 * straight to the new-chart form.
 */
class MainActivity : AppCompatActivity() {
    private lateinit var store: ConfigStore
    private lateinit var config: AppConfig
    private var origin: Origin? = null

    private lateinit var web: WebView
    private lateinit var statusPanel: View
    private lateinit var statusText: TextView
    private lateinit var statusDetail: TextView
    private lateinit var statusProgress: ProgressBar
    private lateinit var statusButtons: LinearLayout

    private var bridge: PageBridge? = null
    private var loaded = false
    private var pendingFiles: ValueCallback<Array<Uri>>? = null

    private val pickFiles = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val cb = pendingFiles ?: return@registerForActivityResult
        pendingFiles = null
        val data = result.data
        val uris = if (result.resultCode != RESULT_OK || data == null) {
            null
        } else {
            val clip = data.clipData
            if (clip != null && clip.itemCount > 0) Array(clip.itemCount) { clip.getItemAt(it).uri } else data.data?.let { arrayOf(it) }
        }
        cb.onReceiveValue(uris)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        store = ConfigStore(this)
        config = store.load()
        if (!config.configured) {
            startActivity(Intent(this, SetupActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_main)
        web = findViewById(R.id.web)
        statusPanel = findViewById(R.id.status)
        statusText = findViewById(R.id.status_text)
        statusDetail = findViewById(R.id.status_detail)
        statusProgress = findViewById(R.id.status_progress)
        statusButtons = findViewById(R.id.status_buttons)
        findViewById<View>(R.id.retry).setOnClickListener { load(null) }
        findViewById<View>(R.id.settings).setOnClickListener { openSettings() }

        // The page lays itself out for the screen it is given (its app shell
        // is sized to the viewport); the bars and the keyboard are kept out
        // of it here.
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.root)) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (loaded && web.canGoBack()) web.goBack() else finish()
            }
        })

        val o = config.origin().getOrElse {
            showProblem(it.message ?: "The settings name no server.", null, retry = false)
            return
        }
        origin = o
        setUpWebView(o)
        load(intent?.action)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        // The "New chart" shortcut while the app is already open.
        if (origin != null && LaunchTarget.isDeepLink(intent.action)) load(intent.action)
    }

    override fun onResume() {
        super.onResume()
        if (!::config.isInitialized || !config.configured) return
        val now = store.load()
        if (now == config) return
        // Back from settings with something changed.
        val before = config
        config = now
        if (now.origin().getOrNull() != before.origin().getOrNull()) recreate()
    }

    override fun onDestroy() {
        bridge?.close()
        if (::web.isInitialized) {
            (web.parent as? ViewGroup)?.removeView(web)
            web.destroy()
        }
        super.onDestroy()
    }

    // --- the web view ---

    @SuppressLint("SetJavaScriptEnabled")
    private fun setUpWebView(o: Origin) {
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            setSupportMultipleWindows(true)
            javaScriptCanOpenWindowsAutomatically = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            builtInZoomControls = false
            // The page is laid out for the phone (its viewport tag says
            // device-width). Overview mode would instead zoom out to whatever
            // is widest on it — a wide dasha table — and rescale the whole app.
            loadWithOverviewMode = false
            useWideViewPort = true
        }
        web.settings.userAgentString = web.settings.userAgentString + " JanmaKundaliApp/" + BuildConfig.VERSION_NAME

        bridge = PageBridge(this, o, { config }, ::openSettings).also { it.install(web) }

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                route(request.url.toString())

            override fun onPageStarted(view: WebView, url: String, favicon: android.graphics.Bitmap?) {
                bridge?.onPageStarted(view, url)
            }

            override fun onPageFinished(view: WebView, url: String) {
                if (o.contains(url) && statusButtons.visibility != View.VISIBLE) {
                    loaded = true
                    hideStatus()
                }
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (!request.isForMainFrame) return
                loaded = false
                showProblem(getString(R.string.cannot_reach, o.toString()), error.description?.toString(), retry = true)
            }

            @SuppressLint("WebViewClientOnReceivedSslError")
            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
                loaded = false
                showProblem(getString(R.string.bad_certificate, o.toString()), null, retry = true)
            }
        }

        web.webChromeClient = object : WebChromeClient() {
            // The Data screen's restore: a JSON backup from the phone.
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                pendingFiles?.onReceiveValue(null)
                pendingFiles = callback
                val types = AcceptTypes.mimeTypes(params.acceptTypes.orEmpty().toList()) {
                    MimeTypeMap.getSingleton().getMimeTypeFromExtension(it)
                }
                val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = types.singleOrNull() ?: "*/*"
                    if (types.size > 1) putExtra(Intent.EXTRA_MIME_TYPES, types.toTypedArray())
                    if (params.mode == FileChooserParams.MODE_OPEN_MULTIPLE) putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                }
                return try {
                    pickFiles.launch(intent)
                    true
                } catch (_: ActivityNotFoundException) {
                    pendingFiles = null
                    false
                }
            }

            // window.open / target=_blank: the developer's page, the source
            // link. Neither belongs in the app; the address goes to the phone.
            override fun onCreateWindow(view: WebView, isDialog: Boolean, isUserGesture: Boolean, resultMsg: Message): Boolean {
                val catcher = WebView(this@MainActivity)
                catcher.webViewClient = object : WebViewClient() {
                    private var done = false

                    private fun take(v: WebView, url: String) {
                        if (done || url == "about:blank") return
                        done = true
                        v.stopLoading()
                        // A window that opens the server itself is a tab of the app.
                        if (!route(url)) web.loadUrl(url)
                        v.post { v.destroy() }
                    }

                    override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest): Boolean {
                        take(v, request.url.toString())
                        return true
                    }

                    // Some web views load a new window's first address without asking.
                    override fun onPageStarted(v: WebView, url: String, favicon: android.graphics.Bitmap?) = take(v, url)
                }
                (resultMsg.obj as WebView.WebViewTransport).webView = catcher
                resultMsg.sendToTarget()
                return true
            }
        }

        // A plain link to a download on the server (the page itself uses
        // blob: anchors, which the bridge takes; this is the fallback).
        web.setDownloadListener { url, _, contentDisposition, mime, _ ->
            when {
                o.contains(url) -> Downloads.fetch(this, o, url, FileNames.fromContentDisposition(contentDisposition), mime) {
                    Viewer.afterSaving(this, it, config)
                }
                url.startsWith("http") -> openExternally(url)
            }
        }
    }

    /** Opens the page [action] asks for — the new-chart form — or else reloads where it was. */
    private fun load(action: String?) {
        val o = origin ?: return
        if (loaded && LaunchTarget.isDeepLink(action)) {
            // Already showing the page: only its hash route changes, which
            // the page handles itself without a load to wait for.
            web.loadUrl(LaunchTarget.url(o, action))
            return
        }
        showWaiting(getString(R.string.connecting, o.toString()))
        web.visibility = View.VISIBLE
        val current = web.url
        when {
            LaunchTarget.isDeepLink(action) -> web.loadUrl(LaunchTarget.url(o, action))
            current != null && o.contains(current) -> web.reload()
            else -> web.loadUrl(LaunchTarget.url(o, action))
        }
    }

    /** Where a navigation goes; true when the web view must not follow it. */
    private fun route(url: String): Boolean {
        val o = origin ?: return true
        return when (NavigationPolicy.decide(o, url)) {
            Navigation.IN_APP -> false
            Navigation.EXTERNAL -> {
                openExternally(url)
                true
            }
            Navigation.INTENT -> {
                openIntent(url)
                true
            }
            Navigation.BLOCK -> true
        }
    }

    private fun openExternally(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.no_app_for_link, Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * An intent: link. The page may name an app and a type, never a
     * component: only apps that take links from a browser can be reached
     * this way, exactly as from Chrome.
     */
    private fun openIntent(url: String) {
        val intent = try {
            Intent.parseUri(url, Intent.URI_INTENT_SCHEME)
        } catch (_: Exception) {
            return
        }
        intent.component = null
        intent.selector = null
        intent.addCategory(Intent.CATEGORY_BROWSABLE)
        intent.flags = 0
        try {
            startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            val pkg = intent.`package`
            if (pkg != null) openExternally("market://details?id=$pkg") else Toast.makeText(this, R.string.no_app_for_link, Toast.LENGTH_SHORT).show()
        }
    }

    private fun openSettings() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    // --- the panel in front of the page ---

    private fun showWaiting(text: String) {
        statusPanel.visibility = View.VISIBLE
        statusProgress.visibility = View.VISIBLE
        statusText.text = text
        statusDetail.visibility = View.GONE
        statusButtons.visibility = View.GONE
    }

    private fun showProblem(text: String, detail: String?, retry: Boolean) {
        statusPanel.visibility = View.VISIBLE
        statusProgress.visibility = View.GONE
        statusText.text = text
        statusDetail.text = detail.orEmpty()
        statusDetail.visibility = if (detail.isNullOrBlank()) View.GONE else View.VISIBLE
        statusButtons.visibility = View.VISIBLE
        findViewById<View>(R.id.retry).visibility = if (retry) View.VISIBLE else View.GONE
        if (::web.isInitialized) web.visibility = View.INVISIBLE
    }

    private fun hideStatus() {
        statusPanel.visibility = View.GONE
        web.visibility = View.VISIBLE
    }
}
