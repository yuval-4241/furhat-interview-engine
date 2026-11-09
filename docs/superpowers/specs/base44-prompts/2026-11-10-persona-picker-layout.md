# Base44 prompt — persona picker layout with robot photo (2026-11-10)

Paste everything inside the fence into Base44's AI builder.

```
Redesign step 5 "דמות" (Robot persona) of the New Session wizard. Replace the dropdown with a list of persona cards, one card per active Persona, and the researcher clicks a card to choose it.

## 1. New Persona fields
- `face_image`: image upload, optional. Label: "תמונת הרובוט". A screenshot of the robot's face with this persona.
- `persona_type`: string, optional. Label: "סוג פרסונה" (free text, e.g. "מראיין גבר", "מראיינת אישה").
Add both to the Persona form and the Persona list page. Do not change any existing field.

## 2. Card layout (right-to-left)
Each card shows, one item per row:
- שם הדמות: <name>
- קול: <furhat_voice label, e.g. "Avri – male">
- סוג פרסונה: <persona_type>
Next to the text (on the left side of the card), show the `face_image` as a square thumbnail about 96x96 px with rounded corners. If there is no image, show a grey placeholder with a robot icon.
The selected card gets a highlighted border and a check mark. Save the chosen Persona's id in the Session's existing `persona` field, exactly as the dropdown does today.
```
