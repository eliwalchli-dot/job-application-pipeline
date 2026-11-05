# Activating Deep Research in the Gemini web app

Stage 3 (research) runs in the Gemini app, not the API — it's free under the Pro
subscription. Deep Research must be turned on **manually for each new conversation**, or
Gemini just answers normally and the output is invalid. These steps match the Gemini UI as
of June 2026 (from Eli's screen recording); the layout may shift over time.

## Steps

1. **Start a new conversation** at `https://gemini.google.com/app`. One job per
   conversation — don't reuse a thread. (We prompt Deep Research directly rather than
   using a custom gem, for full control over the prompt and research plan.)

2. **Click the `+` button** at the left end of the prompt box (the "Ask Gemini" bar).

3. In the menu, hover **"More tools"** (bottom of the list, has a `>` arrow).

4. Click **"Deep research."**

5. **Confirm it's active.** Two tells:
   - A **"Deep research" chip** now sits inside the prompt bar (next to the `+`), and the
     placeholder changes to **"What do you want to research?"** with **Sources** and
     **Files** buttons underneath.
   - If you reopen `+ → More tools`, **"Deep research" has a checkmark** next to it.

6. **Leave the model on "Pro"** (3.1 Pro). Deep Research works with it; you don't need to
   change the model dropdown.

7. **Paste the prompt** from `research_prompt.txt` and send. The send arrow turns into a
   **stop square (■)** and a **`...`** indicator appears while it researches — that's the
   sign it actually engaged. A real run takes several minutes and shows a research plan /
   sources panel.

8. **Optional:** use **Sources** to constrain where it looks, or **Files** to attach a
   document (e.g., the job description PDF) as context.

## Valid vs. invalid run

- **Valid:** the "Deep research" chip was showing when you sent, the stop square + `...`
  appeared, and you get a multi-section report with sources after a few minutes.
- **Invalid:** Gemini replies in a few seconds with no research panel and no sources —
  Deep Research wasn't on. Start a **new** conversation, re-activate it (steps 2–5), and
  resend.

## Then

Copy the finished report into the company's `research_brief.md`
(`data/research_cache/<company-slug>/research_brief.md`), then run
`generate_cover_letter.py --research <that file>`.
