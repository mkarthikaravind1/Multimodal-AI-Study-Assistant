import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

LESSON_MODEL = "llama-3.1-8b-instant"


def lesson_messages(topic: str, student_class: str, easy_mode: bool = False) -> list[dict]:
    """
    Builds the prompt for study notes (shared by the normal and streaming versions).
    easy_mode=True → simpler language, more examples, used for weak topics.
    """

    if easy_mode:
        # Tweaked prompt for weak areas — simpler, more examples
        prompt = f"""
        You are a patient teacher helping a student who is STRUGGLING with the topic: "{topic}"
        for a {student_class} engineering student.

        This student got this topic wrong in a quiz, so:
        - Use VERY simple language, avoid jargon
        - Use real-world analogies to explain concepts
        - Break down each idea into small steps
        - Add at least one worked example

        Format your response as:
        1. Simple Overview (2-3 sentences, beginner-friendly)
        2. Key Concepts Explained Simply (bullet points with analogies)
        3. Worked Example
        4. Common Mistakes to Avoid
        """
    else:
        # Original Phase 4 prompt — unchanged
        prompt = f"""
        You are an expert teacher. Generate clear, structured study notes on the topic: "{topic}"
        for a {student_class} engineering student.

        Format your response as:
        1. Overview (2-3 sentences)
        2. Key Concepts (bullet points)
        3. Important Points to Remember (bullet points)

        Keep it concise and easy to understand.
        """

    return [
        {
            "role": "system",
            "content": "You are a helpful study assistant that generates clear educational notes."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]


def generate_notes(topic: str, student_class: str, easy_mode: bool = False) -> str:
    """Calls Groq LLM and returns generated study notes as a string."""
    response = client.chat.completions.create(
        model=LESSON_MODEL,
        messages=lesson_messages(topic, student_class, easy_mode),   # type: ignore
        temperature=0.7,
        max_tokens=1024
    )

    return response.choices[0].message.content or ""


def stream_notes(topic: str, student_class: str, easy_mode: bool = False):
    """Same as generate_notes, but yields the text piece by piece as the model writes it."""
    stream = client.chat.completions.create(
        model=LESSON_MODEL,
        messages=lesson_messages(topic, student_class, easy_mode),   # type: ignore
        temperature=0.7,
        max_tokens=1024,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def generate_remediation_notes(topic: str, student_class: str, mistakes: list[dict]) -> str:
    """
    Self-healing loop: notes aimed at exactly what the student got wrong.
    mistakes: [{"question", "user_answer", "correct_answer"}] — user_answer may be
    None for quizzes taken before answers were recorded.
    """
    lines = []
    for i, m in enumerate(mistakes, start=1):
        line = f'{i}. Question: "{m["question"]}"\n   Correct answer: "{m["correct_answer"]}"'
        if m.get("user_answer"):
            line += f'\n   Student answered: "{m["user_answer"]}"'
        lines.append(line)
    mistakes_text = "\n".join(lines)

    prompt = f"""
    A {student_class} student is studying "{topic}" and got these quiz questions wrong:

    {mistakes_text}

    Write short, focused "fix-up" study notes that repair exactly these gaps:
    - For each mistake, explain the underlying concept in simple language
    - Where the student's answer is shown, explain why it is wrong (the likely misconception)
    - Use one real-world analogy or tiny worked example per concept
    - Do NOT repeat the quiz questions word for word

    Format your response as:
    1. What went wrong (1-2 sentences, encouraging tone)
    2. Concepts to fix (one short section per concept, with a heading)
    3. Quick memory tips (bullet points)
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a patient tutor who repairs specific misunderstandings."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""
