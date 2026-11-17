# Base44 prompt — Persona management screen (2026-11-09)

Paste everything inside the fence into Base44's AI builder.

```
The researcher needs to see, edit and choose the robot's Persona (its face and voice). Today there is no way to do this in the app, and the existing Persona records hold voice names the robot does not have, so the robot cannot speak. Keep the rule that this app is frontend + database only.

## 1. Persona screen
Add a "Robot personas" page to the main navigation (Hebrew label: "פרסונות של הרובוט"). It lists every Persona with its name, face and voice, and has "Add persona" and "Edit" buttons.

## 2. Persona form
Fields:
- `name`: string, required.
- `furhat_voice`: dropdown, required. Options (stored value → label):
  AvriNeural → "Avri – male", HilaNeural → "Hila – female", Hila:DragonLatestNeural → "Hila HD – female".
- `furhat_face`: dropdown, optional (empty = robot default). Options: Alex, Brooklyn, Chen, Dorothy, Expresivo, Fedora, Fernando, Gyeong, Hayden, Isabel, James, Jamie, Jane, Kione, Lamin, Marty, Maurice, Nazar, Omar, Patricia, Rania, Samuel, Titan, Vinnie, Yi, Yumi, Zhen.
Store the values as plain strings in the existing fields `furhat_voice` and `furhat_face`. Do not rename the fields.

## 3. Fix the existing records
Update the existing Persona records once:
- Daniel: `furhat_voice` = AvriNeural, `furhat_face` = Isabel.
- Noa: `furhat_voice` = HilaNeural, `furhat_face` = Isabel.
If any other Persona has a `furhat_voice` that is not one of the three dropdown values, show a red "Invalid voice – choose again" badge next to it in the list.

## 4. Choosing a persona for a session
In the new-session form, for Live sessions, add a required "Robot persona" dropdown listing all Personas by name, showing the voice next to the name (e.g. "Daniel – Avri, male"). Save the chosen Persona's id in the Session's existing `persona` field. On the Live session screen, show the chosen persona's name, face and voice in the header.

## 5. Documentation
Regenerate the OpenAPI file and give me the field table for Persona and Session (exact field names and types).
```
