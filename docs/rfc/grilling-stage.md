RFC: A grilling stage before specification, using Jev for fast decisions

  Status: Draft for discussion. No files have been changed.

  1. Purpose

  Grilling turns an initial brief into an agreed set of decisions that the branch writer, spec writer, and planner can use without inventing requirements.

  Its central question is:

  > Could two competent builders follow this brief and produce materially different behaviour because something important remains undecided?

  Grilling identifies those decisions, resolves facts from available evidence, and asks the user about the choices they own.

  Jev accelerates the repeated decisions inside the interview: interpreting an answer against known alternatives, identifying possible conflicts, and selecting among prepared questions. A text model investigates unfamiliar issues and writes new questions.

  The objective is a shorter interview with fewer avoidable questions and less waiting, while preserving the quality of the resulting brief.

  2. Position in the workflow

  Initial brief → grilling → agreed brief → branches → specifications → task cards → execution

  The main interview happens before branch generation because an answer can change which capabilities belong in the project.

  Questions discovered during specification return to the same decision record for focused follow-up. Settled decisions are reused unless new evidence or a changed requirement gives a reason to revisit them.

  Grilling is an interactive preparation stage. A later unattended stage that needs a decision records the question and the affected work; it does not repeatedly restart the interview.

  3. Responsibilities

  Jev returns typed decisions and probabilities rather than generated questions or explanations. That makes it suitable for choosing among alternatives prepared by the surrounding workflow. TypeSafe documentation

  The proposed division is:

   Responsibility                                                      Owner
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━
   Inspect the brief, repository, and existing decisions               Text model
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Discover ambiguities and missing requirements                       Text model
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Write questions, choices, explanations, and likely follow-ups       Text model
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Record an explicit selection from presented choices                 Application code
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Classify a free-text answer against known alternatives              Jev
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Flag a possible conflict with relevant decisions                    Jev
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Choose among eligible prepared questions when judgment is needed    Jev
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Investigate unexpected answers and formulate new questions          Text model
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Check readiness and fidelity of the completed brief                 Independent reviewer
  ──────────────────────────────────────────────────────────────────  ──────────────────────
   Decide product requirements and confirm the brief                   User

  Application code handles decisions already determined by explicit selections or simple rules. Jev is called where interpretation is useful.

  4. What deserves a question

  A question is justified when its answer changes scope, observable behaviour, acceptance, compatibility, or permission to act.

  Each question must identify:

  - The uncertainty.
  - The materially different interpretations.
  - The consequence of leaving it unresolved.

  For example:

  > When an imported row is invalid, should the entire import fail, or should valid rows still be saved?

  The answer changes both the implementation and the acceptance criteria.

  Before asking, the interviewer checks whether the repository or an earlier decision already supplies the answer. Existing behaviour establishes what the software currently does; the user may still need to decide whether that behaviour should remain.

  Question count is not a measure of thoroughness.

  5. Opening the interview

  The text model first reads the relevant material and prepares a working set of questions.

  Each question carries:

   Field                Purpose
  ━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Stable identifier    Allows answers and later specifications to reference it.
  ───────────────────  ──────────────────────────────────────────────────────────────────
   Question             The wording shown to the user.
  ───────────────────  ──────────────────────────────────────────────────────────────────
   Consequence          Why the answer matters.
  ───────────────────  ──────────────────────────────────────────────────────────────────
   Evidence             Relevant brief passages, repository facts, or earlier decisions.
  ───────────────────  ──────────────────────────────────────────────────────────────────
   Suggested choices    Concrete alternatives, where useful.
  ───────────────────  ──────────────────────────────────────────────────────────────────
   Prerequisites        Decisions that must be known before this question applies.
  ───────────────────  ──────────────────────────────────────────────────────────────────
   Follow-ups           Prepared questions that particular answers may make relevant.

  This is a starting set. It must grow when an answer exposes an issue the initial analysis did not foresee.

  The interviewer begins with the question whose answer would change the most downstream work.

  6. Processing an answer

  The interview asks one consequential question at a time.

  When the user selects a presented choice, application code records the selection and applies any explicit follow-up rule.

  For free-text answers, Jev receives a focused state containing:

  - The current question.
  - The user’s exact answer.
  - Known answer alternatives.
  - Relevant earlier decisions.
  - The evidence needed to interpret the answer.

  It classifies the response into a defined set, such as:

   Classification                      Next action
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Answers the question                Record the interpretation provisionally and continue.
  ──────────────────────────────────  ──────────────────────────────────────────────────────────────
   Answers only part                   Ask a prepared follow-up or request one from the text model.
  ──────────────────────────────────  ──────────────────────────────────────────────────────────────
   May contradict a decision           Send the conflict to the text model for investigation.
  ──────────────────────────────────  ──────────────────────────────────────────────────────────────
   Introduces a new requirement        Update the analysis before selecting another question.
  ──────────────────────────────────  ──────────────────────────────────────────────────────────────
   Unclear or insufficient evidence    Ask the text model to investigate or clarify.

  The exact answer is always retained. A classification is an interpretation alongside it.

  Jev must have an explicit route for answers that do not fit the known alternatives.

  7. Where the speedup comes from

  A routine turn can use a question already written during the opening analysis.

  For example:

  > Prepared question: What happens when an imported row is invalid?
  > User: Save the good rows and skip the rest.
  > Jev: Matches the partial-import alternative.
  > Prepared follow-up: What information should the user receive about skipped rows?

  The follow-up can be displayed immediately without another prose-generation call.

  If the user instead says:

  > Save valid rows, unless the file belongs to a regulated customer.

  That introduces a distinction the prepared alternatives may not cover. The text model investigates what “regulated customer” means and how the distinction affects the requirement.

  The design must actually avoid text-model calls on routine turns. Calling Jev and then invoking the text model unconditionally would add overhead.

  Independent checks may share a request. Decisions that depend on earlier results remain ordered.

  8. Maintaining the quality of grilling

  Prepared questions must still support a demanding interview.

  Answers such as “handle errors gracefully” or “make it secure” leave behaviour undefined. The interviewer follows their consequences until the user has made an observable decision.

  For example:

  > User: Invalid rows should be skipped.
  > Interviewer: What must the result show about those rows?
  > User: Their row numbers and reasons.
  > Interviewer: If every row is invalid, should the import still report success?
  > User: No, that should fail.

  The resulting decision is specific:

  > Save valid rows. Report each rejected row with its row number and reason. Report partial success when both occur. Fail when no rows are valid.

  A possible contradiction must be presented explicitly. The system must not silently replace an earlier answer because a later answer appears more convenient.

  9. Uncertainty, delegation, and confidence

  The user may resolve a question by answering it, delegating a bounded choice, or excluding the affected behaviour from the current scope.

  For example:

  > Choose the parsing library, provided it supports the agreed formats and requires no network service.

  That grants useful implementation freedom.

  “I don’t know,” an unanswered question, or a skipped question remains unresolved unless the user makes another explicit decision.

  Jev’s confidence can inform whether an interpretation needs deeper review. It does not establish user intent, grant authority, or prove that the brief is complete. TypeSafe likewise distinguishes calibrated probabilities from a guarantee that an individual answer is correct. TypeSafe documentation

  Confidence thresholds must be evaluated on grilling examples. There should be no assumed universal threshold that makes an answer safe to accept.

  Invalid responses, unavailable service, uncertain interpretations, and unexpected choices return control to the text model. They never mark a question resolved.

  10. Question selection

  Application code first determines which questions are eligible: their prerequisites are satisfied, they remain unresolved, and their subject is still in scope.

  When the next question follows directly from an explicit rule, it is selected without a model call.

  Where selection requires judgment, Jev chooses among the eligible identifiers using defined criteria:

  - How much downstream work the answer affects.
  - Whether it resolves a contradiction.
  - Whether other questions depend on it.
  - Whether it risks repeating something already answered.

  Jev may also indicate that the prepared set is insufficient.

  An empty question queue triggers a completeness review. It does not establish completeness by itself.

  11. Durable records

  The stage produces an agreed brief and a separate session history.

  The agreed brief contains the outcome, scope, accepted decisions, examples, constraints, exclusions, and explicitly delegated choices. Consequential decisions have stable identifiers.

  The session history preserves:

  - Exact questions and answers.
  - Jev’s classifications and recorded confidence.
  - Interpretations proposed by the text model.
  - Revisions and superseded decisions.
  - Review findings.
  - Model-call timing, failures, and available cost information.

  The session can resume after interruption without asking answered questions again.

  Raw transcripts and rejected drafts remain outside the approved source material used by the planner. They provide history without turning abandoned suggestions into requirements.

  12. Independent review and confirmation

  When the interview appears complete, the text model prepares the agreed brief.

  An independent reviewer compares it with the original request, recorded answers, and relevant evidence. It looks for invented decisions, omitted answers, contradictions, ambiguous behaviour, and acceptance that cannot be observed.

  Each blocking finding must name the missing decision and explain its consequence. “Needs more detail” is insufficient.

  Readiness requires:

  - All known consequential questions are answered, explicitly delegated, or excluded.
  - No unresolved contradictions remain.
  - Acceptance is concrete enough to guide specification.
  - The independent review finds no blocking ambiguity.
  - The brief accurately preserves the user’s decisions.

  The user then confirms that revision as the basis for specification and planning.

  A time limit, question limit, empty queue, or high Jev confidence cannot substitute for this process. Confirming the brief does not start execution or replace campaign approval.

  13. Integration with graph-loop

  The existing JEV transport in graph/lib/provider_jev.py provides a starting point, but its request and response handling currently target triage’s single cause question.

  The grilling integration needs its own question definitions, structured confidence handling, and fallback policy. Shared transport can be factored out while preserving triage’s existing contract.

  The existing text-model and independent-review machinery should handle discovery, unfamiliar answers, brief composition, and final review.

  The agreed brief and its revision must be supplied explicitly to the branch writer, spec writer, and their reviewers. The current speccer’s goal-string input alone cannot reliably carry the interview’s decisions.

  Specifications should reference the decisions they implement. A later missing decision returns as a precise question attached to the affected work.

  Changes to confirmed answers require another readiness check and review of dependent material. Earlier decisions remain available wherever they still apply.

  14. Evaluation and acceptance

  Evaluate the proposed workflow against the same interviews handled entirely by the text model.

  Measure both efficiency and quality:

   Measure                                          What it establishes
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Waiting time per answer, including slow turns    Whether the interview feels faster.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Text-model calls avoided                         Whether Jev removes work.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Total model cost                                 Whether the extra routing is economical.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Unnecessary or repeated questions                Whether the user’s time is respected.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Questions incorrectly marked answered            Whether ambiguity is being hidden.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Contradictions missed                            Whether earlier decisions remain coherent.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Decisions lost or altered in the brief           Whether the final handoff is faithful.
  ───────────────────────────────────────────────  ──────────────────────────────────────────────
   Gaps found by the final reviewer                 Whether interview coverage remains adequate.

  Verification must include interrupted sessions, unexpected answers, changed decisions, unavailable Jev calls, malformed responses, and attempts to finish with unresolved questions.

  Begin with recorded interviews where Jev’s proposed classifications can be compared with reviewed decisions. Enable automatic routing only for the categories that demonstrate acceptable results.

  The feature succeeds when it reduces waiting and avoidable model calls while preserving the decisions, challenge, and independent scrutiny that make grilling useful.
