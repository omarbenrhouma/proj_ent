from app.services import score_test


def test_scoring_module_is_importable():
    assert callable(score_test)
