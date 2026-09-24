# Paths a campaign keeps visible

Put `gate-paths.json` in the campaign workspace before running its gates:

```json
{
  "read_only": ["/opt/shared-assets", "/srv/gate-inputs"],
  "cache": "/srv/campaign-cache"
}
```

Use absolute paths. Create the paths and the cache directory beforehand.
The box binds each path at the same location after its masks: declared inputs
are read-only and the single cache directory is writable. Other masked paths
stay hidden. Declare only the access this campaign needs; a declared directory
exposes its contents. Gates refer to the cache by its declared path.

The loop neither inspects the contents nor finds or copies dependencies.
Missing paths cause the box to refuse the gate. An absent or empty declaration
leaves existing behavior unchanged. Live gates and hosts without a working box
retain their existing behavior; these bindings apply only inside the box.
