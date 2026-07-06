# The Autonomy Upgrade, In Plain English

Companion to `docs/L4_AUTONOMY_SPEC.md` (the technical instructions). This explains what
that spec is actually trying to achieve, without the jargon.

**The one-line summary:** today the agent only checks the ad account when a human clicks a
button, and every change needs sign-off. After this upgrade, it checks on its own schedule,
remembers what it did before and whether it worked, earns permission to make the safest
kind of change without asking, and keeps the ad spend aligned with what the statistical
model said the budget split should be.

---

## What each part does

| Part | Feature | What it does, in normal English | Why it matters |
|------|---------|--------------------------------|----------------|
| A | Scheduled check-ups | The agent wakes up once a day by itself, looks at the account, and decides if anything needs attention — no human has to remember to run it. | This is the difference between a tool you use and an employee who shows up. |
| A | Proposal inbox | Instead of acting, it files its suggestions into an inbox where you approve or reject each one (rejecting requires you to say why). | You stay in charge, but your job shrinks from "operate the system" to "review its suggestions." |
| A | No nagging | If it already suggested something and you haven't answered — or you said no recently — it won't suggest the same thing again. | An assistant that repeats itself gets ignored; this keeps every suggestion meaningful. |
| A | Ping on Slack | When it files a suggestion, it can drop you a Slack message so you don't have to check the inbox. | Suggestions that nobody sees might as well not exist. |
| B | A diary | After every check-up it writes down what it saw, what it suggested, and what you decided. | Without a record, every check-up starts from zero, like an employee with amnesia. |
| B | Did it work? | A few days after a change is made, it looks back: did the problem actually go away? It marks each past action as "worked," "didn't work," or "too soon to tell." | Most automation fires and forgets. Checking your own results is what turns actions into judgment. |
| B | Learning from outcomes | Its next decision takes that history into account: don't repeat what's pending, respect the reason you gave when you said no, and if a gentle fix didn't work, suggest a stronger one instead of the same one again. | This is the "gets better with feedback" behavior — the agent adapts to you and to results. |
| B | A test for the memory | A new eval scenario checks that after acting once, the agent stays quiet the next day instead of re-reporting the same problem. | Trust, but verify — the memory feature gets its own exam. |
| C | Earned trust | Exactly one type of change — blocking a wasteful keyword, which is small and reversible — can be applied *without* asking, but ONLY if the agent has recently passed every exam question about that type of change with a perfect, repeated score. | Autonomy is earned by proven test results, not switched on by a config setting. That's the whole philosophy in one rule. |
| C | Trust is revocable | If it ever fails one of those test questions again, or the test results get old, the permission is silently taken away and it goes back to asking first. | A driver's license you can lose keeps drivers careful. |
| C | Big red switch + undo | A master off-switch (off by default) disables all self-applied changes, and anything it did apply on its own shows up with an "undo" button. | Even earned trust needs a leash and a reverse gear. |
| C | Never trusted with big moves | Pausing a campaign or changing a budget can NEVER be self-applied, no matter how good the test scores — those always wait for a human. | The blast radius of a mistake decides the rule, not the agent's confidence. |
| D | Strategy watchdog | The statistical model (Track 1) said how the budget *should* be split between channels. This part checks whether real spending has drifted away from that plan, and if it drifts too far, suggests rebalancing — with the numbers as justification. | This finally connects the two halves of the project: the model that sets strategy and the agent that executes it. Until now they only met once, at campaign creation. |
| D | Always asks first | Rebalancing suggestions always go to the inbox — they never self-apply. | Moving money between channels is a strategy decision; strategy stays human. |

---

## What it deliberately does NOT do

| Not doing | Why not |
|-----------|---------|
| Call itself "fully autonomous" (L4) | It isn't. The honest label is "L3 + self-initiated check-ups + earned auto-apply for one safe action." Overclaiming is how this project would lose its credibility. |
| Run as an always-on background process | It wakes, checks once, and exits; a scheduler owns the clock. Simpler, cheaper, easier to debug than a live daemon. |
| Touch real ad accounts by default | Everything runs in mock mode unless explicitly and deliberately switched on — same as the rest of the repo. |
| Add new ways to change the account | Every change, human-approved or self-applied, goes through the same single, guardrailed write path that already exists. |
| Let the agent write emails | Notifications are one Slack message, or a log line. Small surface, fewer failure modes. |

---

## How you'd know it's finished

| Check | Plain English |
|-------|---------------|
| One command runs a full cycle | You type one command; it checks the account, files or skips a suggestion, writes its diary, and prints what it did. |
| The demo shows the whole story | The web demo has the inbox, an approve/reject flow, the strategy-drift panel, and (when enabled) one self-applied keyword block with its undo button. |
| The tests still pass | Everything that worked before still works, and the new behaviors each have their own tests. |
| The README tells the truth | The docs describe exactly what was built, including the new honest label and how permission is earned and lost. |
