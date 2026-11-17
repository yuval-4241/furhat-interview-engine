from apps import demo_question_selection
def test_behavioral_question_triggers_pe():
    assert demo_question_selection.triggers_pe("behavioral_pbdi") is True


def test_self_reflection_question_triggers_pe():
    assert demo_question_selection.triggers_pe("self_reflection") is True


def test_warm_up_question_does_not_trigger_pe():
    assert demo_question_selection.triggers_pe("warm_up") is False


def test_motivation_fit_question_does_not_trigger_pe():
    assert demo_question_selection.triggers_pe("motivation_fit") is False


def test_closing_question_does_not_trigger_pe():
    assert demo_question_selection.triggers_pe("closing") is False
