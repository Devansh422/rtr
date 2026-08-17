# Demo dataset

Sample content so that every page and every feature has something to show. Load it
on a staging site, a local machine, or a fresh deployment you are demonstrating.

```sh
python -m backend.scripts.load_demo --status   # what is currently loaded
python -m backend.scripts.load_demo --load     # load it
python -m backend.scripts.load_demo --purge    # remove every trace of it
```

## Read this before loading it anywhere public

This platform publishes claims about named people. Its whole design — the citation
requirement, the fact-check gate, the verification badges — exists so that nothing
unverified is ever presented as fact. **Fabricated data on a live accountability site
is exactly the failure those controls prevent.**

So this dataset is built to be impossible to mistake for the real thing, and every one
of these markers is deliberate:

| Marker | Why |
| --- | --- |
| Every person's name starts with `[DEMO]` | It appears in the profile heading, every listing, every search result and every screenshot. There is no view where it is hidden. |
| Parties are fictional — "Demo Progressive Party", "Demo People's Front" | No real party is implicated by any figure here. |
| Constituencies are fictional — "Demo North Delhi", "Demo Kothrud" | Nobody real holds a seat in them, so a realistic personal name cannot collide with a real office holder. |
| Every citation is titled `DEMO RECORD - not a real source` | The title renders next to every figure on the profile, which is where a reader looks. |
| Citation URLs point at non-existent paths | Clicking one fails, which is the correct behaviour for evidence that does not exist. |
| Member emails end in `@demo-rtr.example.com` | `example.com` is reserved by RFC 2606 and held by IANA, so it can never reach a real inbox. It is not `.invalid`, which would be the more obvious choice: `email-validator` (behind pydantic's `EmailStr`) rejects special-use TLDs, so `.invalid` addresses were refused with a 422 at sign-in and the demo logins below never worked. Non-email fields — representative office addresses, research source URLs — still use `.invalid`, where nothing validates them and unresolvability is the point. |

**It is not loaded automatically.** Nothing in the normal boot or deploy path touches
it. It only exists if somebody runs the command above on purpose.

## What gets loaded

| File | Contains |
| --- | --- |
| `reference.json` | Campaign stage updates for 6 states, 2 fictional parties, 8 fictional constituencies |
| `accountability.json` | 6 representatives with 40 sourced claims, 9 promises across every status |
| `community.json` | 14 members, 5 petitions with signatures, 12 citizen reports, 6 forum discussions, 3 corrections |
| `participation.json` | 5 events with registrations and attendance, 8 volunteer tasks with claimed and verified work |
| `library.json` | 12 research documents and media items, 1 extra course with lessons and a quiz |

## Signing in as a demo member

Every demo member can sign in at `/login` with their email and the access code
**`DEMO-USER`**:

```
citizen1@demo-rtr.example.com   through   citizen14@demo-rtr.example.com
```

`citizen1` has the most activity — signed petitions, filed reports, forum posts,
volunteer hours, event tickets and a course certificate — so it is the best account
for walking through the member experience.

## Purging

`--purge` removes everything the loader created and restores the campaign stage of
every state it changed. It identifies its own records by the markers above and by
nothing else, so it cannot touch real data that happens to sit alongside it.

Run `--status` afterwards to confirm nothing is left.
