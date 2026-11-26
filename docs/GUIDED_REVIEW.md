# Guided incident review (v1.6)

The review workspace now separates three decisions into a guided flow. Saved annotations and backend validation are unchanged. Unsaved edits are kept when switching sections or cases in the same loaded page; reloads do not persist browser drafts.

## 1. Read incident

Choose an incident and read its evidence, source location, and reported recovery. **Open original report** opens the source in another tab. Resolve any date discrepancy using the date-review control in this section. Then choose **Continue to label review**.

## 2. Review label

The label is the single action used in the accuracy benchmark. Choose one label decision:

- **Keep the original label** if the source supports that coarse mapping.
- **Choose a different label** and select a replacement when the original is inappropriate.
- **I need more information** to leave it flagged and unresolved.

Enter your name and explain the evidence from this specific incident. Click **Save label decision**. The app saves that decision and opens recovery review. It does not approve the recovery plan. Previous decisions remain under a history control.

## 3. Review recovery

Read the numbered reference steps and their prerequisites. Source-based starter drafts remain explicitly unapproved. Use **Edit the reference steps** only when the reference needs changing: choose an action from the menu, write its description, and tick earlier steps that must happen first. Add or remove the last step using the controls. No action codes or pipe-delimited text are needed.

Enter your reviewer name, explain why the plan fits the report, and check its supporting source URL. Click **Save recovery approval** to accept the plan, or **Needs more investigation** to flag it. The single-action label decision is unchanged. Draft source text is not automatically copied into your review explanation.

The status strip reports **Label** and **Recovery** independently. A case is complete when its label is accepted/corrected, any date discrepancy is resolved, and any required recovery plan is accepted. Use **Next case** after completion, or **Save for later · next case** to move on while retaining drafts within the loaded page.

## Optional checker

**Optional: try a proposed sequence** is a separate practice area. Use its action menus and **Add proposed action** control to build a candidate sequence, then choose **Check this sequence**. Missing steps, extra actions, and prerequisite-order violations are reported in plain language.

Changing the practice sequence does not edit the reference plan. Its comparison uses the saved reference or clearly marked source draft, excluding unsaved reference edits. A matching result is not an approval, a verified operational diagnosis, or evidence that the steps have been executed. Changing a candidate action clears the previous result so it does not appear to describe the new input.

## Finish a dataset

The reviewed-version section lists remaining **label decisions**, **incident dates**, and **recovery plans** separately. **Continue reviewing** opens the first unresolved case at the appropriate section. When all required decisions are complete, create the new frozen reviewed version. Original records and previous experiment results remain preserved.

On narrow screens, navigation labels stay visible in a horizontal menu. The case list is compact, review sections stack vertically, and approval controls remain separate from optional checking controls.
