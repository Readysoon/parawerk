import java.util.Properties

// Schlüssel zum Signieren für Google Play (android/key.properties, nicht im Git; anlegen mit mobile/android.sh)
val schluessel = Properties().apply {
    val datei = rootProject.file("key.properties")
    if (datei.exists()) datei.inputStream().use { load(it) }
}

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "at.parawerk.parawerk"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "at.parawerk.parawerk"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (schluessel.containsKey("storeFile")) {
            create("release") {
                storeFile = file(schluessel.getProperty("storeFile"))
                storePassword = schluessel.getProperty("storePassword")
                keyAlias = schluessel.getProperty("keyAlias")
                keyPassword = schluessel.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // Mit eigenem Schlüssel, wenn key.properties da ist; sonst Test-Schlüssel (geht nicht in Google Play)
            signingConfig = if (schluessel.containsKey("storeFile")) signingConfigs.getByName("release")
                            else signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
