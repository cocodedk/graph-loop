# Profile: a Samsung Tizen TV web app

A repository links to this profile when it builds a web app for a Samsung Tizen TV: HTML, CSS and
JavaScript packaged as a signed `.wgt` and run in the TV's built-in web view. The lean loop reads
the first indented line under `## suite_command`, `## build_command` and `## artifact`; the other
sections are for whoever writes a campaign's gates.

## suite_command

    npm run check

The check runs a compatibility lint against the TV's engine, the unit tests, and a Playwright drive
of `index.html` at 1920×1080 that plays the app with synthetic remote keys. The lint rejects known
unsupported features, but desktop tests do not prove the app works on the TV: smoke-test each
release on the oldest TV it serves.

## build_command

    npm run stage

Copies the app's own files, never its tests or tooling, into `dist/app/`. Signing is not part of
the build: it needs the owner's certificates, which never enter a gate box (see on_the_tv).

## artifact

    dist/app/config.xml

The staged folder, which `tizen package` signs; its `config.xml` shows the staging finished.

## paths_the_gate_needs

    $PLAYWRIGHT_BROWSERS_PATH  the Playwright browser builds, read-only
    node_modules               installed once in the main checkout and linked into each worktree
                               with GRAPH_PROVISION_LINK=node_modules, so no gate downloads packages

In `.gitignore`, write `node_modules`, not `node_modules/`. In a worktree it is a link, which git
treats as a file, and a pattern ending in `/` matches only folders. A run whose checkouts would carry
a provisioned path into the diff does not start.

A gate box hides the home directory, and a link does not carry what it points at into the box.
Bind each of these that lives under the home directory by its absolute, expanded path in the
workspace's `gate-paths.json`, such as `{"read_only": ["/opt/cache/ms-playwright",
"/srv/app/node_modules"]}` with your own paths, and export `PLAYWRIGHT_BROWSERS_PATH` to the bound
path before the run. Never bind the Tizen CLI's data directory or any certificate: every gate sees
what that file binds and the box keeps the network, so a test could read the keys and send them
away. For the same reason, keep the certificates and their password files under the home
directory, which the box hides, and run a campaign only where the box works: without it a gate
runs in a plain shell that can read every file.

## machine_is_ready

    node -e "require('playwright').chromium.launch().then(function (b) { return b.close(); })"

Fails when Playwright, its browser build or the libraries the browser needs are missing. The box
hides the real home directory, so anything the check needs from there must be bound; a probe that
passes in your own shell can still fail inside the box.

## the_machine_not_the_card

    Executable doesn't exist at
    Host system is missing dependencies

A gate ending with one of these failed on the machine, not the card. The loop does not know these
lines, so run machine_is_ready before a run, not after rounds are spent.

## red_first

A Playwright drive or a unit test must fail because the behaviour the card requires is missing or
wrong, never because a browser or another dependency is missing.

## house

- The engine is frozen with the TV's firmware: Tizen 6.0 (2021 sets) runs Chromium 76 and Tizen 5.5
  (2020) runs Chromium 69. The lint's ceiling is the oldest TV the app serves. These arrived in
  Chromium 79 to 92, so none is safe on a 2021 or older set: `?.`, `??`, `replaceAll`, `.at()`,
  flex `gap`, `aspect-ratio`, `inset`, `min()`, `max()`, `clamp()`, `:focus-visible`, `:is()`
  and `:where()`.
- Classic `<script>` tags on one shared namespace: no bundler, no framework, no runtime packages.
  A data or logic file ends with a `module.exports` guard so Node tests can load it.
- A fixed 1920×1080 layout. Focus is a class the app moves itself by row and column, never by
  pixel geometry and never with `:focus-visible`. `[hidden]` gets `display: none !important`, and a
  grid declares its rows.
- Input is the arrows, OK (13) and Back (10009), plus any colour key the app registers with
  `tizen.tvinputdevice.registerKey`, which needs the `http://tizen.org/privilege/tv.inputdevice`
  privilege in `config.xml`. Registering the arrows, OK or Back throws, so never do it, and show a
  colour key that failed to register where the person can see it, never only in a catch.
  Back always does something: close a dialog, go back a screen, or ask before exiting.
- Every `tizen` and `webapis` call sits in try/catch, so the same files run in a desktop browser.
- Resume an AudioContext on a key press: Chromium keeps one suspended until the user acts.
- A visible build stamp, bumped on every install, proves the TV is running the new code.

## on_the_tv

Outside any gate, after review. The person turns on the TV's developer mode (Apps, or App
Settings where the TV has it, then 1 2 3 4 5, then this machine's IP address, then restart the
TV). A set that requires it also needs "Permit to install applications" from Tizen Studio's
Device Manager before the first install. `tizen version` and `tizen security-profiles list`
confirm the CLI and the signing profile. Then:

    tizen package -t wgt -s "$TIZEN_PROFILE" -- dist/app
    sdb connect <tv-ip>:26101
    tizen install -n app.wgt -t <device-name> -- dist/app
    tizen run -p <application-id> -t <device-name>

Run them from the checkout the build used. `tizen package` names the `.wgt` after `config.xml`'s
`<name>`, so rename it to `app.wgt` before installing. `-t` takes the name `sdb devices` prints, not
`ip:port`, and the application ID is the one `config.xml` declares, such as `AbCdE12345.MyApp`.
If a retail set rejects the self-signed install, sign with a Samsung certificate that has the
TV's DUID registered.
