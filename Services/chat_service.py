import os
import re
from groq import Groq
from dotenv import load_dotenv
from groq.types.chat import ChatCompletionMessageParam

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Only the most recent messages are sent to the LLM. The full history is still
# saved in MySQL — this just stops long sessions from blowing the token limit.
MAX_HISTORY_MESSAGES = 12

SYSTEM_PROMPT = (
    "You are a friendly, patient tutor helping a student. "
    "Explain concepts clearly, use examples, and encourage questions. "
    "Keep answers focused and not too long.\n\n"
    "CITATIONS: when you use information from the provided sources, cite them "
    "inline with their tag in square brackets, e.g. [S1] or [S2]. "
    "Only use tags that appear in the sources. Never invent a tag. "
    "Never call a video a PDF or vice versa — each source says what type it is. "
    "If no source is relevant, answer from general knowledge without citations."
)


def describe_source(source: dict) -> str:
    """One-line header for a source in the prompt, e.g. 'PDF "notes.pdf", page 3'."""
    kind = source["type"]
    if kind == "pdf":
        page = f", page {source['page']}" if source.get("page") else ""
        return f'PDF "{source["filename"]}"{page}'
    if kind == "video":
        at = f", at {source['timestamp']}" if source.get("timestamp") else ""
        return f'Video "{source["filename"]}"{at}'
    if kind == "image":
        return f'Image "{source["filename"]}"'
    return f'Lesson notes "{source.get("label", "notes")}"'


def get_tutor_reply(messages: list[dict], sources: list[dict] | None = None) -> str:
    """
    Calls Groq LLM with conversation history.
    sources: [{"id": "S1", "type": ..., "text": ..., ...}] — injected into the
    last user message so the model can answer from them and cite [S1].
    """

    # Step 0 — Recent window only, and ONLY role + content (stored messages also
    # carry extra keys such as "sources", which the Groq API would reject)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages[-MAX_HISTORY_MESSAGES:]
    ]

    # Step 1 — If we have retrieved sources, augment the last user message
    if sources and messages:
        context_text = "\n\n".join(
            f"[{s['id']}] {describe_source(s)}:\n{s['text']}" for s in sources
        )
        user_query = messages[-1]["content"]
        messages[-1] = {
            "role": "user",
            "content": (
                "Sources from the student's own materials:\n\n"
                f"{context_text}\n\n"
                "Answer the question below. Cite sources inline with their tags, like [S1].\n\n"
                f"Student's question: {user_query}"
            ),
        }

    final_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *messages,   # type: ignore
    ]

    # Step 2 — Send request to Groq client
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=final_messages,
        temperature=0.7,
        max_tokens=1024
    )

    return response.choices[0].message.content or ""


_BRACKET_GROUP = re.compile(r"\[((?:\s*S\d+\s*[,;]?)+)\]")


def normalize_citations(reply: str, valid_ids: set[str]) -> tuple[str, list[str]]:
    """
    Cleans up the model's citation tags:
      "[S1, S3]" -> "[S1][S3]", unknown tags like "[S9]" are removed.
    Returns (clean_reply, cited_ids_in_order_of_first_use).
    """
    cited: list[str] = []

    def replace(match: re.Match) -> str:
        ids = re.findall(r"S\d+", match.group(1))
        kept = [i for i in ids if i in valid_ids]
        for i in kept:
            if i not in cited:
                cited.append(i)
        return "".join(f"[{i}]" for i in kept)

    clean = _BRACKET_GROUP.sub(replace, reply)
    clean = re.sub(r"[ \t]+([.,;:!?])", r"\1", clean)    # tidy "text [S9]." -> "text."
    return clean, cited
