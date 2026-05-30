import time
from collections import Counter, defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import common as cmn
from parse_and_save import PROC_DIR

def run_tfidf_vectorized(df, top_n=20):
    # ── ONE tokenization pass, reused three ways ──────────────────────────
    # Each speech is tokenized exactly once; from those tokens we feed the
    # unigram TF-IDF *and* count bigrams/trigrams. (Previously TfidfVectorizer
    # tokenized the whole corpus, then we tokenized every speech AGAIN for the
    # n-grams — two passes over the same text.)
    party_tokens: dict[str, list] = defaultdict(list)   # unigram "document" per party
    bigrams: dict[str, Counter] = defaultdict(Counter)
    trigrams: dict[str, Counter] = defaultdict(Counter)
    for party, text in zip(df["party"], df["text"]):
        tokens = cmn.tokenize_and_remove_stopwords(text)
        party_tokens[party].extend(tokens)                       # for TF-IDF
        bigrams[party].update(zip(tokens, tokens[1:]))           # tuple-counted
        trigrams[party].update(zip(tokens, tokens[1:], tokens[2:]))

    parties = list(party_tokens)
    docs = [party_tokens[p] for p in parties]                    # pre-tokenized docs

    # analyzer=identity → TfidfVectorizer does NOT re-tokenize or re-filter; the
    # tokens are already cleaned + stop-word-stripped by common.py. So
    # token_pattern / stop_words are dropped (they'd be ignored anyway).
    vectorizer = TfidfVectorizer(
        analyzer=lambda toks: toks,
        max_features=10_000,                       # cap vocabulary to the 10k most frequent words
        min_df=1,                                  # ignore words appearing in <2 parties (noise)
        sublinear_tf=True,                         # use log(1+tf) — dampens very frequent words
    )
    tfidf_matrix = vectorizer.fit_transform(docs)
    feature_names = vectorizer.get_feature_names_out()

    top_words = {}
    for i, party in enumerate(parties):
        scores = tfidf_matrix[i].toarray().flatten()    # ← row i = this party
        top_idx = np.argsort(scores)[::-1][:top_n]
        top_words[party] = [(feature_names[j], scores[j]) for j in top_idx]

    # join tuple-keys to strings only for the survivors (top_n per party)
    top_bigrams = {p: [(" ".join(ng), c) for ng, c in bigrams[p].most_common(top_n)]
                   for p in parties}
    top_trigrams = {p: [(" ".join(ng), c) for ng, c in trigrams[p].most_common(top_n)]
                    for p in parties}

    similarity_matrix = cosine_similarity(tfidf_matrix)

    return {
        "tfidf_matrix": tfidf_matrix,
        "feature_names": feature_names,
        "parties": parties,
        "top_words": top_words,
        "top_bigrams": top_bigrams,
        "top_trigrams": top_trigrams,
        "similarity_matrix": similarity_matrix,
    }

if __name__ == "__main__":
    df = cmn.load_speeches(PROC_DIR / "speeches.csv")
    start = time.perf_counter()
    result = run_tfidf_vectorized(df)
    end = time.perf_counter()
    print(f"Vectorized analysis completed in {end - start:.3f} seconds")

    print("\nCosine similarity between parties:")
    parties = result["parties"]
    sim = result["similarity_matrix"]
    for i in range(len(parties)):
        for j in range(i + 1, len(parties)):       # i < j → each pair once
            print(f"  {parties[i][:25]:25s} ↔ {parties[j][:25]:25s}: {sim[i][j]:.3f}")

    print("\nTop 5 TF-IDF words per party:")
    for party, words in result["top_words"].items():
        top5 = ", ".join(w for w, _ in words[:5])
        print(f"  {party[:40]:40s}: {top5}")