# Supervised self-repair

The driver implements these changes through atomic cards and independent
contract and diff reviews; its supervisor prepares failing gates and observes
the run, without implementing the production fixes.

- A rename publishes both its addition and its source deletion.
- File scope checks both rename endpoints independently.
- Planning preserves every human-held card while still retrying unheld
  infrastructure failures once.
- Planning and building share one exclusive campaign lock; an overlapping
  command refuses before it writes planning events or changes cards.
- Finished cards stay finished, even when a later integration check finds an
  old gate defect; that defect parks the unfinished work for a new decision.
  Startup traverses settled ancestors and starts only the first runnable
  unfinished card on each independent branch, respecting dependencies,
  human holds, running claims, file overlap and the lane ceiling.
- Unattended Claude calls use a supported permission mode and preserve their
  existing allowed and denied tools.
- Accepted commits use Conventional Commits subjects and retain the card ID.
- A Jev decision selects a configured model and effort for a card: choices
  come from the available resource catalogue, never free-form model names.
  Start a build at medium; higher effort requires a failed medium build. Reviews
  run at xhigh.
  Route builders and reviewers independently and never let the builder grade
  its own change. Reject malformed or unsupported choices, record the actual
  model, effort and fallback reason, and keep working through a deterministic
  fallback if the decision service is unavailable.

The router must be exercised at the real call sites, not merely exposed as an
unused helper, and its transport must have deterministic tests that spend no
external account; a live probe separately establishes service availability.
