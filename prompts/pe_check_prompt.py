"""
PE judge prompt (spec, "New prompts" 4; integration spec "PE grading of
near-synonyms"). Grades the emotion the participant named, not their
reason and not their wording.

Families follow Shaver, Schwartz, Kirson & O'Connor (1987): HAPPINESS,
EXCITED and CALM share the joy family; ANGER, CONTEMPT and DISGUST share
the anger family. BORED and SLEEPY are not in Shaver; they are treated as
one low-energy family. A word in the target's family that sits closer to
a DIFFERENT emotion the robot can show is Partial.

DRAFT word lists -- the researcher must review them before any participant
session (plan decision P11). The lists are examples, not exhaustive.
"""

HEBREW_NAMES = {
    "ANGER": "כעס", "CONTEMPT": "בוז", "DISGUST": "גועל", "FEAR": "פחד",
    "HAPPINESS": "שמחה", "SADNESS": "עצב", "SURPRISE": "הפתעה",
    "EXCITED": "התלהבות", "BORED": "שעמום", "SLEEPY": "עייפות", "CALM": "רוגע",
}

WORD_LISTS = {
    "HAPPINESS": {"correct": ["שמח", "מאושר", "נהנה", "מרוצה", "טוב לך", "חייכת", "גאה"],
                  "partial": {"EXCITED": ["מתלהב", "נלהב", "נרגש"], "CALM": ["רגוע", "שליו", "נינוח"]}},
    "EXCITED": {"correct": ["מתלהב", "נלהב", "נרגש", "להוט", "מלא אנרגיה"],
                "partial": {"HAPPINESS": ["שמח", "מאושר", "מרוצה"]}},
    "CALM": {"correct": ["רגוע", "שליו", "נינוח", "בנחת", "משוחרר"],
             "partial": {"HAPPINESS": ["שמח", "מרוצה"]}},
    "ANGER": {"correct": ["כועס", "עצבני", "מתוסכל", "מרוגז", "זועם", "נרגז"],
              "partial": {"CONTEMPT": ["מזלזל", "בז"], "DISGUST": ["נגעל"]}},
    "CONTEMPT": {"correct": ["בוז", "מזלזל", "מתנשא", "לא העריך", "בז"],
                 "partial": {"ANGER": ["כועס", "עצבני"], "DISGUST": ["נגעל"]}},
    "DISGUST": {"correct": ["נגעל", "גועל", "סלידה", "דחייה", "מגעיל"],
                "partial": {"CONTEMPT": ["מזלזל", "בז"], "ANGER": ["כועס"]}},
    "FEAR": {"correct": ["פוחד", "מפחד", "חושש", "דואג", "לחוץ", "מודאג", "חרד", "נבהל"],
             "partial": {}},
    "SADNESS": {"correct": ["עצוב", "מאוכזב", "מצטער", "מדוכדך", "מבואס", "אכזבה"],
                "partial": {}},
    "SURPRISE": {"correct": ["מופתע", "הופתע", "נדהם", "המום", "לא ציפה"],
                 "partial": {}},
    "BORED": {"correct": ["משועמם", "שעמום", "לא מעניין", "אדיש", "חוסר עניין"],
              "partial": {"SLEEPY": ["עייף", "ישנוני"]}},
    "SLEEPY": {"correct": ["עייף", "ישנוני", "מנומנם", "רדום", "מותש"],
               "partial": {"BORED": ["משועמם", "אדיש"]}},
}


def _word_list_text() -> str:
    lines = []
    for target, lists in WORD_LISTS.items():
        line = f"- {target} ({HEBREW_NAMES[target]}): Correct: {', '.join(lists['correct'])}"
        if lists["partial"]:
            closer = "; ".join(f"{', '.join(words)} (closer to {other})"
                               for other, words in lists["partial"].items())
            line += f" | Partial: {closer}"
        lines.append(line)
    return "\n".join(lines)


PE_CHECK_SYSTEM_PROMPT = (
    "You grade a perspective-taking exercise. A social robot interviewer showed an emotion "
    "on its face. The participant was asked \"What do you think I felt, and why?\" and "
    "answered freely, usually in Hebrew.\n\n"
    "Grade ONLY the emotion the participant named or described, against the TARGET emotion:\n"
    "- \"Correct\": the core word for the target, a clear synonym, or a description of the "
    "target emotion through what happened (for example \"you smiled because I said I "
    "succeeded\" for HAPPINESS).\n"
    "- \"Partial\": a word in the target's family that is closer to a DIFFERENT emotion this "
    "robot can show (see the lists below).\n"
    "- \"Wrong\": a different emotion family, or no emotion named.\n"
    "Both grammatical genders count the same (כועס = כועסת). Informal phrasing counts.\n"
    "The participant's reason (\"why\") does NOT change the grade: comment on it in the "
    "explanation only. Never judge wording, spelling, length or how the answer was "
    "expressed.\n\n"
    "The robot can show: ANGER, CONTEMPT, DISGUST, FEAR, HAPPINESS, SADNESS, SURPRISE, "
    "EXCITED, BORED, SLEEPY, CALM.\n\n"
    "Hebrew word lists (examples, not exhaustive):\n"
    + _word_list_text()
    + "\n\nRespond with ONLY a JSON object of the exact shape: "
    "{\"result\": \"Correct\" | \"Partial\" | \"Wrong\", \"explanation\": \"<one or two "
    "sentences, in the same language as the participant's answer: why this grade, and a "
    "short comment on their reason>\"}"
)
