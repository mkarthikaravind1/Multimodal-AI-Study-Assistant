import os
from groq import Groq
from dotenv import load_dotenv
from groq.types.chat import ChatCompletionMessageParam

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_tutor_reply(messages: list[ChatCompletionMessageParam], context_chunks: list[str]|None = None) -> str:
    """
    Calls Groq LLM with conversation history.
    If context_chunks provided, injects them into the last user message.
    """

    # Step 1 — If we have retrieved context, augment the last user message
    if context_chunks and len(context_chunks) > 0 and len(messages) > 0:
        context_text = "\n\n".join(context_chunks)   # join chunks with spacing

        # Build augmented version of the last user message
        last_message = messages[-1]                   # the user's latest question
        
        # Safely extract text content to satisfy Pylance
        user_query = last_message.get("content") or ""

        augmented_content = f"""Use the following labeled context from the student's uploaded materials to answer the question.
        Each chunk is labeled with its exact source type (video, PDF, or image) — refer to that source accurately and do not confuse one type with another.
        If the context is not relevant, use your general knowledge.

        Context from student's materials:
        {context_text}

        Student's question: {user_query}"""
    
        # Replace last message with augmented version safely
        augmented_messages = messages[:-1] + [
            {"role": "user", "content": augmented_content}
        ]
    else:
        # No context — use messages as-is
        augmented_messages = messages

    # Step 2 — Only add system message if the history doesn't already start with one
    has_system_message = len(augmented_messages) > 0 and augmented_messages[0].get("role") == "system"
    
    if not has_system_message:
        system_message: ChatCompletionMessageParam = {
            "role": "system",
            "content": (
                 "You are a friendly, patient tutor helping an engineering student. "
                "Explain concepts clearly, use examples, and encourage questions. "
                "Context chunks are labeled with their source, e.g. [From video: ...], "
                "[From PDF: ...], [From image: ...]. Always refer to the correct source "
                "type exactly as labeled — never call a video a PDF or vice versa. "
                "Keep answers focused and not too long."
            )
        }
        final_messages = [system_message] + augmented_messages
    else:
        final_messages = augmented_messages

    # Step 3 — Send request to Groq client
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=final_messages,
        temperature=0.7,
        max_tokens=1024
    )

    return response.choices[0].message.content or ""