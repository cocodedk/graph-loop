# Card model and effort routing

One decision chooses one executable profile from the configured resource belt;
model names and effort values returned as free text never become authority.
Jev's typed choice contains the configured agent, account, model and effort.
The selection descriptions must name those fields so the decision can compare
what is offered; the decision question explicitly asks for a model and effort,
while the existing triage question stays a failure diagnosis. Do not hard-code current prices or assume an unavailable
model can run. The existing resource belt still handles account and model
refusals without repeating paid work.

The small public interface is `model_router.choose(task, job, space=None,
builder_model="")`, with optional arguments passed by keyword; its result
exposes `resource`, `effort`, `source` (`jev` or `fallback`) and `why`.
Use the existing Jev transport, preserving triage's request and answer behavior.
Confidence must be a finite number in range, not a boolean; low confidence,
invalid choices, malformed answers and unavailable transport select the first
eligible configured resource at medium effort, with an explicit reason.

All first execution attempts use medium effort. A retry counter alone is not
proof that medium failed. Higher effort becomes eligible only after the
campaign records a medium build for this contract followed by a failed work
gate; an outage or a different card's failure is insufficient. The route record
binds the choice to `contract_digest(task)`. Review candidates exclude the
builder's model, including fallback (configured names are model identities).
No eligible independent reviewer means no accepted review, never self-review: `choose` raises `LookupError`, and
the call site returns an unavailable review without invoking any provider.

Record each decision as a `routed` event with task, purpose, agent, model,
effort, source, reason and contract digest, plus the provider's measured cost
when supplied. The actual builder and independent reviewer calls must use the
chosen model and effort. Preserve the existing attempt accounting and provider
fallbacks. Completed cards are not routed or launched again.

`graph/tests/test_campaign_router_policy.py` tests choice validation and
fallback; `graph/tests/test_campaign_router_calls.py` drives the actual call
sites, with a deterministic Decisions API stand-in so the gates spend nothing.
A live probe of the existing transport has separately returned a typed model
profile successfully; deterministic tests remain the acceptance verdict.

`GRAPH_ROUTER=off` provides an explicit offline mode using the same eligible
medium fallback; the default is Jev routing. Test process fixtures select
offline mode, and the router gates explicitly enable their mocked transport,
so running either repository suite never contacts the decision service.

The build list starts with `gpt-6-astra`; `gpt-*` builders use Codex once per
model, and other names use Claude on its configured accounts. Codex builds
use `workspace-write` rooted at the card worktree, with no extra writable
roots, temporary-directory access, network access or approval escalation.
Reviews remain read-only. Planning and guarded live builds retain their
Claude tool restrictions. The router still chooses among eligible builders.
