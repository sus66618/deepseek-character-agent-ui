# Visual fix checkpoint — 2026-08-20

Branch: `feature/persona-ui-mvp`

## Accepted work

- Tasks 1–4 are implemented and independently reviewed.
- Task 5A transparent subject matte is independently reviewed and accepted in commit `75681fb`.

## Rejected Task 5B revision

Commit `019151f` produced 23 RGBA layers, a grouped PSD, validator, tests, and diagnostic images, but the independent visual review rejected it:

- the blink preview used a temporary drawn overlay rather than the delivered eyelid layers;
- delivered eye and mouth layers were not clean, usable semantic animation parts;
- the blink had a blurred eye-socket patch and crude curves;
- hair offset exposed visible dark seams and edge artifacts;
- the compact checkerboard contact sheet concealed defects and was not user-friendly.

Do not treat commit `019151f` as an accepted character asset package.

## Interrupted fix round 1

The user requested a budget-safe stop while fix round 1 was in progress. The worktree snapshot includes:

- an identity-preserving blink reference;
- focused visual evidence for the rejected face and hair layers;
- partial script and test changes for rebuilding the semantic face layers.

The fix is incomplete and unverified. Resume Task 5 fix round 1 from this checkpoint; rebuild the delivered eyelid and mouth layers, remove the hair seams, make QA use only delivered layers, add visual-negative tests, and create a large normal-background before/after preview.

