# Conversation Engine v1

Synthetic-tested evaluator pipeline for a Furhat social robot job-interview
training system. Combines: synthetic participant simulation, LLM response
evaluation, a No-Masking guardrail, a VA-matched response bank, and a
human review queue — into one runnable pipeline.

See `CLAUDE.md` for build instructions and current status.

## Setup

```bash
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
export LAB_LLM_TOKEN="your_token"   # get from Tomer
```

## Status
Day 1 in progress — see CLAUDE.md for task list.

## הדגמת שיחה חיה עם הרובוט

### התקנה (פעם אחת)
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
ואז למלא ב-`.env`: `OPENAI_API_KEY`, ו-`GOOGLE_SPEECH_API_KEY` (מפתח API
רגיל מ-Google Cloud Console -> APIs & Services -> Credentials, מוגבל
ל-Cloud Speech-to-Text API בלבד). לא נדרש קובץ service-account —
השיחה החיה פונה ל-REST API של Google ישירות עם המפתח.

### הפעלה
```bash
./run.sh
```
הסקריפט בונה את הסקיל, מחכה שתטעני ותריצי אותו בדשבורד של Furhat (צעד
ידני — אין דרך לעשות את זה דרך שורת פקודה), ואז פותח את ממשק השיחה.

### מבנה הממשק
- **שיחה חיה** — מתחילים כאן: קוד משתתף + מספר מפגש + שפת הראיון
  (עברית/English, קובעת גם את שפת הזיהוי הקולי וגם את שפת הדיבור של
  הרובוט) + קול הרובוט (אישה/גבר), כפתור ירוק להתחלה. שאלות "מרכזיות"
  (behavioral/self-reflection) מקבלות תגובה רגשית מהרובוט ואז שאלת
  פרספקטיבה; שאר השאלות — רק אישור.
- **היסטוריה** — כל השיחות השמורות, עם ייצוא ל-CSV.
- **הגדרות** — סטטוס מפתחות (בלי לחשוף ערכים) + בדיקת חיבור לרובוט.
