from app.services.image_result_parser import extract_image_urls_from_provider_result


def test_extracts_openai_style_data_list():
    result = {"data": [{"url": "https://cdn.example.com/a.png"}]}

    assert extract_image_urls_from_provider_result(result) == ["https://cdn.example.com/a.png"]


def test_extracts_minimax_nested_image_urls():
    result = {"data": {"image_urls": ["https://cdn.example.com/minimax.png"]}}

    assert extract_image_urls_from_provider_result(result) == ["https://cdn.example.com/minimax.png"]


def test_extracts_local_dev_urls_without_duplicates():
    result = {
        "local_urls": ["/static/dev/avatar.png"],
        "data": [{"url": "/static/dev/avatar.png"}],
    }

    assert extract_image_urls_from_provider_result(result) == ["/static/dev/avatar.png"]
