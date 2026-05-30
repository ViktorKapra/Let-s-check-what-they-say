import math
import pandas as pd
import common as cmn
from collections import Counter, defaultdict
from parse_and_save import PROC_DIR
import time

def analyze_one_speech(speech:dict) -> dict:
    tokens = cmn.tokenize_and_remove_stopwords(speech["text"])
    return {"party": speech["party"],
            "unigrams": Counter(tokens), 
            "bigrams": Counter(cmn.make_bigrams(tokens)),
            "trigrams": Counter(cmn.make_trigrams(tokens)),
            "total_words": len(tokens)
            }
    

def aggregate_by_party(results :list[dict]) -> dict[str, dict]:
    by_party = defaultdict(lambda: {"unigrams": Counter(), "bigrams": Counter(), "trigrams": Counter(), "total_words": 0, "speech_count": 0})
    for result in results:
        party = result["party"]
        by_party[party]["unigrams"].update(result["unigrams"])
        by_party[party]["bigrams"].update(result["bigrams"])
        by_party[party]["trigrams"].update(result["trigrams"])
        by_party[party]["total_words"] += result["total_words"]
        by_party[party]["speech_count"] += 1
    return dict(by_party)

def compute_tf_idf(by_party, top_n=20):
    vectors = compute_tf_idf_vectors(by_party)
    return {party: sorted(value.items(), key=lambda x: x[1], reverse=True)[:top_n]
            for party, value in vectors.items()}

def compute_tf_idf_vectors(by_party) -> dict[str, dict[str, float]]:
    n_parties = len(by_party)
    doc_freq = Counter()
    party_tf_idf = {}

    for party_data in by_party.values():
        doc_freq.update(party_data["unigrams"].keys())   # .keys() → unique words per party
    
    for party in by_party:
        vec = {}
        for word, count in by_party[party]["unigrams"].items():
            tf = 1 + math.log(count)                                     # sklearn sublinear_tf=True
            idf = math.log((1 + n_parties) / (1 + doc_freq[word])) + 1   # sklearn smooth_idf=True
            vec[word] = tf * idf
        party_tf_idf[party] = vec
    return party_tf_idf

def _cosine(vec_a: dict, vec_b: dict) -> float:
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[w] * vec_b[w] for w in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)

def compute_cosine_similarity(by_party) -> dict[tuple[str, str], float]:
    vectors = compute_tf_idf_vectors(by_party)
    parties = list(vectors)
    sims = {}
    for i, p1 in enumerate(parties):
        for p2 in parties[i + 1:]:
            sims[(p1, p2)] = _cosine(vectors[p1], vectors[p2])
    return sims

def run_serial(df: pd.DataFrame) -> dict:
    speeches = df.to_dict("records")
    results = [analyze_one_speech(s) for s in speeches]
    by_party = aggregate_by_party(results)
    tfidf = compute_tf_idf(by_party)
    similarity = compute_cosine_similarity(by_party)

    return {"by_party": by_party, "tfidf": tfidf, "similarity": similarity}

if __name__ == "__main__":
    df = cmn.load_speeches(PROC_DIR / "speeches.csv")
    start = time.perf_counter()
    analysis_result = run_serial(df)
    end = time.perf_counter()
    print(f"Serial analysis completed in {end - start:.2f} seconds")

    print("\nTop 5 TF-IDF words per party:")
    for party, words in analysis_result["tfidf"].items():
        top5 = ", ".join(w for w, _ in words[:10])
        print(f"  {party[:40]:40s}: {top5}")
