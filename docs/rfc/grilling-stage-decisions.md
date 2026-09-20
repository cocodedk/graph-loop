# Grilling stage — decisions the RFC left open

Status: **proposed — not confirmed.** Nothing may be sliced or built from these until the
owner confirms this revision. A decisions model's confidence does not authorise a decision,
and "overturn them or they stand" is not a confirmation.

`grilling-stage.md` beside this file is the brief, kept as written. Planning it surfaced
five points where two competent builders could have built different behaviour. Each was
found by an independent reviewer refusing a specification that had filled the gap with a
rule of its own. They are recorded here with stable identifiers so that specifications can
name the decisions they implement.

## D1 — The asking order is a recorded default; the chooser keeps its path

*The gap:* sections 5 and 10 speak of "the question whose answer would change the most
downstream work" and never say how that is determined.

*Decision:* the opening analysis records an explicit asking order, with a stated reason for
each question's position. That order is the **default**: among the eligible questions the
interview asks the earliest. It does not replace section 10: when the switch for choosing
the next question is on, the decisions model chooses among the eligible questions by
section 10's four criteria, and may report the prepared set insufficient. No counting rule
stands in for either.

## D2 — A person switches a category on, looking at what the report exposes

*The gap:* section 14 enables routing "only for the categories that demonstrate acceptable
results" and defines neither *acceptable* nor who judges it.

*Decision:* switching a routing category on is a recorded decision by a person that names
the evaluation report it rests on. No threshold is built in. The report exposes, per
category: how many reviewed examples it holds, how many of the model's classifications
disagreed with the reviewed decision and which, and how many examples carry no annotation.
The tool refuses to switch on a category whose named report holds no reviewed example of it
— which proves only that the report is not empty, never that the category is reliable;
reliability is the person's judgment of the numbers exposed.

## D3 — Permission to classify is separate from permission to act

*The gap:* section 14 enables routing per category, but section 6's category of an answer
is known only after the model has classified it, so a per-category switch cannot decide
whether to ask the model.

*Decision:* one switch decides whether the decisions model classifies free-text answers at
all. A further switch per kind of answer decides whether the application *acts* on a
classification of that kind without the text model. A kind that is off hands the turn to
the text model, with the model's classification recorded beside the text model's
interpretation for later comparison. Every switch is off until switched on under D2. The
same holds for the switch that lets the model choose the next question.

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

## D5 — The brief is checked against current accepted decisions

*The gap:* section 12's reviewer looks for "omitted answers", while section 11 puts
"revisions and superseded decisions" in the session history. Read literally, a brief that
correctly leaves out a revised answer would be refused, and a brief that states the old
answer would pass.

*Decision:* the current accepted decision for a question is the latest answer the user has
not superseded, together with every bounded delegation and every exclusion from scope. The
fidelity checks compare the brief with those. A superseded answer stays in the session
history word for word, is never a current accepted decision, and must not appear in the
brief as a decision.
