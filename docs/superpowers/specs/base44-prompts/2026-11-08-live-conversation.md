# Base44 prompt — Live sessions run by the robot (2026-11-08)

Paste everything inside the fence into Base44's AI builder. Skip section 6
if the Persona dropdowns are already in place.

```
In Live sessions the robot now runs the conversation itself: it says each line, listens to the participant through its own speech recognition, and the external Engine writes the transcripts. Keep the rule that this app is frontend + database only. Simulation and Mock sessions must keep their current flow exactly as it is today.

## 1. New Turn fields
- `skip_reason`: string
- `robot_line`: string (what the robot said after the participant's answer)
- `engine_model`: string (which language model the Engine used for this turn)
In Live sessions the Engine now writes `participant_answer` and `participant_pe_answer` (speech-recognition transcripts) and `question_text` for Opening/Closing turns.

## 2. Turn.status values
Add these values to the Turn.status enum and keep every existing value: `queued`, `robot_speaking`, `listening`, `pe_listening`, `robot_feedback`, `skipped`.
Make sure `pe_result` allows `Correct`, `Partial`, `Wrong`.

## 3. Creating turns
When a Live session starts, create its turns exactly as today, but with status `queued` instead of `awaiting_answer`. Simulation and Mock: unchanged.

## 4. Live session screen (Live mode only)
- The researcher does not type answers in Live mode. Hide the answer and PE-answer text boxes and the "Send to Engine" button. Show `participant_answer` and `participant_pe_answer` read-only as "What the participant said".
- Do not create `say` RobotCommands in Live sessions, and hide any "read question aloud" button: the Engine makes the robot say every line itself.
- Status labels:
  queued = "Waiting", robot_speaking = "Robot is speaking", listening = "Robot is listening", engine_processing = "Processing", awaiting_approval = "Needs your approval", robot_reacting = "Robot is reacting", pe_listening = "Listening for the PE answer", awaiting_feedback = "Feedback needs your approval", robot_feedback = "Robot is giving feedback", done = "Done", skipped = "Skipped".
- awaiting_approval: as today. Show the transcript, the emotion and the editable reply. Approve sets `final_reply` and status `robot_reacting`.
- awaiting_feedback: show `participant_pe_answer`, `pe_result` (the researcher may change it to Correct / Partial / Wrong), `pe_explanation`, and an editable `final_feedback` prefilled from `proposed_feedback`. In Live mode, Approve sets `final_feedback` and status `robot_feedback`. In Simulation it stays as today.
- skipped: show the turn greyed out with the reason in plain words: no_answer = "No answer (silence)", no_recognition = "Speech not recognized", pe_no_answer = "No answer to the PE question", pe_no_recognition = "PE answer not recognized", researcher = "Skipped by researcher".
- If `engine_error` is not empty, show it in red with a Retry button. Retry sets `engine_error` to an empty string and does NOT change the status.
- Add a "Skip this turn" button on the current Live turn when its status is `queued`, `awaiting_approval` or `awaiting_feedback`, or when `engine_error` is not empty. It sets status `skipped`, `skipped = true`, `skip_reason = "researcher"`.
- Show `robot_line` under the transcript as "Robot said", and `engine_model` as a small grey label.

## 5. Participant gender and first name
Add two optional fields to the Participant entity:
- `gender`: enum `Male`, `Female`. Label: "Gender (how the robot addresses the participant)".
- `first_name`: string. Label: "First name (the robot uses it in small talk only)".
Show both in the participant form and the participant list. Existing participants keep them empty until the researcher fills them in.

## 6. Persona (skip if already done)
In the Persona form, make `furhat_voice` a dropdown: AvriNeural ("Avri – male"), HilaNeural ("Hila – female"), Hila:DragonLatestNeural ("Hila HD – female"). Make `furhat_face` a dropdown: Alex, Brooklyn, Chen, Dorothy, Expresivo, Fedora, Fernando, Gyeong, Hayden, Isabel, James, Jamie, Jane, Kione, Lamin, Marty, Maurice, Nazar, Omar, Patricia, Rania, Samuel, Titan, Vinnie, Yi, Yumi, Zhen. Both are optional (empty = robot default). Values are stored as plain strings with the same field names.

## 7. Documentation
Regenerate the OpenAPI file and give me the updated field table for Turn (exact field names, types and enum values).
```
