import re
from rank_bm25 import BM25Okapi

def chunk_text(text, chunk_size=200, overlap=50):
    """
    Splits text into overlapping word chunks.
    """
    words = text.split()
    chunks = []
    
    if len(words) == 0:
        return chunks

    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += (chunk_size - overlap)
        
    return chunks

def tokenize(text):
    """
    Simple tokenizer that lowercases and strips punctuation.
    """
    return re.findall(r'\b\w+\b', text.lower())

def retrieve_relevant_chunks(query, text, top_k=3):
    """
    Splits the text into chunks, runs BM25 to find the most relevant ones to the query,
    and returns a combined string of the top results.
    """
    chunks = chunk_text(text, chunk_size=250, overlap=50)
    
    if not chunks:
        return ""
        
    # Tokenize corpus
    tokenized_corpus = [tokenize(chunk) for chunk in chunks]
    
    # Initialize BM25
    bm25 = BM25Okapi(tokenized_corpus)
    
    # Tokenize query
    tokenized_query = tokenize(query)
    
    # Get top k results
    top_chunks = bm25.get_top_n(tokenized_query, chunks, n=top_k)
    
    # Return formatted string with separators
    return "\n\n...[Snippet]...\n\n".join(top_chunks)
