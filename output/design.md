# Campus Customs Back Office Desk: Design

The dashboard (`frontend/`, React + Vite + TypeScript) is a modern back office for a small Yale shop. **One rule shaped every decision: there should be one place to look.** The Boss decides the order and works every ticket himself; the cards line up in that order; and everything the human has to do sits on those cards as numbered steps, read left to right. The live log and the Summary hold the details for anyone who wants them.

Run it with `npm run dev` in `frontend/`. It talks to the backend at `http://localhost:8000`, which allows the Vite origin `http://localhost:5173`.

## Layout

| Area | What's there | Why |
|---|---|---|
| **Top bar** | Yale-blue bar with the Handsome Dan badge, a wide **checking counter** (white digits on navy, a bar marking the $100 buffer, a red "−$2,400" chip that pops out when money leaves), the **shop's date** from `desk.date_today`, and sound, lamp, and Reset desk | Cash is always in view without a panel of its own. The calendar uses the shop's date, because every overdue rule does. |
| **Ticket rail** | One big **"▶ Let the Boss run the board"** button, then the three ticket cards **in the Boss's order**, with orange arrows between them | Work comes in at the top and flows left to right. Running a single ticket by hand is only a small grey "or run just this ticket" link, so it's clearly not the main way. |
| **Each card** | Rank number and a 📝 note, the request, **a picture of what the ticket is about**, a tiny row of the agents who worked it, the stamp, and the **numbered steps** for the human | Everything about a ticket, including what you must do, is in one place. |
| **Desk log** | **Live log** (each agent's words and tool calls, for the selected ticket) and **Summary** (the Boss's reason for this ticket's place, then a numbered timeline of the work in order) | Details live here, out of the way of the work itself. |

## How the agents read differently

- **A picture instead of a diagram.** Each card shows what the ticket is about: the real catalog photo of the **Basic Hoodie Big Yale** (#103, from our HW4 product images, backdrop cleaned to white), a **drawn white Bulldog tee** (#101; there's no photo of that exact tee, so we drew one instead of passing off a different shirt), and a **drawn Chapel Street storefront** with a blue-and-white awning (#102, rent). An earlier version had a branching tree of agents on each card; it repeated what the log and Summary already show, so we replaced it.
- **A tiny agent row** under the picture: Handsome Dan in each agent's headgear (Boss top hat, Inventory delivery cap, Accounting green eyeshade, Facilities hard hat, Customer Service headset), in the order they joined. Each one bobs and lights up while it works.
- **Distinct, varied agent colors:** Boss Yale navy, Inventory teal, Accounting green, Facilities purple, Customer Service pink. Each card's side stripe uses its owner's color.
- **Summary as a timeline of the work:** ① Boss routes the ticket → ② Inventory → ③ Accounting (from Inventory) → ④ Customer Service (from Inventory) → ⑤ Boss makes the final call. An agent called twice appears twice, and anyone not needed is listed as off shift. It opens with the Boss's reason for the ticket's place in line.
- **📝 sticky notes** on each card show *why* the ticket is where it is ("#1: the Boss's call: rent is $2,400, due in 2 days…"), or "#1: your order (the Boss had it at #3)" after a drag.

## How resolved tickets, approvals, and cash show up

- **The Boss runs the board.** One click: he triages (rent first, then overdue vendor bills, then restocks and discounts, never below the $100 buffer) and works every ticket in that order. While he works, the steps show "after the Boss" and nothing is clickable yet.
- **Your turn, with no reading required.** When he's done: a chime, a message, a "(6) to do" count in the browser tab, and the page scrolls to the rail. Your steps are numbered ① ② ③… across the cards, left to right; **START HERE** glows on the next one; orange arrows point the way. Each check shows the balance after it ("→ $1,000 left"), "after step 2" when a purchase order needs its vendor's bill paid first, and a red "not enough cash: void it" when the pay tool would refuse.
- **"Why step N?" on hover.** Hover over (or tab to) any open step and a small note explains why it comes at that point, in plain numbers: "Rent comes first: it keeps the shop space. $2,400.00 is due Sep 2 (in 2 days). Leaves $1,000.00"; "Overdue 3 days. Bulldog Print Co won't ship any restock while this bill is open, so it goes before steps 3 and 4"; "Not enough cash: … checking would be −$112.00. The pay tool refuses negative balances, so void it." The Summary keeps only the Boss's reason for the ticket's place in line.
- **No false green.** A card stays **amber, "action needed"** while anything waits on a human: a check *or* a customer draft. It turns **emerald "ALL DONE"** only when every check is signed or voided **and** every draft is approved. (An earlier version turned green as soon as the checks were signed, even with an email still unreviewed.)
- **Reviewing a customer draft.** The pulsing amber "✉ Review" button opens a split-pane overlay. On the left is the draft, which you can edit. On the right are **only the real sources**: the original request, what the teammate told Customer Service, and the facts the agents pulled from the database (stock by size, vendor status, prepared checks, restock drafts). "✓ Approve draft" logs the approval in the audit trail. **Nothing is ever emailed**; the approved draft stays on the board, as the assignment requires. Changed your mind? **↶ Undo approval** (in the review, or the small "undo" on the approved step) puts the draft back in your steps, keeps any edits, and turns the card amber again. Signed checks have no undo, because the money has already moved.
- **Drag to reorder.** Before the Boss runs, a visible ⠿ grip and a "Drag the cards" hint invite you to drag the cards into your own order. A quick "Recalculating…" confirms it, and the Boss then works your order. After the board has run, reordering is refused, so the order shown is always the order the work really happened in.
- **Signing.** Type your name once in "Signing as" (wide enough for a full name). Every Sign, Void, and Approve records it.

## Creative choices that make it special

- **Campus Customs blue and white.** Light mode is clean white with Yale blue; night mode (💡) is a deep navy background. Amber and orange are reserved for "you need to act," and green for "done," so color alone tells you where things stand. We moved here from a warm brown "vintage" palette that read as muddy.
- **Handsome Dan everywhere, in costume.** It's our own mascot drawing (not Yale's logo), so it's safe for a public repo: a friendly bulldog with a brindle eye patch, droopy jowls, and outward-slanting underbite fangs, in a blue collar. He appears as the badge logo, as each agent (in headgear), and as one-ink rubber stamps on RESOLVED and ALL DONE.
- **Physical metaphors, kept light:** rubber stamps, sticky notes, and pictures of the actual goods. Everything else stays modern and minimal so those moments stand out.
- **Sounds made in the browser** (no audio files): a paper slide on each handoff, a stamp thump and chime when a ticket resolves, a ka-ching when a check clears, a thud on a refusal. 🔔/🔕 mutes them.
- **Calm by default, lively when it matters:** the board polls slowly when idle and quickly while agents work.

## How we got here

Built in rounds of feedback, using the desk for real: a wood-and-cork vintage desk → modern layout with a top ticket rail → big agent seats replaced by small per-ticket trees → the Boss runs the whole board → one numbered list of human steps → steps moved onto the cards (no separate panel) → trees replaced by pictures → blue-and-white palette. Each round removed something to look at.

## Built with

`frontend/src/App.tsx` (desk, polling, sounds, alerts), `steps.ts` (orders every human action across the cards and projects cash), `components/` (`TicketRail` cards + step tokens + drag and drop, `TicketArt` pictures + agent row, `DraftReview` split-pane review, `Transcript` log + Summary tab, `Reports` timeline, `Team` agent status, `Till` checking counter, `Dan`), `labels.ts`, `sound.ts`, `styles.css`. Data comes only from the backend routes (`/api/tickets`, `/api/run-board`, `/api/events`, `/api/approvals/{id}/approve|reject`, `/api/drafts/{id}/approve|unapprove`, `/api/order`, `/api/cash`, `/api/reset`).
