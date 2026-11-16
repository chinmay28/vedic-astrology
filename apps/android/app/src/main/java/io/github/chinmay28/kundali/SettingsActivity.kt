package io.github.chinmay28.kundali

import android.os.Bundle
import android.text.InputType
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.preference.EditTextPreference
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import com.google.android.material.appbar.MaterialToolbar
import io.github.chinmay28.kundali.core.Origin

/**
 * The app's own settings — which server, and what to do with a report once
 * it is saved. Everything about the charts is in the web app itself.
 *
 * Changes are saved as they are made; the main screen picks them up when it
 * comes back, reconnecting if the server changed.
 */
class SettingsActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        setSupportActionBar(findViewById<MaterialToolbar>(R.id.toolbar))
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        // Edge to edge (always, from Android 15): the toolbar's background
        // runs up under the status bar while its contents stay below it, and
        // the list keeps clear of the navigation bar and any cutout.
        val appBar = findViewById<View>(R.id.app_bar)
        val container = findViewById<View>(R.id.settings_container)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.root)) { _, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            appBar.setPadding(bars.left, bars.top, bars.right, 0)
            container.setPadding(bars.left, 0, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }

        if (savedInstanceState == null) {
            supportFragmentManager.beginTransaction().replace(R.id.settings_container, SettingsFragment()).commit()
        }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    class SettingsFragment : PreferenceFragmentCompat() {
        override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
            preferenceManager.sharedPreferencesName = ConfigStore.FILE
            setPreferencesFromResource(R.xml.preferences, rootKey)

            findPreference<EditTextPreference>(ConfigStore.KEY_ADDRESS)!!.apply {
                setOnBindEditTextListener { it.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI }
                setOnPreferenceChangeListener { pref, v ->
                    Origin.parse(v as String).fold(
                        onSuccess = { o ->
                            // Stored the way it will be read back: the origin, spelled out.
                            (pref as EditTextPreference).text = o.toString()
                            false
                        },
                        onFailure = { message(it.message ?: "That is not an address."); false },
                    )
                }
            }
            findPreference<Preference>("version")!!.summary = BuildConfig.VERSION_NAME
            findPreference<Preference>("developer")!!.setOnPreferenceClickListener {
                DevFlashOverlay.show(requireActivity())
                true
            }
        }

        override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
            super.onViewCreated(view, savedInstanceState)
            // The last rows scroll up clear of the navigation bar, rather than
            // the list stopping short of it with a dead band underneath.
            listView.clipToPadding = false
        }

        private fun message(text: String) {
            AlertDialog.Builder(requireContext()).setMessage(text).setPositiveButton(android.R.string.ok, null).show()
        }
    }
}
