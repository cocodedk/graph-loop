# Profile: android-gradle

A campaign links to this profile when it builds an Android app with Gradle. The loop carries the
file; it reads the fields, it does not know what they mean.

## proof_command

    ./gradlew testDebugUnitTest --tests '<class>'

Never `-q`: at quiet level the console carries no per-test failure text.

## report

    app/build/test-results/testDebugUnitTest/TEST-<class>.xml

The failing test names and their exception types live here, not in the console.

## paths_the_gate_needs

    $ANDROID_HOME          the SDK, wherever the machine keeps it
    $GRADLE_USER_HOME      a writable cache directory, outside any masked home
    $ANDROID_USER_HOME     a writable directory holding a copy of the debug.keystore the owner's
                           own builds sign with (by default ~/.android/; match fingerprints with
                           `apksigner verify --print-certs`): without it the build signs with a
                           throwaway key, and its APK cannot update the installed app. This hands
                           the build's code that debug key; a dedicated per-project debug key
                           avoids it, at the cost of one reinstall (which clears the app's data)

A gate box that hides the user's home hides both. The SDK is read-only; the cache must be writable
and should survive between gates, or every gate downloads the toolchain again.

## machine_is_ready

    ./gradlew --version

Fails when the JDK is a JRE, when the SDK is unreachable, or when the wrapper cannot download.

## the_machine_not_the_card

    SDK location not found
    does not provide the required capabilities
    Daemon startup failed
    Could not start ... daemon
    Unable to locate a Java Runtime
    Cannot allocate memory

A gate ending with one of these is the machine's fault. The card keeps its status and its rounds.

## after_a_gate

The build leaves a daemon alive per gate, and each holds a gigabyte or more. They must be closed
with the gate that started them, or the machine runs out of memory and the next card is blamed.

## red_first

A judge is red when every case in the report fails with `NotImplementedError` from a `TODO()` body.
Count the failures in the XML, not in the console.

## house

The JDK is not pinned in the repository, no toolchain resolver is declared, the manifest gains no
permission, and release keeps R8 and resource shrinking on — an F-Droid build must stay reproducible.
