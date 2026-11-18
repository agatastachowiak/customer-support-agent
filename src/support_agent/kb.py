"""Knowledge base search (the R in RAG): find the policy sections that best match a question."""
from pathlib import Path
from functools import lru_cache
from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "all-MiniLM-L6-v2"

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"


def _make_chunk(source, title, lines):
    return {"source": source, "title": title, "text": " ".join(lines)}

# ## means a new card begins

def load_chunks(): 
    """Split every policy file into sections, one per '## ' heading. 
    Returns a list like [{"source": "shipping.md", "title": "...", "text": "..."}, ...]"""
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):            # every .md file in data/kb
        title, lines = None, []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):                   # a new section starts
                if title is not None:                    # save the previous one first
                    chunks.append(_make_chunk(path.name, title, lines))
                title, lines = line[3:].strip(), []      # heading text without "## "
            elif title is not None and line.strip():     # a text line inside a section
                lines.append(line.strip())
        if title is not None:                            # save the last section of the file
            chunks.append(_make_chunk(path.name, title, lines))
    return chunks


@lru_cache(maxsize=1) #a decorator that makes a function remember its result, a first call to _index() 
                      #loads the model and fingerprints the 18 cards. Every later call returns the stored result instantly. 
                      # Without it, every single question would reload the model and recompute all 18 fingerprints.
def _index():
    """Load the model and fingerprint all chunks. Runs only once; later calls reuse the result."""
    model = SentenceTransformer(MODEL_NAME)
    chunks = load_chunks()
    texts = [f"{c['title']}. {c['text']}" for c in chunks]   # heading + text together
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)    # normalize_embeddings=True : scales every vector to length 1
    return model, chunks, vectors


def search_policies(query: str, top_k: int = 3) -> list[dict]:
    """Return the top_k policy sections most similar in meaning to the query."""
    model, chunks, vectors = _index()
    query_vector = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
    scores = util.cos_sim(query_vector, vectors)[0]           # one score per chunk
    best = scores.argsort(descending=True)[:top_k]            # argsort(descending=True) : positions of the highest scores, 
                                                              # and [:top_k] keeps the first three
    return [
        {**chunks[int(i)], "score": round(float(scores[i]), 3)} # copies the chunk dictionary and adds a "score" key with the rounded similarity score
        for i in best
    ]


if __name__ == "__main__":
    questions = [
        "I got my headphones two weeks ago, can I still send them back?",
        "My package still hasn't arrived and it's a week late",
        "Do you deliver to Belgium?",
        "My coffee machine stopped working after a year",
        "When will I get my money back?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        for hit in search_policies(q):
            print(f"   {hit['score']:.3f}  [{hit['source']}] {hit['title']}")