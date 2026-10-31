# AI Prompts — Homework 5 (Campus Customs Multi-Agent Operations)

Prompts I gave my AI coding assistant, one section per problem. The running app, database writes, and screenshots are the evidence of the results.

---

## Scenario and Setup

**Prompt (my words):**
> It's time to work on homework 5: Campus Customs Multi-Agent Operations. This is the agentic team that runs the shop. Open tickets land on a board: customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. We'll build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can watch the agents at work and approve requests. Our agent team has full connectivity, so an agent may delegate tasks to any other agent for help. The agents are: Boss (reads each ticket, decides who should work on it, and makes the final calls), Inventory (checks stock by SKU and size, spots shortfalls, figures out which vendor can restock), Accounting (watches cash and invoices, checks margins, prepares payments or purchase orders for human approval), Facilities (handles the shop space side, like leases and rent), and Customer Service (drafts messages for customers).
>
> Download data.zip and unzip it so we have data/campus_customs.db, the original shop database (tables include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices). Our tools will update the database as tickets get resolved. Make a copy called data/campus_customs_new.db and point the MCP server and backend at that working copy. Keep campus_customs.db untouched so we can reset when we want to restart resolving the tickets.
>
> Shop rules: desk.date_today is today for the shop, so use it to determine what's overdue. Vendor lead times come from the vendors table. A vendor will not ship new product while they still have an unpaid open invoice. Human approval is required for any payment. If a payment is made, update the relevant table. If there's not enough cash, the pay tool must refuse, with no negative balances. Cash only goes out; we did not model revenue. Before a full run to resolve the tickets, reset the database to the original values. Do not email customers or call real vendors; the drafts stay on the board. Use PORTKEY_API_KEY for all AI calls, and use only GPT-6 Luna through Portkey for every agent. We work one problem at a time, and the final submission is a public GitHub repo.

---

## Problem 1: Vibe Coder Prompts

**Prompt (my words):**
> Create AI_prompts.md and keep it updated as we work. This is the log of what I type. I'm going to describe each problem in my own words. Put one section for each problem. Each section must include the problem number and title, at least one prompt I typed in my own words as much as possible, and one follow-up prompt if I needed it, with one sentence on what was lacking after the first.

**Follow-up:** None needed.

---

## Problem 2: Study the Campus Customs Database

**Prompt (my words):**
> Study the Campus Customs database. Open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db; later problems are going to update that working copy. We'll study the three open tickets to see how they link to the other tables. Then start output/harness.md: for each table, list the fields and one short line on why that table matters for the agents. We'll keep growing this harness file in later problems. It's hard for me to look at a database file, so if there's something I need to see or a summary, let me know.

**Follow-up:** None needed.

*What was lacking:* Nothing important; the first prompt covered every step, and asking for a summary (since I can't read a .db file myself) is what got me the plain-English table list in harness.md.

---

## Problem 3: Build the MCP Server

**Prompt (my words):**
> Build the MCP server. Write an MCP server in mcp_server/ using fastmcp that talks to data/campus_customs_new.db. We don't need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. We'll add more tools later, but for now write 3 tools we know we'll need for the tickets in the database. Keep the names clear, never invent any data, and use only information in the database. In output/harness.md, list each of the 3 MCP tools: which table it reads, which ticket it helps unlock (101, 102, or 103), and 1 sentence on why that tool is right for that ticket. Also add a short mcp_server/README.md that explains what the MCP server is for, which database file it uses, and the 3 tools it has. For these three tools, I think it would be helpful to brainstorm some ideas.

**Follow-up:**
> I agree with you: A, B, and C (check_stock, get_vendor_status, get_lease).

*What was lacking:* The first prompt asked to brainstorm but didn't pick the three tools, so after the assistant listed eight options with what each one reads and unlocks, I chose the set that covers all three tickets.

---

## Problem 4: Add the MCP Server to the Vibe Coder and Test Each Tool

**Prompt (my words):**
> Add the MCP server to the vibe coder and test each tool. We're adding the MCP server to this project so you can call the tools. Save the connection JSON in .mcp.json at the project root, or however you save local MCP server lists. Then, with you connected as the vibe coder, we're going to test each of the 3 MCP tools. Save the evidence in output/mcp_smoke.json. Every tool needs to include the prompt I asked you, the tool name, and the tool output, which must match values in data/campus_customs_new.db.

**Test prompt (my words):**
> Okay, can you check how many classic bulldog Tees we have in size small? And can you see if Bulldog Print Co. (vendor one) can ship right now? Show me any lead time, any open invoices. And finally, look up lease one. Let me know how much is the rent and when is it due.

**Follow-up:**
> Can you pick up where you left off? … Oh, I see. Well, in order to meet the homework requirements, which one do we do? … Okay, so maybe a new one just to reduce token usage reading this chat. … Okay, that's fine. You can continue here.

*What was lacking:* My first prompt assumed the vibe coder could call the new server right away, but a session only loads a project's `.mcp.json` when it starts, so we had to test the tools from a session that had the server connected. Later, after Problem 9's payments changed the working database, we re-ran the same three tools so `mcp_smoke.json` still matches `data/campus_customs_new.db` (see `post_run_recheck`).

---

## Problem 5: Build the Agent Team and Grow the MCP Tools

**Prompt (my words):**
> Build the agent team and grow the MCP tools. Build the agentic team for Campus Customs using PydanticAI. The team is Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backend/prompts/, one file per agent. Put data types in backend/models.py and the agent files under backend/; the layout can vary as long as the 5 roles are clear. Use PORTKEY_API_KEY and only gpt-6-luna for every agent. The prompts should all be written in my own words with the shop rules the agents need, and more detailed prompts that cover all aspects of each agent's work and scope score higher than a short generic prompt, so help me make sure we get good prompts. Also add any tools the agents need to the MCP server so they can work on the open tickets. The shop facts should come from the MCP server over data/campus_customs_new.db; we shouldn't invent a second shop-tools layer that bypasses the MCP. Wire the agents so they append to output/audit_trail.json as they run, and for each agent loop step, record enough to audit later. Append to the file; don't wipe it each run. In output/harness.md, list each agent and each MCP tool, including the ones we add in this problem, along with which table each tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/README.md so the tool list matches what we have now. And make sure you engage me in all of this where I should be coming up with things, so that I understand what we're doing.

**Follow-up:**
> OK, this is totally new to me. I need us to go through one by one and to get some help from you, suggestions.

Then I answered the prompt questions one at a time, in my own words:

1. **Boss routing:** "I like option A. The boss should route the ticket by type to the most obvious owner and should step in only if there are disagreements or a decision needs to be made that the other agent can't make."
2. **Resolved:** "Resolved should mean that nothing is waiting on anyone. So if it is just completely done, but if something still needs my okay, for example, it should be waiting_approval."
3. **Inventory:** "Inventory should report exactly how many are on hand compared with how many were asked for and the shortfall, whether a partial order can ship now, and what other sizes are in stock as an alternative for the customer. It should report which vendor can restock, its lead time and the earliest arrival date, and whether that vendor is blocked by an unpaid invoice. It should also report the restock cost drafted as a purchase order for my review. It should choose a vendor by matching what the vendor makes to the item. For example, apparel goes to Bulldog Print Co. If that vendor is blocked, it should say so and hand the unpaid invoice to Accounting rather than picking a vendor that doesn't make the item. We should never pick a place that doesn't actually make what we need." (Then: "We can take QuickShip out of the prompt.")
4. **Discounts:** "Bulk orders of 10 or more can get up to 15% off. Do not ever sell below $45 for a hoodie. And anything more than that needs my approval."
5. **Cash priority:** "We need to pay rent first because that's what makes sure that we can keep our shop space. Then we pay the overdue vendor bills, especially starting with the ones that block any restocking. And then restock only with what's left. We always want a buffer in our account, so never let checking drop below $100. And if there's not enough for everything, just show me all of them and let me choose."
6. **Facilities:** "They should make sure the notice is really from the landlord and that the amount and the due date match the lease. They should make sure it hasn't already been paid, so this isn't a duplicate. If anything doesn't match or seem right, they should flag it for the Boss instead of passing it on. The Boss will decide if I need to see it. They don't need to pass anything back to the Boss or to me if everything looks right. Once it does look right, they should just send it directly to Accounting to prepare the payment."
7. **Customer Service:** "The tone should be friendly and personal, but definitely clear and to the point. They should be a little bit funny in a dad-joke kind of way that still stays professional. They should never promise a date we can't keep, never talk about our money problems, and never confirm discounts we haven't approved. If we have an alternative we can offer, they should always offer it."
8. **Rules for every agent:** "Definitely everything you said. And I think we already mentioned that if something's off, it should go to the Boss."

*What was lacking:* The first prompt asked for detailed prompts in my own words but didn't give the business rules (routing, what "resolved" means, the discount limits, payment order, the cash buffer, rent checks, customer tone), so we went question by question and I decided each one. My answers also added two tools: get_payments for the duplicate check, and a $100 below-buffer warning in prepare_payment.

---

## Problem 6: Plan the Three Tickets

**Prompt (my words):**
> Plan the 3 tickets. Before we wire the backend, we need to write down what we expect the team to do on each open ticket. Build output/desk_tickets.html, a page we can double-click with one tab per ticket (101, 102, 103, in numerical order). Also add empty Cash and Reflection tabs for later problems, but leave them blank or with a "coming later" note for now. On each ticket tab, fill an Expected section only, and leave room for an Actual section that we fill after we run the agents. For each ticket's Expected section, write in our own words who the Boss should call first and why, all the agent delegations we expect (not "Boss calls everyone"), and which MCP tools we expect that run to use. Plans that send every specialist on every ticket score low, because that's crazy. We need a good, efficient plan, and we'll compare this plan to what actually happens when the agents resolve the 3 tickets.

**Follow-up:**
> Plans look right.

*What was lacking:* Nothing; the expected plans follow the routing and business rules I chose in Problem 5 (route by ticket type to one owner; the owner hands off directly to teammates), so I only had to confirm them.

---

## Problem 7: Backend Routes

**Prompt (my words):**
> Backend routes. The React frontend dashboard, which is the next problem, needs a backend it can call. In backend/main.py, use FastAPI to add routes that do the following: return the three tickets and whether each is open or resolved; take a ticket ID and run the agent team on that ticket; return recent agent events (what each agent said and which tools they used) so the board can refresh; approve a payment or purchase after a human clicks Approve, remembering that agents only prepare the payment and the route is what actually changes cash; return the current checking balance from cash_accounts; and reset the database to the original values when we want to try a fresh run. From the backend/ folder, start the server with `uvicorn main:app --reload --port 8000`. This turns on the backend at http://localhost:8000 so the frontend dashboard can call these routes. Then in output/harness.md, list each route in one line: what URL, and what it does.

**Follow-up:** None needed.

*What was lacking:* Nothing for this problem; the prompt listed every route. The dashboard in Problems 8 and 9 later needed more routes (drafts, board runs, triage, order changes), which are logged there.

---

## Problem 8: Agent Dashboard

**Prompt (my words):**
> Agent dashboard. Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes we built in Problem 7. At minimum, the board should list all 3 tickets, let you pick 1 ticket and start the agent team on it, show each agent and what they're saying or doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay or purchase when asked, and show the checking balance, which should drop after an approved pay. Make the dashboard look good. It should be really cool, with the feel of a real desk that people would want to sit at, so give me some ideas for how to make it really nice. The frontend talks to the backend at http://localhost:8000, and the backend allows the Vite page origin (usually http://localhost:5173) so the browser can call those routes. We start the board with `npm run dev`. Write output/design.md with what we chose for the dashboard look (the layout, how the agents read differently, how resolved tickets and cash show up) and why, including the creative choices that make it feel special and something humans would actually enjoy using. I'd love some ideas from you, and then I can look at what we're building and give feedback.

**Follow-up:**
> Love it, keep all. Can the rubber stamp have a little Handsome Dan on it? When something is resolved, can it make a fun noise? And when something gets passed to a different agent, could it make a little sliding-across-the-desk sound, or would that be too annoying? I'm okay keeping my resolved rule as long as it doesn't get in the way of getting 100%. If resolved is what the homework is asking for, we should go with what the homework says, and make a different term for when I'm done, like signed or complete.

> Would it be cute if the Handsome Dan stamp had a little outfit or hat that matched the agent he's working for? Didn't accountants wear visors back in the day? … OK, no, stick with the top hat for the Boss. All headgear is the best.

> Pretty good, but the text in the desk log is kind of ugly. Can we make it nicer to look at? And when the note comes across, it's so big and the agents are so small, so maybe spread the agents more across the top. It could look cleaner if we don't have to see the checks and drafts all the time. Maybe they can be in a pile that can expand, like the drafts, or the checks could be in a checkbook that we can open.

> Good changes, but the color scheme is kind of boring, and Handsome Dan could look way cooler. … Dan A/B + Vintage. Actually, Dan should have been all three, then Vintage. … Dan looks too mad right now. … If the teeth pointed out like a bulldog's, slightly slanted out, it would look cuter.

> OK, Handsome Dan looks better. Now imagine a 35-year-old wants to work at this desk. It looks too old-fashioned, you know. Maybe it's the wood stripes in the background. And don't you think a ticket board would be better along the top or something?

> OK, close, but now a lot of the stuff doesn't fit on one page. What if, under each ticket, there was a branching system that shows how it moves from the Boss to Accounting, etc., without all the text, while the desk log has the text? The seats are kind of redundant now anyway, no? … Does it need to be left to right? Could it show the Boss down to Accounting, etc., with arrows for the directions, to keep it under the specific ticket? … Yes.

> Yes, looks good. Now the bar across the top: I think the checking section should be added to the top bar as a small counter. And the checks and email drafts should link directly from the ticket, so it's clear what they're linked to.

> You're doing great. But why are the numbers next to the Dans so weird? And the night color is poop brown, no good. When a ticket is selected, it should be clearly highlighted so we know which log and summary are up. When I click on the sign part, it should go only to checks, and the drafts should go only to emails. … Make the checking section more salient as well. … Instead of fatter, maybe wider? There's so much free space on that bar.

> I'm wondering if the draft still needs to open in a pop-up, now that the whole sidebar is clear. What do you think? Or if it should because of mobile or something, then the check should too. … Go. … Does it turn poop brown when I open the sidebar for checks or emails?

> OK, I think it's pretty good. Any final recs? … Can we make both changes, but also note it for Problem 10?

*What was lacking:* The first prompt asked for ideas but didn't choose a direction, and my Problem 5 "resolved" rule (wait for my approval) didn't match the homework's "mark resolved when the run finishes." So I picked the Back Office Desk with all the extras, added Handsome Dan stamps in each agent's headgear plus desk sounds, and we split "resolved" (the agents are done) from "signed" (I'm done). After trying the first build, the log showed raw tool calls, the seats were small, and the checks and drafts cluttered the till, so the log became a chat with plain-English tool pills, the team moved to a full-width row, and the checks went into an openable checkbook with the drafts in an envelope pile. Then the palette felt boring and Dan looked like a teddy bear, so we compared three Dan styles and three palettes side by side, chose all three Dans (badge logo, seat Dan, stamp Dan) with Varsity Vintage colors, and softened Dan's face with fangs that slant outward. Finally, the desk still felt too old-fashioned for a modern manager, so we removed the wood stripes and slab type for a clean, modern look and moved the tickets to a rail across the top. To fit everything on one screen, the big agent seats became a small top-down flow tree inside each ticket card (planned handoffs dashed, real ones solid), and the shift reports became a Summary tab in the log. Last, checking moved into the top bar as a small counter, and each ticket's checks and drafts now open from link chips on that ticket, so it's clear what they belong to. A final polish pass removed the confusing tool-count numbers on the Dans, made night mode charcoal instead of brown, clearly highlighted the selected ticket, split the drawer so checks and drafts open separately, and made the checking counter a wide strip with a pop-out chip when money leaves. Drafts now unfold inline in the drawer instead of a pop-up, and the drawer's backdrop is a neutral gray instead of brown. In a last pass, the Summary tab now opens by itself when a run finishes, and the Boss prompt now leaves customer drafts to the ticket's owner. Test runs of ticket 103 showed an unplanned Boss → Customer Service handoff that made a duplicate draft and used about 46% more tokens, which we saved to discuss in Problem 10.

---

## Problem 9: Resolve the Tickets

**Prompt (my words):**
> Resolve the tickets. Before testing the agents on a full run over the 3 tickets, reset the working database data/campus_customs_new.db again so we start clean, and note the starting checking balance. Then we'll run all three tickets on the board until each is resolved. Open output/desk_tickets.html from Problem 6. On each ticket tab, fill the Actual section from this run (which agents worked, what they delegated, which tools they used) and keep the Expected section so we can compare the two. On the Cash tab of the same file, itemize the money: the starting balance after the reset; for each ticket, how cash changed when the ticket resolved and why (which pay or purchase, dollar amount); and the ending checking balance, which must match cash_accounts in the working database. Wrong cash math loses points even if the board shows every ticket resolved. Also save output/resolved_tickets.json (for each ticket ID: final status, short outcome, what each agent contributed, and any human approvals) and output/resolved_board.html, a page we can double-click with a screenshot of the React board for each resolved ticket. Real runs append to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the 5 agents, API routes, the dashboard, and safety rules. I'm guessing I'll have to void a check so the last one resolves, because we don't have enough money. Does it all make sense? Any comments?

**Follow-up:**
> Interesting question: if we know rent should go first, shouldn't the Boss be suggesting the first ticket we address? … Yes. … Signed it. … Signed both. … Refused, then voided.

> Now that I'm using the finished product, a couple of pieces of feedback. In the Summary, reorder the agents in the order of the work they did, and if work goes to one agent more than once, it should show up again, so we can see the full flow. Also, the Boss is supposed to make things easier: if he's determined an order from the parameters we gave him, he should just go through all those tickets instead of making me hand them over manually. Then, once it's ready for me, I should be alerted that I can start signing, and it should be extremely clear, without reading a bunch of text, where I start and what order I do it in. … If we keep a manual "hand to the Boss," it should be really clear that it's not the primary way this works. … Done signing.

> Now the Boss's order banner at the top is a little too much; too many places to look. The Boss should just decide and start working, maybe with a sticky-note pop-up showing why, and the Summary could show the why. Minimize duplicate information. Also, ticket 103 was signed, but the green stamp makes it look done when an email still needs to go out. And I'd like a manual override where I reorder the cards. (I then shared an expanded version of this feedback, written with Gemini: remove the banner, sticky-note reasons, no "false green" with a pulsing amber action button, a split-pane review before a draft goes out, and drag-and-drop reordering.) … Do we even need the "my turn" area, or could the reordered cards just show the order visually, like an arrow from left to right? … Does the branching tree actually help on the tickets, or is it just busier? Maybe a picture of what's happening instead, like the shirt, the hoodie, or the shop. And take the brown out: Campus Customs colors, Yale blue and white, a blue background for dark mode and white for light. My signature doesn't fit, and nothing makes it clear I can drag and drop.

> Okay, I did them all and that was awesome. But I realized then that we need some kind of undo button for the approved draft. Also, instead of the summary showing, well, I guess the summary can still show why the boss put it if it's not superfluous, but I'm thinking that when you go to do something like pay rent, if you hover over it, it should show why that's the next step.

> This note is still brown. … Wait, why do I have to manually do that? And will it be gone going forward? Can't you just update that language here: take out that inventory counts piece and the internal codes?

> I don't really see a reason to mark them as "edited"; aren't we setting it up now? … Ahh, so maybe the Boss should review for that kind of language, or we program the agent not to use that language. … Yes, let's make that part of the agent's rules, and then it won't need to say "edited."

*What was lacking:* The first prompt didn't say what order to run the tickets in, and I was doing it from my own rule, so we added a Boss triage step that ranks the board from the cash rules (102 → 101 → 103). I then signed each payment myself as the tickets resolved, and on 103 tried to sign the $264 hoodie restock, which the pay tool refused (no negative balances), then voided it. Checking went $3,400 → $152. The first attempt was reset and rerun after the Boss closed a ticket as `waiting_approval` instead of `resolved`, which we fixed in code. After using it, I asked for the Boss to run the whole board himself and give me one clear, numbered signing queue (plus a Summary in work order), so we reset and redid the official run that way: one click, all three resolved, then I signed steps 1–3 and voided step 4 for the same $152 ending balance. The last round added an **Undo** for an approved customer draft (safe because drafts are never sent; signed checks stay final because the money has already moved) and a **"Why step N?" note** on hover for each step, built from the real numbers (e.g., rent due in 2 days, a bill 3 days overdue that blocks restocks, a restock that would take checking to -$112). The pop-up notice was still the old brown and is now Yale navy. A later run's customer drafts leaked internal text ("(Inventory counts: check_stock, as shared.)" and the SKU "CC-HOOD-NAVY"): Customer Service had applied the team's "show your sources" rule inside the customer's message. We fixed it three ways: the Customer Service prompt now says sources go in the report, never the draft, and to use plain product names; the `save_customer_draft` tool now refuses any draft containing a tool name or SKU code so the agent must rewrite it (enforced in code, since prompts alone weren't reliable); and a new edit route let the AI clean up that run's two drafts, which still wait for my approval. Rather than hide the "edited" mark (the audit would still show the agent's original words), we kept the rule in the agent (prompt plus code check, not a Boss review, since the Boss is also a model and a review costs tokens), then reset and reran the board (audit seq 2438–2630). Both drafts came out clean on their own with no edits and no refusals, and every handoff matched the plan.

---

## Problem 10: Reflection

**Prompt (my words):**
> Problem 10: Reflection. We open output/desk_tickets.html and fill the Reflection tab. How would we evaluate the performance of the agents on each ticket, and why? Please remind me of the things we've identified that I'm forgetting, but I'll start with that. It looks like Customer Service was using things customers wouldn't want to see, like back-end language, so we had to fix that, and it did a lot better. I think the Boss did a pretty good job of figuring out where things needed to go. We made notes on where we had to fix things along the way. Accounting did a good job: they made sure we didn't go under $100. Inventory was on top of what we have and what other options we could use. Remind me how the Actual compared to our Expected outcome, and what would have been simpler as one agent with tools; we took notes on that. What are three new problems Campus Customs might face that this team could solve with the tools we built? Right now we don't have anything about money coming in; if we did, the team could help balance money in and out and plan timing. Other payments, like electricity. And if someone got the wrong product, we could check what was shipped and suggest fixes. What could they not do? Maybe that last one, since we haven't built tools for it yet. What other thoughts do you have?

**Follow-up:**
> We should be tying every answer to this particular app and the three tickets we ran, and use the ticket tabs and Cash tab on the same page as our evidence. Generic AI essays without Campus Customs details would score low.

*What was lacking:* My first prompt mixed up two of the questions: money coming in, utility bills and wrong-product complaints all need tools or tables we don't have (no sales, orders or shipments tables, and `pay` only knows invoices, rent and purchase orders), so they became the three problems the team could *not* solve, and the AI suggested three it *could* solve with today's tools (a duplicate or fake rent notice, a bigger-discount request, and when the AI Club's other 12 hoodies become affordable). My note that "Accounting made sure we didn't go under $100" also needed checking: going back to the audit trail showed Accounting did flag that the $264 restock would breach the buffer, but the money was actually stopped by code (the dashboard's red flag and the pay tool's no-negative refusal) and my void. While writing it, the AI first read only Accounting's one-line summary and wrongly said the buffer warning was missing in the official run; the full findings showed it was there, so we corrected the reflection and restored that line to the #103 outcome. The audit also showed the draft leak was systematic (6 runs with "check_stock", 7 with the SKU) and that several #103 reruns were identical to the token, which is why only changing the rules fixed it.

