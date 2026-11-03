def test_probe():
    import importlib
    m = importlib.import_module("nlp.evaluation")
    assert "/marimo/nlp/nlp/evaluation" in list(m.__path__), list(m.__path__)
    print("GOOD PATH")
