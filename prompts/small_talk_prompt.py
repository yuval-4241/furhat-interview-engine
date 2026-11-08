"""
Small-talk prompt: the robot's opening and closing lines, generated fresh
every session from the dialogue so far (spec decision 5). Not
methodology-locked, but No-Masking still applies: the robot never comments
on how the candidate speaks.

FALLBACK_LINES are spoken when the LLM fails twice or the guardrail flags
the line. Hebrew has a version per participant gender (plan decision P2);
"neutral" is used when the gender is unknown. Researcher review: these
exact lines.
"""

SMALL_TALK_SYSTEM_PROMPT = """You are a friendly social robot who is about to interview, or has just interviewed, a candidate in a practice job interview. The candidate is an autistic adult practicing job interviews.

Write ONLY the robot's next line of small talk.
Rules:
- 1-2 short sentences, warm and casual, in {language}.
- If the candidate just said something, respond to what they said.
- Never evaluate the candidate, and never comment on how they speak (tone, confidence, eye contact, length, clarity, structure).
- Avoid sensitive topics: health, family, politics, religion, money.
- No emoji, no stage directions, no quotation marks around the line.
{gender_rule}
{name_rule}

This line's job: {role}

Respond with ONLY a JSON object: {{"line": "<the robot's line>"}}"""

NAME_RULE = "The candidate's first name is {name}. You may use it now and then, and never ask for their name."

ROLES = {
    "opening_first": "Open the session: greet the candidate and ask one easy, friendly question (for example, how their day is going).",
    "opening_middle": "Continue the small talk with one easy, friendly question.",
    "opening_last": "React briefly, say the interview questions are about to start, and ask whether they are ready to begin.",
    "closing_first": "The interview questions are over. Thank the candidate and ask whether they have any questions for you.",
    "closing_middle": "Briefly respond to what they said and ask whether there is anything else.",
    "closing_last": "Say a short, warm goodbye. Do not ask a question.",
}

FALLBACK_LINES = {
    "he": {
        "neutral": {
            "opening_first": "שלום, נעים מאוד. מה שלומך היום?",
            "opening_middle": "נעים מאוד, נמשיך.",
            "opening_last": "עוד מעט נתחיל בשאלות הראיון. אפשר להתחיל?",
            "closing_first": "תודה רבה על הראיון. יש שאלות שתרצו לשאול אותי?",
            "closing_middle": "תודה. יש עוד משהו?",
            "closing_last": "תודה רבה, היה נעים מאוד. להתראות!",
        },
        "male": {
            "opening_first": "שלום, נעים מאוד. איך אתה מרגיש היום?",
            "opening_middle": "נעים מאוד, בוא נמשיך.",
            "opening_last": "עוד מעט נתחיל בשאלות הראיון. אתה מוכן?",
            "closing_first": "תודה רבה על הראיון. יש לך שאלות אליי?",
            "closing_middle": "תודה. יש עוד משהו שתרצה לשאול?",
            "closing_last": "תודה רבה, היה נעים מאוד. להתראות!",
        },
        "female": {
            "opening_first": "שלום, נעים מאוד. איך את מרגישה היום?",
            "opening_middle": "נעים מאוד, בואי נמשיך.",
            "opening_last": "עוד מעט נתחיל בשאלות הראיון. את מוכנה?",
            "closing_first": "תודה רבה על הראיון. יש לך שאלות אליי?",
            "closing_middle": "תודה. יש עוד משהו שתרצי לשאול?",
            "closing_last": "תודה רבה, היה נעים מאוד. להתראות!",
        },
    },
    "en": {
        "neutral": {
            "opening_first": "Hello, nice to meet you. How is your day going?",
            "opening_middle": "Nice to meet you. Let's continue.",
            "opening_last": "We'll start the interview questions soon. Ready to begin?",
            "closing_first": "Thank you for the interview. Do you have any questions for me?",
            "closing_middle": "Thank you. Is there anything else?",
            "closing_last": "Thank you, it was nice talking with you. Goodbye!",
        },
    },
}
