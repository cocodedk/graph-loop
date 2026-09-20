# Grilling stage — decisions the RFC left open

Status: **confirmed by the owner, 2026-09-20 — revision 3.** Specifications are written from
this revision and name the decisions they implement. A change to any decision here needs a
new revision, a new confirmation, and a review of what was built from the old one. A
decisions model's confidence never authorised any of these; the owner's confirmation did.

`grilling-stage.md` beside this file is the brief, kept as written. Planning it surfaced
points where two competent builders could have built different behaviour. Each was found
by an independent reviewer refusing a specification that had filled the gap with a rule of
its own, or by a reader of the specifications. They carry stable identifiers so that
specifications can name the decisions they implement. Revision 2 corrected D1, D3 and D5
after review and added D6 and the retained task T1. Revision 3 tightens D1, D3 and D6.

## D1 — Rules first, then the recorded order; the chooser only where judgment is needed

*The gap:* sections 5 and 10 speak of "the question whose answer would change the most
downstream work" and never say how that is determined.

*Decision:* selection has three steps, in this order.

1. **A deterministic follow-up rule decides, when one applies** — a picked choice or a
   classified answer whose prepared follow-up names it. No model is called **for question
   selection**; interpreting the answer that triggered the rule may still have needed a
   request, which D6 counts on its own. Switching the chooser on never overrides such a
   rule.
2. **Otherwise the recorded asking order is the default.** The opening analysis records an
   explicit order with a stated reason for each question's position; among the eligible
   questions the interview asks the earliest. No counting rule stands in for that judgment.
3. **The chooser is called only when selection requires judgment and its switch is on**:
   no rule applies and more than one question is eligible. It is given section 10's four
   criteria and the recorded order with its reasons, and returns one eligible identifier
   or reports the prepared set insufficient. An insufficient set goes to the text model to
   update the analysis. An invalid or unavailable chooser falls back to step 2, which is the
   text model's own earlier judgment, and the fallback is recorded.

## D2 — A person switches a category on, looking at what the report exposes

*The gap:* section 14 enables routing "only for the categories that demonstrate acceptable
results" and defines neither *acceptable* nor who judges it.

*Decision:* letting the application **act** on the decisions model's result is a recorded
decision by a person that names the evaluation report it rests on. No threshold is built
in. The report exposes, per category: how many reviewed examples it holds, how many of the
model's results disagreed with the reviewed decision and which, and how many examples carry
no annotation. The tool refuses to switch on acting for a category whose named report holds
no reviewed example of it — which proves only that the report is not empty, never that the
category is reliable; reliability is the person's judgment of the numbers exposed.

## D3 — Three states, so that evidence can exist before anything acts on it

*The gap:* section 14 enables routing per category, but section 6's category of an answer
is known only after the model has classified it; and if classifying at all needed an
evaluation report, no report could ever be made.

*Decision:* the decisions model's part in an interview is in one of three states, set
separately for interpreting answers and for choosing the next question.

- **off** — it is not called.
- **observe** — it is called and its result is recorded beside the text model's
  interpretation or beside the question actually asked, and **nothing acts on it**: the
  turn runs exactly as when off. Switching observe on is a person's recorded decision,
  because it sends the interview's content to the decisions service and costs calls, but it
  needs no evaluation report. This is how evidence is gathered from live interviews.
- **act** — per kind of answer, and for the chooser, under D2.

A classification of a kind that is not switched to *act* — because the state is *observe*,
or because *act* is on for other kinds only — goes to the text model, and **cannot resolve
the question by itself**: whatever the model returned, the turn is handled as if it had not
classified, and its result stays a record for comparison.

Evidence for a report therefore comes from two places that need no *act* switch: replaying
recorded interviews, and the records observe mode leaves. Either becomes a *reviewed
example* when a reviewer has annotated it. Everything starts off.

## D4 — What needs a person's verdict is never reported as zero

*The gap:* five of section 14's measures cannot be computed from a transcript, and one
needs a baseline to mean anything.

*Decision:* waiting time per answer, total model cost and a resolved question asked again
are computed from the record alone. Unnecessary questions, questions incorrectly marked
answered, contradictions missed, decisions lost or altered in the brief, and gaps found by
the final reviewer are computed only from reviewer annotations in a defined format; without
an annotation the measure is reported as *not annotated*, never as zero. Text-model calls
avoided is reported only against a text-model-only run of the same interview; without one
it is reported as *no baseline*.

## D5 — The brief is checked against current resolved decisions

*The gap:* section 12's reviewer looks for "omitted answers", while section 11 puts
"revisions and superseded decisions" in the session history. Read literally, a brief that
correctly leaves out a revised answer would be refused, and one that states the old answer
would pass.

*Decision:* a **decision** is a question the user has *resolved*: by an answer that answers
it, by a bounded delegation, or by an exclusion from scope. A reply is not a decision
merely by being the latest: a reply that answers only part, is unclear, or may contradict
an earlier decision is recorded word for word and leaves its question **pending**. Any
decision — an answer, a delegation or an exclusion alike — can be **superseded** by a later
resolved decision on the same question; the superseded one stays in the session history
word for word, naming what superseded it, and is never current. The fidelity checks compare
the brief with the *current resolved decisions*: one the brief lacks is an omission, one it
changes is an alteration, and a decision in the brief that only a pending reply or a
superseded decision supports is unsupported. A pending question makes the brief not ready.

## D6 — Calls are counted by purpose

*The gap:* section 7 requires routine turns to avoid text-model calls; a refused
specification turned that into "no model calls in the turn", which contradicts interpreting
a free-text answer at all.

*Decision:* three counts are kept apart for every turn: text-model calls, decisions-model
requests for **interpreting the answer**, and decisions-model requests for **choosing the
next question**. "No selection call" — a rule or the recorded order chose — says nothing
about the other two. A routine turn is one with **zero text-model calls**; it may hold one
interpretation request, in which independent checks about that answer share the request,
and separately at most one selection request. A check that depends on an earlier result
**may** need a further request; it is made after the result it depends on and counted under
its own purpose, so a turn can hold more than one interpretation request and still be
routine as long as no text model is called. **Every request actually made is counted** —
a retry, a request that failed, timed out or came back invalid included — each with its
purpose, its outcome and its timing, so the counts are what was spent, not what succeeded.

## T1 — Retained task: the planning layer keeps no log of its reviewers

Observed while planning this brief. The branch writer records nothing: it has no campaign
directory. The spec writer records its own prompts and answers, and of its independent
reviewer only one line on standard output when it refuses. No reviewer prompt, no reviewer
reply, no timing, no failure, no cost — for the layer where, in this planning run, six of
eleven specification submissions were refused. The loop's own rule is that everything it says, hears
and measures is written to an append-only log. Task: the branch writer and the spec writer
record, per call and for writer and reviewer alike, the prompt, the reply, the timing, any
failure, and the cost where it is available, in the campaign's log.
