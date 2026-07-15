import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_notes(topic: str, student_class: str, easy_mode: bool = False) -> str:
    """
    Calls Groq LLM and returns generated study notes as a string.
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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful study assistant that generates clear educational notes."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=1024
    )

    return response.choices[0].message.content or ""