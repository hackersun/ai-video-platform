from app.services.dialogue_lineage_service import extract_explicit_dialogue


def test_extracts_named_chinese_dialogue_with_stable_source_span():
    source = '沈砚抵达雾港。沈砚说：“我会查清真相。”'
    result = extract_explicit_dialogue(source)
    assert len(result) == 1
    assert result[0]['speaker'] == '沈砚'
    assert result[0]['spoken_text'] == '我会查清真相。'
    assert result[0]['dialogue'] == '沈砚：我会查清真相。'
    start, end = result[0]['source_span']
    assert source[start:end] == '沈砚说：“我会查清真相。”'


def test_does_not_treat_pronouns_common_words_or_titles_as_speakers():
    source = '他说：“快走。”\n大家问：“为什么？”\n老师说：“安静。”\n母亲答：“知道了。”'
    assert extract_explicit_dialogue(source) == []


def test_does_not_consume_across_sentence_or_line_boundaries():
    source = '风吹过长街。沈砚说：“回去吧。”\n夜色渐深\n苏晚问：「你确定吗？」'
    result = extract_explicit_dialogue(source)
    assert [(item['speaker'], item['spoken_text']) for item in result] == [
        ('沈砚', '回去吧。'),
        ('苏晚', '你确定吗？'),
    ]
    assert source[result[0]['source_span'][0]:result[0]['source_span'][1]] == '沈砚说：“回去吧。”'
    assert source[result[1]['source_span'][0]:result[1]['source_span'][1]] == '苏晚问：「你确定吗？」'


def test_requires_two_to_four_chinese_characters_for_a_proper_name():
    source = '李说：“不行。”\n欧阳修说：“可以。”\n司马相如说：“再议。”\n阿尔法五号说：“收到。”'
    result = extract_explicit_dialogue(source)
    assert [(item['speaker'], item['spoken_text']) for item in result] == [
        ('欧阳修', '可以。'),
        ('司马相如', '再议。'),
    ]


def test_requires_matching_chinese_or_english_quote_pairs():
    source = '沈砚说：“正确。”\n苏晚说：「也正确。」\n林舟说：『仍正确。』\n顾宁说：“错配。」\n周岚说：「错配。”\n陆川说:"英文正确。"'
    result = extract_explicit_dialogue(source)
    assert [(item['speaker'], item['spoken_text']) for item in result] == [
        ('沈砚', '正确。'),
        ('苏晚', '也正确。'),
        ('林舟', '仍正确。'),
        ('陆川', '英文正确。'),
    ]


def test_keeps_nested_quotes_inside_one_dialogue():
    source = '沈砚说：“她只说了「等等」，随后就走了。”'
    result = extract_explicit_dialogue(source)
    assert len(result) == 1
    assert result[0]['spoken_text'] == '她只说了「等等」，随后就走了。'


def test_extracts_multiple_speakers_without_cross_match_contamination():
    source = '沈砚说：“第一句。”苏晚问：“第二句？”林舟答：“第三句。”'
    result = extract_explicit_dialogue(source)
    assert [(item['speaker'], item['spoken_text']) for item in result] == [
        ('沈砚', '第一句。'),
        ('苏晚', '第二句？'),
        ('林舟', '第三句。'),
    ]


def test_rejects_unclosed_or_overlong_dialogue_without_swallowing_next_sentence():
    overlong = '甲' * 501
    source = f'沈砚说：“没有闭合。苏晚说：“也不应被吞。”\n林舟说：“{overlong}”\n顾宁说：“有效。”'
    result = extract_explicit_dialogue(source)
    assert [(item['speaker'], item['spoken_text']) for item in result] == [('顾宁', '有效。')]
