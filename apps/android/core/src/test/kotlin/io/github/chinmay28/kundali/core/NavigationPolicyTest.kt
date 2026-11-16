package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Test

class NavigationPolicyTest {
    private val app = Origin("http", "192.168.1.20", 8777)

    private fun check(url: String, want: Navigation) = assertEquals(url, want, NavigationPolicy.decide(app, url))

    @Test
    fun theServersOwnPagesStayInTheApp() {
        check("http://192.168.1.20:8777/", Navigation.IN_APP)
        check("http://192.168.1.20:8777/api/charts/3/report.pdf", Navigation.IN_APP)
        check("blob:http://192.168.1.20:8777/0b1c", Navigation.IN_APP)
        check("data:image/png;base64,AAAA", Navigation.IN_APP)
        check("about:blank", Navigation.IN_APP)
    }

    @Test
    fun otherSitesGoToThePhone() {
        check("https://github.com/chinmay28", Navigation.EXTERNAL)
        check("http://192.168.1.20:9999/", Navigation.EXTERNAL)
        check("https://192.168.1.20:8777/", Navigation.EXTERNAL)
        check("mailto:someone@example.com", Navigation.EXTERNAL)
        check("tel:+15555550100", Navigation.EXTERNAL)
        check("geo:14.6197,74.8354", Navigation.EXTERNAL)
    }

    @Test
    fun intentUrlsAreTheirOwnCase() {
        check("intent://maps.example#Intent;scheme=https;package=com.google.android.apps.maps;end", Navigation.INTENT)
    }

    @Test
    fun dangerousSchemesAreBlocked() {
        check("javascript:alert(1)", Navigation.BLOCK)
        check("file:///data/data/io.github.chinmay28.kundali/shared_prefs/kundali.xml", Navigation.BLOCK)
        check("content://com.android.contacts/contacts", Navigation.BLOCK)
        check("about:config", Navigation.BLOCK)
        check("weird", Navigation.BLOCK)
        check("", Navigation.BLOCK)
    }
}
