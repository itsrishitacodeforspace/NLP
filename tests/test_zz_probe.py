def test_probe():
    import importlib
    m = importlib.import_module("nlp.evaluation")
    p = list(m.__path__)
    assert "/marimo/nlp/nlp/evaluation" in p, p
    print("GOOD PATH")
