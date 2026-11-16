package io.github.chinmay28.kundali

import android.content.Intent
import android.os.Bundle
import android.view.inputmethod.EditorInfo
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.widget.doAfterTextChanged
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import io.github.chinmay28.kundali.core.Health
import io.github.chinmay28.kundali.core.Origin
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * The first screen: where is the Janma Kundali server?
 *
 * The address is checked against `/api/health` before it is kept, so a typo
 * shows up here rather than as a blank page — but a server that is merely
 * off right now can still be saved ("Continue anyway").
 */
class SetupActivity : AppCompatActivity() {
    private lateinit var addressLayout: TextInputLayout
    private lateinit var address: TextInputEditText
    private lateinit var go: MaterialButton

    /** The origin last checked and found not to answer: a second tap keeps it. */
    private var unconfirmed: Origin? = null
    private var checking = false

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.root)) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }

        addressLayout = findViewById(R.id.address_layout)
        address = findViewById(R.id.address)
        go = findViewById(R.id.go)
        findViewById<TextView>(R.id.version).text = getString(R.string.setup_version, BuildConfig.VERSION_NAME)
        findViewById<android.view.View>(R.id.dev_badge).setOnClickListener { DevFlashOverlay.show(this) }

        address.setText(ConfigStore(this).load().serverAddress)
        address.doAfterTextChanged {
            addressLayout.error = null
            unconfirmed = null
            go.setText(R.string.setup_continue)
            refresh()
        }
        address.setOnEditorActionListener { _, action, _ ->
            if (action == EditorInfo.IME_ACTION_GO && go.isEnabled) go.performClick()
            action == EditorInfo.IME_ACTION_GO
        }
        go.setOnClickListener { submit() }
        refresh()
    }

    private fun refresh() {
        go.isEnabled = !checking && !address.text.isNullOrBlank()
    }

    private fun submit() {
        val o = Origin.parse(address.text.toString()).getOrElse {
            addressLayout.error = it.message
            return
        }
        if (o == unconfirmed) {
            keep(o)
            return
        }
        checking = true
        refresh()
        go.setText(R.string.setup_checking)
        thread(name = "kundali-health") {
            val version = probe(o)
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                checking = false
                if (version != null) {
                    keep(o)
                } else {
                    unconfirmed = o
                    addressLayout.error = getString(R.string.setup_not_kundali, o.toString())
                    go.setText(R.string.setup_continue_anyway)
                    refresh()
                }
            }
        }
    }

    private fun probe(o: Origin): String? = try {
        val conn = URL(o.url("/api/health")).openConnection() as HttpURLConnection
        conn.connectTimeout = 4_000
        conn.readTimeout = 4_000
        try {
            if (conn.responseCode == 200) Health.version(conn.inputStream.bufferedReader().use { it.readText() }) else null
        } finally {
            conn.disconnect()
        }
    } catch (_: Exception) {
        null
    }

    private fun keep(o: Origin) {
        val store = ConfigStore(this)
        // Stored the way it will be read back: the origin, spelled out.
        store.save(store.load().copy(serverAddress = o.toString()))
        startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
        finish()
    }
}
