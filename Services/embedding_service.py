from sentence_transformers import SentenceTransformer
import chromadb

# "all-MiniLM-L6-v2" → small, fast, 384-dimension embeddings.
# IMPORTANT: it only reads the first 256 word-piece tokens of any input and
# silently ignores the rest, so every text we embed must be chunked small.
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# ~180 words ≈ 230-250 tokens → fits inside the 256-token window
CHUNK_SIZE_WORDS = 180
CHUNK_OVERLAP_WORDS = 30

# ChromaDB client — persists to disk in ./Chroma_DB folder
chroma_client = chromadb.PersistentClient(path="./Chroma_DB")

# Get or create the shared collection (Decision 2)
notes_collection = chroma_client.get_or_create_collection(name="notes_embeddings")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """
    Splits text into overlapping word chunks.

    chunk_size = 180 words per chunk (fits the embedding model's 256-token limit)
    overlap    = 30 words repeated between chunks
                 so context isn't lost at chunk boundaries
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += chunk_size - overlap   # move forward, keeping overlap

    return chunks


def add_note_to_vectorstore(note_id: int, content: str, user_id: int, topic: str):
    """
    Chunks + embeds note content and stores it in ChromaDB.
    Called right after a note is generated.
    """
    chunks = chunk_text(content)
    if not chunks:
        return

    # One batched encode call instead of one per chunk
    embeddings = embedding_model.encode(chunks).tolist()

    # upsert (not add) so re-indexing the same note never fails or keeps stale text
    notes_collection.upsert(
        ids=[f"user_{user_id}_note_{note_id}_chunk_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=chunks,
        metadatas=[
            {
                "user_id": user_id,
                "note_id": note_id,
                "topic": topic,
                "chunk_index": i,
                "source": "note"
            }
            for i in range(len(chunks))
        ]
    )


def retrieve_relevant_notes(query: str, user_id: int, n_results: int = 5) -> list[str]:
    """
    Searches ChromaDB for notes semantically similar to the query.
    Filters by user_id so users only see their own notes.
    Returns a list of relevant text chunks, tagged with their source.
    """
    count = notes_collection.count()
    if count == 0:
        return []

    query_embedding = embedding_model.encode(query).tolist()

    results = notes_collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"user_id": user_id}
    )

    documents = (results.get('documents') or [[]])[0]
    metadatas = (results.get('metadatas') or [[]])[0]

    tagged_chunks = []
    for doc, meta in zip(documents, metadatas):
        source = meta.get("source", "note")
        filename = meta.get("filename", "")
        if source == "video":
            label = f"[From video: {filename}]"
        elif source == "pdf":
            label = f"[From PDF: {filename}]"
        elif source == "image":
            label = f"[From image: {filename}]"
        else:
            label = "[From notes]"
        tagged_chunks.append(f"{label}\n{doc}")

    return tagged_chunks


def delete_note_vectors(note_id: int):
    """Removes every chunk of a note (used to roll back a failed save)."""
    notes_collection.delete(where={"$and": [{"note_id": note_id}, {"source": "note"}]})


def delete_material_vectors(material_id: int, source: str):
    """Removes every chunk of an uploaded PDF / image / video."""
    notes_collection.delete(where={"$and": [{"material_id": material_id}, {"source": source}]})


def add_pdf_chunks_to_vectorstore(material_id: int, chunks: list[str], user_id: int, filename: str, source: str = "pdf") -> int:
    """
    Embeds all chunks in one batch and stores them in ChromaDB.
    Used for PDF, image and video material. Returns number of chunks stored.
    """
    if not chunks:
        return 0

    embeddings = embedding_model.encode(chunks).tolist()

    notes_collection.upsert(
        ids=[f"{source}_{material_id}_chunk_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=chunks,
        metadatas=[
            {
                "user_id": user_id,
                "material_id": material_id,
                "filename": filename,
                "chunk_index": i,
                "source": source
            }
            for i in range(len(chunks))
        ]
    )

    return len(chunks)
