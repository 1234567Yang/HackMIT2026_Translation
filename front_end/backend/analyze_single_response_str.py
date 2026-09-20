"""纯文本分析：分析用户说话内容里的语言习惯问题。"""

import string

# 纯语气词/感叹词，几乎不会在正常句子里合法出现，误判风险很低
FILLER_WORDS = {"um", "umm", "uh", "uhh", "erm"}

# 作为独立话语标记出现时几乎总是口头禅，误判风险较低
FILLER_PHRASES = ("you know",)

# 只在这些功能词（代词/冠词/介词/连接词等）上检测“连续重复”。
# 像 "very very good"、"no no no" 这种实义词重复大多是刻意强调，属于正常修辞；
# 而 "i i"、"the the" 这类功能词几乎不会是刻意重复，基本都是卡壳/口误。
STUTTER_CANDIDATE_WORDS = {
    "i", "a", "the", "an", "is", "are", "was", "were",
    "it", "to", "that", "and", "of", "in", "you", "so", "but",
}

# 常见粗口/脏话，命中就提示注意用语
PROFANITY_WORDS = {
    "fuck", "fucking", "fucked", "fucker",
    "shit", "shitty", "bullshit",
    "damn", "goddamn",
    "ass", "asshole",
    "bitch",
    "crap",
}


def slur_word_detection(single_user_input: str) -> str:
    """检测粗口/脏话（fuck, shit 等），命中就给出提示（可能是空字符串）。"""

    text = single_user_input.lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    words = text.split(" ")

    hit_count = sum(1 for word in words if word in PROFANITY_WORDS)

    if hit_count > 0:
        return (
            " You used profanity (e.g. \"fuck\", \"shit\") during the "
            "conversation, try to keep your language professional in this "
            "context."
        )

    return ""


def analyze_user_input_from_text(single_user_input: str) -> str:
    """对一段文字做纯文本分析，返回给用户的建议（可能是空字符串）。"""

    return_suggestion = ""

    text = single_user_input.lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)

    words = text.split(" ")
    word_count = len(words)

    and_count = text.count(" and")

    if word_count > 0 and (and_count / word_count) > 0.05:
        return_suggestion += (
            "You used too much \"and\", you could practice more about what you "
            "are trying to express, and make sure that use structurized output "
            "like \"First of all\", \"then\", ..."
        )

    filler_count = sum(1 for word in words if word in FILLER_WORDS)
    filler_count += sum(
        1 for a, b in zip(words, words[1:]) if f"{a} {b}" in FILLER_PHRASES
    )

    if word_count > 0 and (filler_count / word_count) > 0.05:
        return_suggestion += (
            " You used a lot of filler words/phrases (like \"um\", \"uh\", "
            "\"you know\"), try pausing silently instead of filling the gap "
            "with these words."
        )

    stutter_count = sum(
        1
        for a, b in zip(words, words[1:])
        if a and a == b and a in STUTTER_CANDIDATE_WORDS
    )

    if stutter_count >= 2:
        return_suggestion += (
            " You repeated the same word back-to-back multiple times (e.g. "
            "\"I I\", \"the the\"), try to slow down a bit so you don't "
            "stumble over your words."
        )

    return_suggestion += slur_word_detection(single_user_input)

    return return_suggestion
