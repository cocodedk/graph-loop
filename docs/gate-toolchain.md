# Home-installed gate toolchains

Confined gates discover the Android SDK from `ANDROID_HOME`, then
`ANDROID_SDK_ROOT`, then `~/Android/Sdk`. They discover a compiler-bearing JDK
from `org.gradle.java.home` in the host Gradle properties, then `JAVA_HOME`,
then `javac` on `PATH`. The Gradle setting uses `org.gradle.java.home=PATH`;
other user properties are never copied. Resolved SDK and JDK directories are
restored read-only after the home mask, with corresponding environment values
and the selected JDK first on `PATH`.

`GRADLE_USER_HOME` inside the gate always names its private writable home.
Only `wrapper/dists` from the host Gradle user home (default `~/.gradle`) is
copied there, so an already downloaded distribution can be reused without
sharing writable host state. Symlinks inside that cache are omitted. User
properties, init scripts, dependency caches and credentials are not copied.
The private copy is removed with the gate home; large distributions cost local
copy time and disk space. Missing distributions still download normally.

This discovers an installed toolchain; it does not install an absent SDK or JDK.
LIVE gates retain their existing host environment. On machines without a working
sandbox, the same environment setup applies, but filesystem isolation remains
unavailable as reported by the loop.
