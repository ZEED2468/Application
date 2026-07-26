from app.llm import experience_classify

def test_experience_classify():
    assert experience_classify.classify(title="Junior Developer") == "junior"
    assert experience_classify.classify(title="Graduate Software Engineer") == "junior"
    assert experience_classify.classify(title="Intern - Backend") == "junior"
    
    assert experience_classify.classify(title="Senior React Developer") == "senior"
    assert experience_classify.classify(title="Staff Engineer") == "senior"
    
    assert experience_classify.classify(title="Lead Product Engineer") == "lead"
    assert experience_classify.classify(title="Engineering Manager") == "lead"
    assert experience_classify.classify(title="Director of Engineering") == "lead"
    
    assert experience_classify.classify(title="Full-Stack Developer") == "mid"
    assert experience_classify.classify(title="Software Engineer") == "mid"
