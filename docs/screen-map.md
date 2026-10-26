# MySys screen map (test site)

**Version:** 1.2 · 25 Oct 2026 (1.2: slice M0b.1, rows 25–28, 15b and the row-26 anchors; rows 21–22 not mapped and row 23 moved to M0b.2 (decisions, 25 Oct 2026); 1.1: corrections from the captures: one Creator field, the Note body is one line, the Note Pool joins title and body and sorts newest first; denylist note; open items moved to `SPEC.md` → MySys screen rules and slice M0b) · **Source:** the Stage 3A walkthrough (`docs/workflow.md`), rows 01–16, captured with Playwright CLI on 16 Oct 2026, and slice M0b.1 (rows 15b, 25–28) on 25 Oct 2026 (snapshots and screenshots in `private/captures/test/`, laptop only). No live captures yet (Stage 3B is view-only and optional for the MVP).

Every value below is **fake**. The real captures stay in `private/`. **The test site's 3 trial POs are real B1 POs** (16 Oct 2026), so test-site captures and screenshots are real data too: never commit them.

| Fake value | Stands for |
|---|---|
| `2600001B` | a client internal number |
| `2600001B/048` | its PO number |
| `2600001B_048_1.pdf` | the PO PDF attached to the Note |
| `300001` | a Note ID |
| `pln_10001` | a project |
| `tsk_200001` | a task |
| `Lot 123 (#45) Sample Lane Sampleville 6000 WA` | a project address |
| `<project creator>`, `<user>` | a person's name |

Names kept as they are, because the agent uses them: the agent's account **Agent 1 (MySys Only)**, the pool **Agent Pool** (test) / **PO Allocation Pool** (live), the Creator **Perth Scheduling**, the company **B1 Homes**, the office **Prompt Engineering Pty Ltd**.

## How MySys behaves (every screen)

- **One page, many windows.** The page title changes with the module (`Test Prompt Engineering - Note Pool`, `- Projects`, `- Tasks`), but the URL stays `…view=management&tmpl=component`. Notes, projects, Create New Task, Hold Task and PDF previews open as **floating windows**, each with a heading and `Close` / `Maximize` / `Minimize` controls (role `generic`, names "Close", "Maximize", "Minimize"), and an entry in the bottom taskbar with its own "Close".
- **Minimised windows stay in the page.** Their controls are still in the DOM but hidden. **Scope every locator to its window** (by the window's heading, e.g. "Note 300001 …", "Create New Task", "Hold Task: tsk_200001"), and close the windows the agent opened when it's done with them.
- **Generated ids change on every load:** e.g. `#project_list_<digits>`, `[id="p_<digits>.<digits>"]`, `[id="<digits>.<digits>_s_po_1_6"]`. Never use them. Several fields have no accessible name and only got a position-based locator (marked **weak** below): the agent needs a locator anchored on the field's visible label inside its window.
- **Focus can land on a dangerous button.** After Assign re-renders the Note window, keyboard focus was on the assignee's **Unlink**. The agent never sends key presses to whatever has focus; it acts only through named, guarded locators.
- **Uploads:** the agent calls `set_input_files` on the file input. (While Playwright CLI is attached, clicking Upload opens no dialog: the file chooser is intercepted. That only affects mapping.)
- **A banner may say the connection is lost.** Through the whole M0b.1 session the page showed "Your internet connection appears to be disconnected. Any changes you make may not be saved.", even after a reload, while every action still worked. The agent ignores it and relies on its read-backs.
- **Empty lists say different things:** Note Pool "No record could be found."; Projects "No record found.".

### Danger: never press or target

| Control | Where | What it does |
|---|---|---|
| button "Discard" | Note window, Status buttons | Discards the Note |
| button "Unlink" (two of them after linking) | Note window: beside Assignee, and beside the project | Unassigns the Note (assignee becomes blank, no pool); removes the project link |
| button "Change Project" | Note window, after linking | Relinks the Note to another project |
| button "Pending" | Note window, once Solved | Reopens the Note |
| button "Cancel" | Project → task row | Cancels the task |
| button "Undo Cancellation" | Project → cancelled task row | Reinstates a cancelled task |
| button "Un-Hold" | Project → on-hold task row | Releases the hold |
| cell "close" (×) beside the attached file | Create New Task → PO Documents | Removes the document |
| "close" beside Task Client | Create New Task → Compaction Test | Clears the task client |
| any checkbox | Hold Task dialog (reminder, reset turn-around time, related tasks) | Changes the hold or holds other jobs |

Match these by **substring or regex, not exact name**: "Undo Cancellation" contains "Cancel", and Playwright's own locator for the task's Cancel needed `exact: true`. The spec's denylist (`docs/specs/spec.md` §5, v1.6) covers all of these, matched as substrings; v1.6 added **close**, which also covers the window Close controls (the agent reloads the page instead of closing windows). The Note Pool's Status filter lists a **Discard** option, so the agent leaves that filter at its default (Pending).

---

## Part 1 — Check the PO email

### Row 01 · Note Pool

Project (top tab) → **Note Pool**.

| Role | Accessible name | Locator | Notes |
|---|---|---|---|
| textbox | "Search/filter" | `getByRole('textbox', { name: 'Search/filter' })` | Free-text filter |
| combobox | (label "Assigned User") | `select[name="filter_user_id"]` (row 26) | Default **All Users** |
| combobox | (label "Assigned Pool") | `select[name="filter_allocation_pool_id"]` (row 26) | Default **All Pools**; options include **Agent Pool** |
| combobox | (label "Status") | `select[name="filter_status"]` (row 26) | Default **Pending**; also All Status, Solved, Discard (filter only: never choose Discard) |
| combobox | (label "Locked/Unlocked") | `select[name="filter_lock_status"]` (row 26) | Default **All**; also Locked, Unlocked |
| combobox | (labels "Creator", "Source", "Note Type") | `select[name="filter_creator_id"]`, `filter_source`, `filter_note_type` (row 26) | All on All |
| checkbox | "Filter No Company Note" | `getByRole('checkbox', { name: 'Filter No Company Note' })` | Unticked |
| button | "Refresh", "Reset Filter", "New Note" | by role and name | |
| button | "edit Batch Edit (0)" | | Disabled until rows are ticked; the agent never ticks rows |
| table | columns ID, Assignee, Project, Task, Company, Date, Source, Subject/Note, Status, Note Type | | One row per Note; a row checkbox in the first cell; the row opens the Note. **Newest first.** Subject/Note shows the title and body joined; Project, Task and Company read `---` until the Note is linked |
| combobox | page size | | Default **50**; footer "Page 1 of 1(N Items)" |

**Read:** find the Note's row by the subject text and take the **ID cell** (e.g. `300001`).
**Test-site findings:**
- The same PO can have **two Notes**: an older one titled only `Please find attached …` (title = body), and a newer one titled `[B1 Homes] Order 2600001B/048` with body `Please find attached …`; Subject/Note shows `[B1 Homes] Order 2600001B/048 Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf`. Filtering by Agent Pool can hide a copy assigned elsewhere. `SPEC.md` → MySys screen rules: the first copy processed is booked, any other skips `DUPLICATE_TASK`.
- A Note that is linked shows the project in the **Project** column and **B1 Homes** in **Company**; the **Task** column stays `---`.

### Row 02 · Note window

Opens from a Note Pool row. Heading **"Note 300001 - created on 12 Oct 2026"**; after linking it becomes **"Note 300001 - pln_10001 - created on …"** (seen when the window is reopened).

| Role | Accessible name | Locator | Notes |
|---|---|---|---|
| heading (3) | the Note title | | `[B1 Homes] Order 2600001B/048` (newer Notes, as on live) or `Please find attached …` (older Notes) |
| text | "Assignee:" + name | | e.g. **Agent Pool**, **Agent 1 (MySys Only)** |
| button | "Unlink" | `getByRole('button', { name: 'Unlink' })` | **Danger** |
| list | Logs | | Newest first: "16 Oct 2026 09:53 User Assigned: (By Agent 1 (MySys Only)) From X to Y", "Status changed: … From Pending to Solved" |
| textbox / button | "Add a comment...", "Add Comment" | | Not used |
| group "Status buttons" | buttons "Pending", "Solved", "Discard" | `getByRole('button', { name: 'Solved' })` | The current status's button is disabled. **Discard is danger** |
| combobox | user list (no name) | the select in this Note window that contains the option `--Select User--` (row 26) | **Pre-selects "Agent 1 (MySys Only)" even when the Note is in Agent Pool**: it doesn't show the assignee |
| combobox | pool list (no name) | the select in this Note window that contains the option `--Select Pool--` (row 26) | Default **--Select Pool--**; includes **Agent Pool** |
| button | "Assign" | `getByRole('button', { name: 'Assign' })` | |
| checkbox | "Send Email Notification" | `getByRole('checkbox', { name: 'Send Email Notification' })` | **Ticked every time a Note window opens.** The only screen where it appears |
| button | "Link to Project" | `getByRole('button', { name: 'Link to Project' })` | Replaced after linking (row 13) |
| text | Source, Created, Type, Status | | Status e.g. **Pending**, **Solved by Agent 1 (MySys Only)** |
| link | "Download document" | `getByRole('link', { name: 'Download document' })` | Next to the file name. The link's name is only "Download document": the **file name is in its URL** (`file_name=2600001B_048_1.pdf`). The file-name cell beside it shows the name on screen but has no accessible text |
| text | the Note body | | One line, below the attachment: `Please find attached Purchase Order / Quotation file 2600001B_048_1.pdf`. This is the "email body" for the task Note |

**Read:** title, body, file name, assignee, status.
**Opening a Note changes nothing visible:** no log line, no status change (check 3.5).

### Rows 03–04 · Assign the Note to the agent

Untick **Send Email Notification** → choose **Agent 1 (MySys Only)** in the user list → **Assign**.

**Read back:**
- "Assignee:" reads **Agent 1 (MySys Only)**.
- A new log line "User Assigned: … From X to Agent 1 (MySys Only)".
- Both lists reset to **--Select User--** / **--Select Pool--** and **Assign is disabled** until one is chosen again.
- With **Assigned Pool = Agent Pool**, the Note drops off the Note Pool list.
- Send Email Notification keeps the state it had (unticked if the agent unticked it).

The user list is a native select (about 330 users): the agent selects by option label without opening it.

### Row 05 · Download the PDF

Click **Download document** (or the file row). The file row also opens a **preview window**, heading **"2600001B_048_1.pdf"** with a "Previewing" marker and the PDF in an iframe; the download fires once or twice.

**Agent:** wrap the "Download document" click in `expect_download` and save the file; don't use the preview window. The link's URL carries a `user_note_id` that is **not** the Note ID (`…task=get_note_file_content&download=1&user_note_id=<n>&file_name=2600001B_048_1.pdf`).
**Downloading changes nothing on the Note** (check 3.5).

## Part 2 — Create the task

### Row 06 · Projects search

Projects (sub-tab, not Tasks) → type the internal number in **Search**.

| Role | Accessible name | Locator | Notes |
|---|---|---|---|
| textbox | "Search..." (label "Search") | weak: playwright gave `locator('#project_list_<digits>')…`, a generated id. The page header has a second, hidden "Search..." textbox | Scope to the Projects panel by the "Search" label |
| textbox | "Select..." (label "Company") | | Empty |
| combobox | Status, Eng Type, Sales Type | | **All Projects**, **All Eng Types**, **All Sales Types** |
| button | "Reset Filter" | | |
| table | columns Project No., Title, Client Ref No., Date In, Address, Status, Company, Completed | | |
| link | "pln_10001" | `getByRole('link', { name: 'pln_10001' })` | Opens the project |

**Read:** exactly one row; **Client Ref No.** = `2600001B`; **Company** = **B1 Homes**; **Address** = `Lot 123 (#45) Sample Lane Sampleville 6000 WA`. Footer "Page 1 of 1(1 Items)".
**No match:** see row 16.

### Row 07 · Project window

Heading **"pln_10001 B1 Homes Sample Lane, Sampleville WA 6000"** (with a `Client: B1 Homes` label).

| Role | Accessible name | Notes |
|---|---|---|
| combobox | "-- Select Task --" | Only the placeholder until the project has tasks |
| text | Title, Office, Created, Lodged By, **Client Internal No.**, Site Owner, **Address**, Estate, Shire, Latitude, Longitude; Soil block | Client Internal No. = `2600001B`; Address as in row 06 |
| link | "B1 Homes" (Project Company), `<project creator>` (Project Creator) | |
| button | "Tasks", "Stages", "Log", "Communication", "Documents", "Notes" | Tasks is shown by default |
| button | "Create New Task" | `getByRole('button', { name: 'Create New Task' })`: **the first write** |
| table | columns Lodged By, Task Creator, Create, Office, Stage, Owner, Turn Around Time, Days to Complete, Due Date, Price, Status | Each task takes two rows (below) |

**Each task in the table:** a header row with cell **"(tsk_200001) | Compaction Test"** plus its buttons, then a details row:

| Task state | Buttons in the header row | Status cell |
|---|---|---|
| Just created | **Cancel**, **Hold** | "New Project" (later "Inspection Analysis") |
| On hold | **Cancel**, **Un-Hold** | "On-hold Notes: ON HOLD UNTIL CALL UP" |
| Cancelled | **Undo Cancellation** | "Cancelled" |

**Read before any write (duplicate check):** every row whose header is "| Compaction Test". The project table shows the task number, type and status, **not the PO number**: to compare PO numbers the agent must open the task (open item).
The **Notes** tab lists linked Notes ("1 Notes"), each with its status and a **Manage Note** button (`getByRole('button', { name: 'Manage Note' })`).

### Row 08 · Create New Task (empty)

Window heading **"Create New Task"**.

| Role | Accessible name | Locator | Default |
|---|---|---|---|
| text | Office | | Prompt Engineering Pty Ltd (read-only) |
| checkbox | (label "Multiple Units") | weak: `getByRole('checkbox').nth(1)` | Unticked |
| text | Project Client | | B1 Homes (read-only) |
| combobox | (label "Creator") | weak: `locator('.controls > select')` | **The project's creator**, not Perth Scheduling (about 170 options) |
| checkbox ×4 | Sales Template Bundle: "- 0. Site Classification Bundle", "- 1.Single Storey Engineering Bundle", "- 2.Two Storey Engineering Bundle", "- 3. Architectural Drafting" | | Unticked |
| checkbox ×54 | Individual services, incl. **"- Compaction Test"** | `getByRole('checkbox', { name: '- Compaction Test' })` | Unticked. The four bundle names repeat here, so exact names aren't unique for them; "- Compaction Test" is |
| button | "Submit" | `getByRole('button', { name: 'Submit' })`, scoped to this window | **The write** |

**No Send Email Notification on this form** (check 3.3).

## Part 3 — Fill in the form

### Row 09 · Create New Task, Compaction Test ticked

Ticking **- Compaction Test** opens a sub-form under it. (**Creator** isn't in the sub-form: the only Creator field is the one in the Client section, row 08, set to **Perth Scheduling** in the walkthrough.)

| Field | Role / name | Locator | Default / value |
|---|---|---|---|
| Task Client | text "Same as Project", button "Select Client", "close" | `getByRole('button', { name: 'Select Client' })` | Same as Project. **The "close" clears it: never touch** |
| Task Name | textbox "Task Name" | `getByRole('textbox', { name: 'Task Name' })` | Empty |
| PO Number | textbox (no name) | weak: `div:nth-child(2) > .controls > input` | `2600001B/048` |
| PO Contact | combobox (no name) | weak | Choose... |
| **PO Documents** | "Upload" with button "Choose File" | weak: generated id `…_s_po_1_6` | After upload a table row: cell **"2600001B_048_1.pdf"** + cell **"close"** (removes it: **danger**) |
| Documents | "Upload" with button "Choose File" | weak: generated id `…_s_1_6` | A second, separate upload. The walkthrough used **PO Documents** |
| Sale Office | combobox | | **Prompt Engineering Pty Ltd** |
| Delivery Office | combobox | weak | Choose... |
| Note | textbox (no name) | weak: `[id="p_<digits>"] textarea` | **Empty in the walkthrough.** The SOP says Note = email body |

**Read back before Submit:** Creator = Perth Scheduling; Compaction Test ticked and **nothing else ticked**; PO Number; the file name in the PO Documents table; Note = email body; Task Client = Same as Project. Any mismatch → close the browser context (`WRITE_NOT_STARTED`).

### Row 10 · After Submit

The Create New Task window closes. On the project, a new task: header **"(tsk_200001) | Compaction Test"** with **Cancel** and **Hold**; details: Lodged By **Agent 1 (MySys Only)**, Task Creator **Perth Scheduling**, today's date, Office **Prompt Engineering Pty Ltd**, Turn Around Time "0 Days", Days to Complete "2 Days", a due date, a price, Status **New Project**.

**Read back:** a new Compaction Test task on this project, Task Creator = Perth Scheduling, and its task number (needed for Hold). **PO number and document aren't shown in this table:** open the task to read them back (open item).

### Row 11 · Hold Task dialog

The task row's **Hold** opens window **"Hold Task"** with heading **"Hold Task: tsk_200001"**.

| Field | Role / name | Default |
|---|---|---|
| Confirm | button "Hold", top right beside the heading | Two "Hold" buttons are now on the page (this one and the task row's). Playwright could only tell them apart by generated id: **scope to the dialog with heading "Hold Task: tsk_200001"** |
| Active task after selected task complete | combobox | Choose... |
| Active task after this task changed task owner | combobox | Choose... |
| Reminder Email Setting | checkbox **"Send me a reminder email every days"** + spinbutton | **Ticked, with 0** ("0 days = no email reminders") |
| | checkbox "Send me a reminder email at this date:" + date box | Unticked; date box disabled |
| Reset turn around time | checkbox | Unticked |
| Note | textbox "Note" | `getByRole('textbox', { name: 'Note' })`: type **ON HOLD UNTIL CALL UP** |
| Hold Image | "Upload Image" / "Choose File" | Not used |
| Related Tasks | "There are N related jobs with the same sales type/ suburb/ estate. Select jobs to hold together." + a table with a Select-all checkbox and one checkbox per job | **All unticked** (58 jobs on the walkthrough project) |

**The agent touches no checkbox here** (Must never #2). **Read before confirming:** the heading names its own task number; every Related Tasks checkbox and the reset checkbox are unticked; the reminder is ticked with **0**; Note = "ON HOLD UNTIL CALL UP". Anything else → close the browser context.
No Cancel or Discard in the dialog: its only exits are Hold and the window controls.

### Row 12 · After Hold

The dialog closes. The task's header row now has **Cancel** and **Un-Hold**; Turn Around Time "0 Days (On Hold: 0 Days)"; Status **"On-hold Notes: ON HOLD UNTIL CALL UP"**. The Tasks module list shows Status **On-hold** for the same task.

**Read back:** the row for *this* task number has **Un-Hold** and a status starting **"On-hold"** with the hold note.

## Part 4 — Link and mark Solved

### Row 13 · Link to Project

On the Note: **Link to Project** → search the project → select. (The search and result screens weren't captured; only the result.)

After linking, in the Note window:
- "Link to Project" is replaced by button **"pln_10001"**, button **"Change Project"** (danger) and a second **"Unlink"** (danger). Both Unlinks now share the name: `getByRole('button', { name: 'Unlink' })` matches two.
- Status stays **Pending**; Send Email Notification is still ticked.

In the Note Pool: Project = **pln_10001**, Company = **B1 Homes**, **Task = `---`**. This screen links the Note to the project only, not to the task.

**Read back:** the Note's project button is **pln_10001** (the project just booked).

### Row 14 · Solved

There is **no Resolve button** on the test site. Press **Solved** in the Note's Status buttons.

**Read back:**
- Status reads **"Solved by Agent 1 (MySys Only)"**.
- New log line "Status changed: (By Agent 1 (MySys Only)) From **Pending** to **Solved**".
- **Solved** is disabled and **Pending** is enabled (Pending would reopen it: danger).
- The Note leaves the Pending list ("No record could be found." when searched).
- On the project's Notes tab the Note shows **Solved**.

No Send Email Notification appears with Solved.

## Off the happy path

### Row 15 · Note back to the pool (the skip path)

On the Note: choose **Agent 1 (MySys Only)** → **Assign**; then choose **Agent Pool** in the pool list → **Assign**. No Unassign or Unlink needed (check 3.2).

**Row 15b (M0b.1):** one Assign with `--Select User--` + **Agent Pool** does the same from a freshly opened window; the agent uses that.

**Read back:** log line "User Assigned: … From Agent 1 (MySys Only) to **Agent Pool**"; "Assignee:" reads **Agent Pool**; Status still **Pending**; Note Pool Assignee column **Agent Pool**; lists reset and Assign disabled.

### Row 16 · Projects search, no match

Search an internal number that doesn't exist: no project rows, no pager, the text **"No record found."** in the list area. Playwright's locator (`getByText('No record found. Project No.')`) includes a hidden header and is brittle: match the exact text inside the Projects panel.

**Agent rule:** wait for the search to finish, then: no `pln_` row **and** "No record found." → `PROJECT_NOT_FOUND`.

### Rows 17–18 · not captured

Row 17 (a Create New Task error) was skipped as optional. Row 18 (a cancelled task) is covered by the cancelled task seen in rows 09–10 (table in row 07).

## Slice M0b.1: moving between screens, anchors, searches (25 Oct 2026)

Joey clicked in the Playwright window, logged in as the agent; Claude observed only. Fake values as above (`300001`, `300002` are two Note IDs).

### Row 26 · Anchors for controls with no name

| Screen | How the agent finds it | Notes |
|---|---|---|
| Login page | Page title `Test Prompt Engineering - Login`; textbox "Username", textbox "Password", button "Log in" | All three have names and are unique. A "Microsoft account login" link is there too: never used |
| Module tabs | Project (top menu) → the section tab bar `#dash_board_section_buttons` (a fixed id, no digits) → the tab by exact text ("Projects", "Note Pool") | The tabs are `generic` elements with text, not buttons. **After a reload the page lands on Dashboard and the tab bar is hidden until Project is clicked** (Joey, row 27) |
| Note Pool panel | No heading; its container id is generated (`#user_note__<digits>`). Anchor: the panel that holds button "New Note" **and** textbox "Search/filter" | Filters: each select has a fixed `name` (row 01). Page size: the select in the footer (`.limit > select`) |
| Projects panel | No heading; container id generated (`#project_list_<digits>`). Anchor: the panel that holds the label "Search", button "Reset Filter" and the Status select with option **All Projects** | Its textbox is named "Search...", like the page header's search box: always scope it to this panel. Its selects (Status, Eng Type, Sales Type) have no name; the agent never changes them. **No Refresh button** |
| Note window user list | Inside the window scoped by heading `Note <id> - …`: the select that contains the option `--Select User--` | Next to the pool list and **Assign** |
| Note window pool list | Same window: the select that contains the option `--Select Pool--` | |
| Taskbar | Bottom bar, one entry per open window: a `paragraph` with the window's heading text (`Note 300001 - created on …`, `pln_10001…`), with its own "Close" beside it | Entry ids are generated (`…__dockTabText`) |

**Danger seen again:** "close" beside Company in both the Note Pool and the Projects panel (clears the company filter); **Unlink** beside "Assignee:" in the Note window; Discard; each window's and each taskbar entry's Close. All are on the denylist.

### Row 27 · The Note Pool after a filter change, a search, a reload and a login

| Action | What happened |
|---|---|
| Change **Assigned Pool** to Agent Pool | The list **reloads by itself** (29 rows → 2); no Refresh needed. The footer "Page 1 of 1(N Items)" updates with it |
| Put a Note ID into **Search/filter** with no key press (pasted) | **Nothing happens while the box keeps focus.** The search runs only when focus leaves the box (a click elsewhere), then the list shows the one row (`(1 Items)`) |
| Search/filter, then the panel's **Refresh** | Filtered, but the **same Note showed twice** in the table while the footer said `(1 Items)` (two searches, one from leaving the box and one from Refresh, both added rows). A second Refresh: one row |
| Reload the page (F5) | Still logged in; the page lands on **Dashboard**; **every open window is gone**; the Note Pool tab appears after clicking Project. **The filters and the Search/filter text persist** (Agent Pool and the Note ID were still set) |
| Log out and log in again | Every filter back to its default (All Users, All Pools, Pending, All) and Search/filter empty |

**Answer: `fill` alone does not run the Note Pool search.** `fill` sets the text without moving focus, and the search runs when focus leaves the box. The agent fills, then clicks **Refresh** (a guarded click that also moves focus), as in `SPEC.md` → MySys screen rules.
**Not mapped:** whether `fill` alone runs the **Projects** search (row 06; Joey typed and the list was shown). The Projects panel has no Refresh button; task 1.8 or 3.2 tests it (see `SPEC.md`).

### Row 25 · Note window → Projects → project window → back to the Note

1. With Note `300001`'s window open, the **Projects** tab: the Note window **stays open and on top**, covering most of the Projects results (the `pln_10001` link is mostly hidden behind it). The Search box above stays visible.
2. Joey minimised the Note window, then opened `pln_10001`: the project window opens; the minimised Note window stays in the page (hidden) and in the taskbar.
3. Clicking the taskbar entry `Note 300001 - created on …` brings back **the same Note window** (same state, not reopened).

**For the agent:** it never clicks Minimize or a taskbar entry. It reloads `base_url` after the Note-window steps (windows gone, nothing in MySys changes), does the Projects search and project reads, then reloads again and reopens the Note from the Note Pool (`SPEC.md` → MySys screen rules → Moving between windows).

### Row 28 · Opening a project that's already open

Clicking `pln_10001` again while its window is open: **still one window** and one taskbar entry. No second copy.

### Row 15b · Returning a Note from a freshly opened window

The Note was assigned to Agent 1 (one Assign, Send Email unticked). Page reloaded, Note reopened from the Note Pool: user list **pre-selects Agent 1 (MySys Only)**, pool list `--Select Pool--`, **Send Email Notification ticked again**. Untick it, choose `--Select User--` and **Agent Pool**, **one Assign**:
- "Assignee:" reads **Agent Pool**; new log line "User Assigned: … From **Agent 1 (MySys Only)** to **Agent Pool**".
- Both lists reset (`--Select User--`, `--Select Pool--`), Assign disabled, Send Email stays unticked.

**Answer: one Assign is enough** (`--Select User--` + pool). The walkthrough's two Assigns (row 15) aren't needed.

### Rows 21–23 · not mapped in M0b.1

- **Rows 21–22** (a Note with no attachment, one with two PDFs) were dropped for the MVP (decisions, 25 Oct 2026): no such Notes were made. `SPEC.md` → Attachment and download sets the rule without them: exactly one "Download document" link whose URL `file_name` ends `.pdf`, else skip.
- **Row 23** (does an open Note window refresh its Assignee after someone else reassigns it) moves to **M0b.2**, before task 3.6. The Note Pool search by Note ID under All Pools is mapped in row 27.

---

## Live vs test

| | Test site | Live (from `docs/decisions.md`; no live captures yet) |
|---|---|---|
| URL | `test-prompt.mysys.com.au` | `prompt.mysys.com.au`: the MVP never touches it |
| Pool | **Agent Pool** | **PO Allocation Pool** |
| Locked filter | Default All; the SOP applies Locked | Locked |
| Note title | Both `[B1 Homes] Order 2600001B/048 Please find attached …` and plain `Please find attached …` | Always `[B1 Homes] Order 2600001B/048` |
| Source | Agent 1 (MySys Only) | The sender's email |
| Duplicate Notes for one PO | Seen (two per PO) | Unknown |
| Last step | **Solved** (no Resolve button) | **Unknown: check in Stage 3B** whether live has Resolve |
| Login | Username, Password, "Log in"; also a "Microsoft account login" link. No MFA step seen | Not checked |
| Everything else | As mapped | Assumed the same; not verified |

## Open items

1. ~~Duplicate Notes per PO~~ **Done:** the first copy processed is booked, any other skips `DUPLICATE_TASK` (`SPEC.md` → MySys screen rules → Note Pool).
2. **Read back PO number and document after Submit:** they aren't in the project's task table; the task detail screen is mapped in **slice M0b**. Until then the MVP's duplicate check counts any non-Cancelled Compaction Test task.
3. **Note field and upload:** Note = the Note's body (`SPEC.md` → MySys screen rules). Upload: SPEC uses **PO Documents**, as in the walkthrough; PO admin to confirm (`SPEC.md` open question 11).
4. **Creator** ~~and PO Number~~: one Creator field (row 08), set to Perth Scheduling. Whether PO Number is prefilled: **slice M0b** (the agent's fill replaces any prefill anyway).
5. **Link to Project search screens** (row 13) weren't captured: **slice M0b**.
6. **Note-to-task link:** the Note links to the project only (Task `---`). That's what `SPEC.md` S4 checks.
7. ~~Denylist additions~~ **Done:** Pending, Undo Cancellation, Un-Hold and Change Project are in the spec's denylist (v1.5) and `SPEC.md` → Never (v1.9).
8. **Weak locators to anchor on labels:** ~~Assigned Pool / Status / Locked filters, the Note window's user and pool lists, Projects search~~ (done in M0b.1, row 26); still open for **slice M0b.2**: Creator, Multiple Units, PO Number, PO Contact, Delivery Office, Note, both Choose File inputs, the Hold confirm button.
9. **Live:** pool, title, Locked filter, whether a Resolve button exists, and which Projects search column ends with `/048` (3–4 results per internal number on live; Stage 3B).
10. ~~Notes with no attachment or two attachments~~ **Done without mapping:** the attachment rule in `SPEC.md` (decisions, 25 Oct 2026). Whether an open Note window refreshes its Assignee (row 23): **slice M0b.2**, before task 3.6.
