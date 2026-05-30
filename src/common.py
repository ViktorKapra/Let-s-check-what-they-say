import re
import pandas as pd


REG_EXPRESSION_BULGARIAN = re.compile(r"\b[а-яА-Яa-zA-Z]{3,}\b")

# Only 3+ character words matter here -- the tokenizer regex ({3,}) already
# drops every 1-2 char function word (и, в, на, за, да, не, се, че, аз, той...).
STOP_WORDS = {
    # parliamentary etiquette / procedure
    "уважаеми", "уважаема", "господин", "госпожо", "колеги",
    "народни", "представители", "председател", "заповядайте",
    "моля", "благодаря", "реплика", "народния", "представител",
    # demonstrative / relative / personal pronouns
    "това", "този", "тази", "тези", "онзи", "онази", "онова", "онези",
    "който", "която", "което", "които", "ние", "вие", "тях", "него", "нея",
    "нашия", "вашия", "своя", "свое", "себе",
    "някой", "някоя", "някое", "някои", "всеки", "всяка", "всяко",
    "всички", "всичко", "нищо", "никой",
    # conjunctions / particles
    "като", "защото", "затова", "така", "или", "ако", "обаче", "понеже",
    "докато", "въпреки", "също", "нали", "нека", "дори", "тъй", "нито",
    "пък", "ето", "дали",
    # adverbs (degree / time / quantity — no concrete meaning)
    "сега", "тогава", "още", "вече", "само", "пак", "тук", "там",
    "твърде", "доста", "почти", "съвсем", "малко", "повече", "много",
    # prepositions (3+ chars)
    "при", "към", "след", "преди", "върху", "между", "около", "чрез",
    "освен", "заради", "поради", "спрямо", "относно", "според",
    # common auxiliary / linking verbs
    "ще", "има", "няма", "нямат", "сме", "сте", "съм", "беше", "бяха",
    "може", "трябва", "бъде", "бъда", "бъдат",
    # interrogatives / numerals / indefinites (no concrete meaning)
    "как", "какво", "какъв", "каква", "какви", "кога", "когато", "защо",
    "един", "една", "едно", "нещо", "някак",
    # remaining prepositions / particles
    "без", "най",
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