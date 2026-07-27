"""Provider response parsing tolerates truncated/empty payloads (the Gemini/OpenAI
`max_tokens` ping used to KeyError and report a healthy key as unreachable)."""

from app.llm.providers import google, openai_compat


def test_google_extract_text_normal():
    data = {"candidates": [{"content": {"parts": [{"text": "hello"}, {"text": " world"}]}}]}
    assert google._extract_text(data) == "hello world"


def test_google_extract_text_truncated():
    # maxOutputTokens=1 -> a candidate with finishReason MAX_TOKENS and no content.
    assert google._extract_text({"candidates": [{"finishReason": "MAX_TOKENS"}]}) == ""
    assert google._extract_text({}) == ""


def test_openai_extract_text_normal():
    data = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
    assert openai_compat._extract_text(data) == "ok"


def test_openai_extract_text_null_content():
    assert openai_compat._extract_text({"choices": [{"message": {"content": None}}]}) == ""
    assert openai_compat._extract_text({}) == ""
