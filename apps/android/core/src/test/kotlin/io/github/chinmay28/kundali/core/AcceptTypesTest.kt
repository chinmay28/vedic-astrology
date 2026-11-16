package io.github.chinmay28.kundali.core

import org.junit.Assert.assertEquals
import org.junit.Test

class AcceptTypesTest {
    private val known = mapOf("json" to "application/json", "pdf" to "application/pdf", "jpg" to "image/jpeg")
    private fun types(vararg accept: String) = AcceptTypes.mimeTypes(accept.toList()) { known[it] }

    @Test
    fun nothingMeansAnything() {
        assertEquals(emptyList<String>(), types())
        assertEquals(emptyList<String>(), types(""))
        assertEquals(emptyList<String>(), types("*/*"))
    }

    @Test
    fun typesPassThroughAndExtensionsAreLookedUp() {
        assertEquals(listOf("image/*"), types("image/*"))
        assertEquals(listOf("application/pdf", "image/jpeg"), types(".PDF, .jpg"))
        // The Data screen's restore picker.
        assertEquals(listOf("application/json"), types("application/json,.json"))
    }

    @Test
    fun anExtensionWithNoTypeWidensToAnything() {
        assertEquals(emptyList<String>(), types(".json,.kundali"))
        assertEquals(emptyList<String>(), types("not a type"))
    }
}
