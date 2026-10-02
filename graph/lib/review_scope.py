"""The answer a reviewer must give: the one closed shape `review_read` reads."""
from __future__ import annotations

# The exact shape `review._json_verdict` will accept, for the prompts that ask
# for it. It lives here, next to its parser, because for a year four prompts
# said only "the graph review JSON: review, accept boolean, findings list" and
# a reviewer that obeyed those words and wrote findings as OBJECTS had a
# correct REJECT thrown away as malformed (2026-09-18). A prompt and a parser
# that state the shape separately will drift; these two cannot.
SHAPE = ('Answer with exactly one JSON object on one line and no other text: '
         '{"review":"ACCEPT|REJECT","accept":true,"findings":["what is wrong, in one sentence"]}. '
         'Exactly those three keys. `findings` lists every finding, at most ten plain strings, never objects. ')
VERDICT = SHAPE + 'ACCEPT requires accept=true and no findings; REJECT requires accept=false and at least one finding.'
# The lean reviewer's own rule: an ACCEPT may list findings that block nothing, said once, not overridden.
NOTED_VERDICT = (SHAPE + 'ACCEPT requires accept=true and may list findings that block nothing; REJECT requires '
                 'accept=false and at least one finding.')
