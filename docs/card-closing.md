# A card closes what it opened

At turn end the driver joins its lanes and removes every private checkout
registered by those lanes, including a checkout whose creation failed halfway.
Registration precedes creation. Accepted commits already live on the campaign
branch; deleting a private clone removes its other branches and its own records.
There is no shared worktree registration to prune for these clones.

Each command has a small parent that adopts orphaned descendants. When the
command ends, or its driver dies, that parent kills and reaps its own children,
including descendants that detached into new sessions. Ownership comes from
parentage, never names, an old pid file, or a scan of unrelated processes.
The driver retains child handles until closing. Failure to close is an error.
Exit 125 is reserved for startup or ownership failure and is treated as a
harness fault, including when a command itself chooses that exit code.

The next driver attempt starts from a fresh checkout with no saved session or
completed-phase shortcut. Findings and attempt counts remain. Existing checkouts
from earlier runs are neither adopted nor swept. No edits are replayed.

Before each lane opens, available memory must be at least 512 MiB and free disk
at least 1 GiB on both the repository and temporary filesystems. Missing readings
also mean wait. This is an admission floor, not a resource reservation.

The driver must survive to remove checkouts. Killing the whole driver prevents
its turn-end filesystem cleanup; this change does not add a startup sweep.
