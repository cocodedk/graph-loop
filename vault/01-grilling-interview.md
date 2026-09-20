---
status: branch
---

## Goal

Interview the user about an initial brief until every consequential question is answered, delegated or excluded, and keep an exact record of the session.

## Why

Given an initial brief, the user is asked one consequential question at a time, each naming the uncertainty, the different readings and the cost of leaving it open. A question the repository or an earlier decision already answers is not asked as an open question. The user is still asked whether existing behaviour should stay, when that is a real choice. A picked choice is recorded as picked. A free-text answer is kept word for word, with an interpretation beside it. It is treated as answering, partly answering, possibly contradicting an earlier decision, adding a requirement, or unclear. Anything that fits no known alternative, a malformed reply, or an unavailable Jev service goes to the text model and never marks a question resolved. A possible contradiction is shown to the user and never quietly replaces an earlier answer. "I don't know", a skip or no answer stays unresolved, while a bounded delegation or an exclusion from scope counts as resolved. The next question is chosen from those whose prerequisites are met. Routine turns show a prepared question without a text-model call. An empty queue triggers a completeness review and is not taken as proof of completeness. A question raised later, during specification, returns to the same record for a focused follow-up. Settled decisions are reused unless new evidence or a changed requirement gives a reason to revisit them, and a changed confirmed answer marks the dependent decisions for review. The session record holds exact questions and answers, classifications with confidence, proposed interpretations, revisions and superseded decisions, review findings, and call timing, failures and cost. An interrupted session resumes without repeating answered questions, and raw transcripts and rejected drafts stay out of the material later stages plan from.
