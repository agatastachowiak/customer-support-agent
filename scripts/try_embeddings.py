"""Small experiment: do embeddings really capture meaning?"""
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")   # small, free embedding model

sentences = [
    "Can I send my headphones back?",
    "Customers can return any item within 30 days of the delivery date.",
    "We accept iDEAL, credit card, PayPal and Klarna.",
]

vectors = model.encode(sentences)       # turns each sentence into its 384-number fingerprint
print("Shape:", vectors.shape)          # (3 sentences, 384 numbers each)

scores = util.cos_sim(vectors[0], vectors[1:])      #calculates the cosine similarity between the question and the other two sentences
print("Question vs return policy: ", round(float(scores[0][0]), 3))
print("Question vs payment methods:", round(float(scores[0][1]), 3))