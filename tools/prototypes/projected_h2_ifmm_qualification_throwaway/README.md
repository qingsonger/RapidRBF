# Issue 65 throwaway candidate-closure audit

This prototype answers one prerequisite question for
[Qualify the projected H2/IFMM factor route on the complete mechanism panel](https://github.com/qingsonger/RapidRBF/issues/65):
is the supposedly frozen projected `H^2`/IFMM candidate specified and
source-bound tightly enough that a four-platform observation can be judged
without the implementer making result-affecting choices?

It does not implement or qualify a factor route. It compares the ratified
Issue 64 resolution and the Issue 65 body against the minimum identity needed
to distinguish a valid candidate result from implementation-selected
observations. The pure state logic is in `model.py`; `review.py` is a throwaway
in-memory terminal shell.

Run the live review with one command from the repository root:

```powershell
python tools/prototypes/projected_h2_ifmm_qualification_throwaway/review.py
```

Print the same initial state non-interactively:

```powershell
python tools/prototypes/projected_h2_ifmm_qualification_throwaway/review.py --snapshot
```

The proposed finding is `INVALID_UNJUDGED`: the numerical family and several
gates are frozen, but the executable candidate identity, deterministic
construction rules, evidence schema, and 100k fixture identities are not.
Accepting the finding would split the next frontier into:

1. freeze and materialize one exact source/build/fixture/evidence binding
   without candidate execution; then
2. execute that immutable binding on the complete panel and 100k structural
   preflight.

No GitHub state is changed by this prototype. The reviewer must report their
accept, adjust, or reject choice back to the Wayfinder session.
