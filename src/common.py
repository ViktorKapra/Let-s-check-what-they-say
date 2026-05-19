import re
import pandas as pd


REG_EXPRESSION_BULGARIAN = re.compile(r"\b[а-яА-Яa-zA-Z]{3,}\b")

STOP_WORDS = {
    "ще", "има", "това", "които", "като", "при", "тук", "там",
    "сме", "сте", "съм", "беше", "бяха", "може", "трябва",
    "уважаеми", "уважаема", "господин", "госпожо", "колеги",
    "народни", "представители", "председател", "заповядайте",
    "моля", "благодаря", "реплика", "народния", "представител",
}

def clean_text(text: str) -> str:
    prep_text = re.sub(r'\(.*?\)', '', text)
    prep_text = re.sub(r'\s+', ' ', prep_text)
    return prep_text.strip().lower()

def tokenize_and_remove_stopwords(text: str) -> list[str]:
    prep_text = clean_text(text)
    words = REG_EXPRESSION_BULGARIAN.findall(prep_text)
    cleaned_words = [word.lower() for word in words if word.lower() not in STOP_WORDS]
    return cleaned_words

def make_bigrams(words: list[str]) -> list[str]:
    return [f"{w1} {w2}" for w1, w2 in zip(words, words[1:])]

def make_trigrams(words: list[str]) -> list[str]:
    return [f"{w1} {w2} {w3}" for w1, w2, w3 in zip(words, words[1:], words[2:])]  
    

def load_speeches(csv_path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8")
    df = df[df["party"] != "Неизвестна"].copy()
    df = df[df["word_count"] >= 10].copy()
    return df