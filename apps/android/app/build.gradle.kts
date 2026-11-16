plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Janma Kundali for Android is a thin client: the charts are computed by the
// Python server (Swiss Ephemeris, reportlab, cairo), which does not come to
// the phone. So there is nothing to build here but the shell.
android {
    namespace = "io.github.chinmay28.kundali"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.chinmay28.kundali"
        // Android 10: scoped storage and MediaStore.Downloads, so saving a
        // report needs no storage permission.
        minSdk = 29
        targetSdk = 35
        // Stamped by the release workflow: the release's version as the
        // name, its commit count (which only grows) as the code.
        versionCode = (findProperty("appVersionCode") as String?)?.toInt() ?: 1
        versionName = (findProperty("appVersionName") as String?) ?: "dev"
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Signed with the debug key so the release build sideloads as it
            // stands. Anybody publishing to a store signs it with their own.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    lint {
        disable += setOf(
            // Plain HTTP is how kundali-web runs on a home network, and a
            // private CA is how it runs behind TLS at home: both are the
            // point (see network_security_config.xml).
            "InsecureBaseConfiguration",
            "AcceptsUserCertificates",
            // allowBackup is off; there is nothing for fullBackupContent to say.
            "DataExtractionRules",
            // Versions move on purpose, together, not whenever lint notices.
            "GradleDependency",
        )
    }
}

dependencies {
    implementation(project(":core"))
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.preference:preference-ktx:1.2.1")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("com.google.android.material:material:1.12.0")
}
