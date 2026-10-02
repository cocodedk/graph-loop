"""What a lean loop says: to its builder, and in a new pull request."""

from __future__ import annotations

import pathlib

import lean_spec
from review_scope import VERDICT


def pr_body(spec_path: str, why: str, found: str, open_questions: str = "", choices: str = "") -> str:
    """What a new pull request says: the suite, the reviewer's verdict and its findings."""
    said = "accepted it" if not why else "still did not accept it after the last repair"
    return (f"Built by graph-loop's lean loop from `{pathlib.Path(spec_path).name}`: the suite "
            f"is green, and an independent reviewer {said}."
            + (f"\n\nThe reviewer's findings:\n\n{found}" if found else "")
            + (f"\n\n## Built on the builder's choices\n\nThe grill left these questions to the builder: "
               f"Jev judged them the builder's to settle, or {lean_spec.GRILL_ROUNDS} rounds left them "
               f"open:\n\n```\n{open_questions}\n```\n\nThe builder decided "
               f"them; its list:\n\n{choices.strip()[:3000]}" if open_questions else ""))


def builder_prompt(spec: str, script: str, profile_path: str, lessons: str, own_gate: bool,
                   open_questions: str = "", lint: str = "") -> str:
    """What the builder is told. A card with its own fast gate runs only that: the loop runs the full
    suite after the build and hands back any failure. Any builder is barred from background jobs,
    because each wait is a paid turn (one card spent about $75 polling a 25-minute suite)."""
    run = (f"Run this card's own gate with `bash {script}` and leave it green, never the full suite: "
           f"the loop runs that after you finish and hands you any failure" if own_gate
           else f"Run the suite with `bash {script}` and leave it green")
    return (f"Implement what this spec asks, including its tests. Follow the repository's "
            f"CLAUDE.md and the profile at {profile_path}. Choose the smallest coherent solution: reuse "
            f"existing code and shared functions, prefer the standard library or platform, and add an "
            f"abstraction only when the spec needs it. {run}. And never start or wait on a "
            f"background job: every wait is a paid turn. Do not commit: the loop commits."
            + (f" The loop also runs `{lint}` before the suite and needs it green: run it yourself when "
               f"your permissions allow." if lint else "")
            + f"\n\n## Spec\n\n{spec}{lessons}" + (
                f"\n\n## Questions the grill left open\n\nNobody has answered these:\n\n```\n{open_questions}\n```\n\n"
                f"Decide each one sensibly. End your final answer with a complete list, one line each: "
                f"question, your choice and why." if open_questions else ""))


def grill_prompt(profile_path: str, lessons: str, specs: str, earlier: str = "") -> str:
    """What the grill is told. From the second round on it also gets its earlier questions and may ask only
    what the spec still leaves unanswered or the edits broke: each answer adds detail, and asking about
    that new detail is how a spec gets refused round after round."""
    again = (f"\n\n## Earlier round(s) asked these questions\n\n```\n{earlier}\n```\n\nThe person has edited the "
             f"spec since. Now ask only about an earlier question the spec still leaves unanswered, or "
             f"about something the edits made contradict itself or the code; never about new detail the "
             f"edits introduced: the builder settles that.") if earlier else ""
    once = "" if earlier else (" Ask every crucial question you have now, in this one answer: a question held "
                               "back costs the person another round.")
    return (f"You read this spec before it is built, read-only; the repository's CLAUDE.md, "
              f"its brief and the profile at {profile_path} give the context. A builder implements "
              f"it next. It edits files and runs git, the suite and the programs the suite uses; it "
              f"cannot commit or push. The suite is the profile's command, run on this machine with "
              f"its network and Docker in a scrubbed environment; your own read-only sandbox may be "
              f"unable to run it, and that is no question for the person. Refuse only for what a "
              f"person must decide first: a spec that contradicts itself, a decision the builder "
              f"would have to guess, or a requirement it cannot meet here. If the feature has a user "
              f"interface, be critical of every word the spec says about it: refuse until it defines "
              f"the whole journey, from where the feature starts through every page and state the "
              f"user meets (empty, loading and error included) and what the user sees and can do at "
              f"each, to where it ends, and names a design reference (a mock, a sketch or an existing "
              f"screen) to match. Existing screens, components and the repository's standing rules may supply "
              f"those details: what they settle is no question. Ask about anything vague, contradictory or "
              f"likely to confuse a user. "
              f"Each finding is one question to the person. Ask only the crucial questions, the ones whose "
              f"answer changes what is built, the most important first; what the builder can settle "
              f"itself is no question: accept.{once}{lessons}{again}\n\n{specs}\n\n{VERDICT}")
