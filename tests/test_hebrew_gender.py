import pytest

from engine import hebrew_gender
@pytest.mark.parametrize("text,male,female", [
    ("ספר/י על עצמך", "ספר על עצמך", "ספרי על עצמך"),
    ("מה תעשה/י אם המנהל יבקש", "מה תעשה אם המנהל יבקש", "מה תעשי אם המנהל יבקש"),
    ("איך היית מתמודד/ת עם לקוח?", "איך היית מתמודד עם לקוח?", "איך היית מתמודדת עם לקוח?"),
    ("האם את/ה מוכן/ה?", "האם אתה מוכן?", "האם את מוכנה?"),
    ("אתה/את מוכן/ה?", "אתה מוכן?", "את מוכנה?"),
    ("עבודה ו/או לימודים", "עבודה ו/או לימודים", "עבודה ו/או לימודים"),
    ("שאלה בלי לוכסן", "שאלה בלי לוכסן", "שאלה בלי לוכסן"),
])
def test_render(text, male, female):
    assert hebrew_gender.render(text, "male") == male
    assert hebrew_gender.render(text, "female") == female
    assert hebrew_gender.render(text, None) == male  # unknown gender: first form, as written
