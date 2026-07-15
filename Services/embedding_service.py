from sentence_transformers import SentenceTransformer
import chromadb

# "all-MiniLM-L6-v2" → small, fast, 384-dimension embeddings
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# ChromaDB client — persists to disk in ./chroma_db folder
chroma_client = chromadb.PersistentClient(path="./Chroma_DB")

# Get or create the shared collection (Decision 2)
notes_collection = chroma_client.get_or_create_collection(name="notes_embeddings")

def add_note_to_vectorstore(note_id: int, content: str, user_id: int, topic: str):
    """
    Embeds note content and stores it in ChromaDB.
    Called right after a note is generated (Phase 4/8).
    """

    # Step 1 — Generate embedding (384-dim vector)
    embedding = embedding_model.encode(content).tolist()  # numpy array → list for ChromaDB

    # Step 2 — Store in ChromaDB
    notes_collection.add(
        ids=[f"user_{user_id}_note_{note_id}"],          # ChromaDB requires string IDs
        embeddings=[embedding],
        documents=[content],          # original text, returned during retrieval
        metadatas=[{
            "user_id": user_id,
            "note_id": note_id,
            "topic": topic,
            "source": "note" 
        }]
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

    # notes_collection.add(
    #     ids=[str(note_id)],          # ChromaDB requires string IDs
    #     embeddings=[embedding],
    #     documents=[content],          # original text, returned during retrieval
    #     metadatas=[{
    #         "user_id": user_id,
    #         "note_id": note_id,
    #         "topic": topic,
    #         "source": "note" 
    #     }]
    # )

# def retrieve_relevant_notes(query: str, user_id: int, n_results: int = 5) -> list[str]:
#     """
#     Searches ChromaDB for notes semantically similar to the query.
#     Filters by user_id so users only see their own notes.
#     Returns a list of relevant text chunks.
#     """
#     count = notes_collection.count()
#     if count == 0:
#         return []
#     # Step 1 — Embed the query using the SAME model used during storage
#     # Critical: must use same model, else vectors are incompatible
#     query_embedding = embedding_model.encode(query).tolist()

#     # Step 2 — Query ChromaDB
#     results = notes_collection.query(
#         query_embeddings=[query_embedding],
#         n_results=n_results,
#         where={"user_id": user_id}     # Decision 2 — filter by user
#     )

#     # Step 3 — Extract just the text chunks from results
#     # results["documents"] is a list of lists: [[doc1, doc2, doc3]]
#     # [0] gets the inner list for our single query
#     documents = (results.get('documents') or [[]])[0]

#     return documents    # list of 3 most relevant note texts

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Splits text into overlapping chunks.
    
    chunk_size = 500 words per chunk (fits embedding model's limit)
    overlap    = 50 words repeated between chunks
                 so context isn't lost at chunk boundaries
    
    Example with overlap:
    Chunk 1: words 1-500
    Chunk 2: words 451-950   ← starts 50 words before chunk 1 ends
    Chunk 3: words 901-1400
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap   # move forward, keeping overlap

    return chunks


# def add_pdf_chunks_to_vectorstore(material_id: int,chunks: list[str],user_id: int,filename: str) -> int:
#     """
#     Embeds each chunk and stores in ChromaDB.
#     Returns total number of chunks stored.
#     """
#     for i, chunk in enumerate(chunks):
#         embedding = embedding_model.encode(chunk).tolist()

#         notes_collection.add(
#             ids=[f"pdf_{material_id}_chunk_{i}"],   # unique ID per chunk
#             embeddings=[embedding],
#             documents=[chunk],
#             metadatas=[{
#                 "user_id": user_id,
#                 "material_id": material_id,
#                 "filename": filename,
#                 "chunk_index": i,
#                 "source": "pdf"             # distinguish from note embeddings
#             }]
#         )

#     return len(chunks)

def add_pdf_chunks_to_vectorstore(material_id: int, chunks: list[str], user_id: int, filename: str, source: str = "pdf") -> int:
    for i, chunk in enumerate(chunks):
        embedding = embedding_model.encode(chunk).tolist()

        notes_collection.add(
            ids=[f"{source}_{material_id}_chunk_{i}"],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{
                "user_id": user_id,
                "material_id": material_id,
                "filename": filename,
                "chunk_index": i,
                "source": source
            }]
        )

    return len(chunks)