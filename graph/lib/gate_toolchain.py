"""Discover home-installed Android tools without sharing the user's Gradle secrets."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def gradle_home() -> Path:
    return Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle"))).expanduser()


def tools() -> dict[str, str]:
    """Resolve aliases before binding: their symlink parents may be masked."""
    found = {}
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
               or str(Path.home() / "Android/Sdk")).expanduser().resolve()
    if sdk.is_dir():
        found.update(ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk))
    configured = ""
    try:
        for line in (gradle_home() / "gradle.properties").read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == "org.gradle.java.home":
                configured = value.strip()
    except (OSError, UnicodeError):
        pass
    compiler = shutil.which("javac")
    candidates = [configured, os.environ.get("JAVA_HOME", "")]
    if compiler:
        candidates.append(str(Path(compiler).resolve().parent.parent))
    for candidate in candidates:
        if candidate:
            jdk = Path(candidate).expanduser().resolve()
            if (jdk / "bin/javac").is_file():
                found["JAVA_HOME"] = str(jdk)
                break
    return found


def environment(home: str) -> dict[str, str]:
    """Only distributions are reused; properties, init scripts and keys stay hidden.

    Copy rather than bind the wrapper cache: Gradle needs writable lock files,
    and a gate must not change the host's distributions. Never follow cache links.
    """
    found = tools()
    if "JAVA_HOME" in found:
        found["PATH"] = found["JAVA_HOME"] + "/bin" + os.pathsep + os.environ.get("PATH", "")
    cache = Path(home) / ".gradle"
    source = gradle_home() / "wrapper/dists"
    if source.is_dir():
        shutil.copytree(source, cache / "wrapper/dists", dirs_exist_ok=True,
                        ignore=lambda directory, names: [
                            name for name in names if (Path(directory) / name).is_symlink()])
    found["GRADLE_USER_HOME"] = str(cache)
    return found
