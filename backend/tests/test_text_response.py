import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).parents[1] / "app/features/model_drivers/text_response.py"
_SPEC = importlib.util.spec_from_file_location("text_response_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
sanitize_chat_response = _MODULE.sanitize_chat_response


def test_sanitize_chat_response_accepts_null_choices() -> None:
    response = {"choices": None, "output_text": "下一章正文"}

    sanitized = sanitize_chat_response(response)

    assert sanitized["choices"][0]["message"]["content"] == "下一章正文"
