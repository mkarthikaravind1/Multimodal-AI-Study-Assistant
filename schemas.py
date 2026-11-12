#schemas.py
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints

# Reusable constrained string types — whitespace is stripped first,
# so "   " counts as empty and is rejected.
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")]
Password = Annotated[str, StringConstraints(min_length=8, max_length=72)]   # bcrypt only reads 72 bytes
Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
StudentClass = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]

class RegisterRequest(BaseModel):
    username: Username      # 3-50 chars: letters, digits, _ . -
    password: Password      # 8-72 chars

class TokenResponse(BaseModel):
    access_token:str
    token_type:str = "bearer"

class LessonRequest(BaseModel):
    topic: Topic
    student_class: StudentClass

class LessonResponse(BaseModel):
    note_id: int
    title: str
    content: str
    topic: str
    student_class: str
    youtube_links: list[str]
    message: str

class MeResponse(BaseModel):
    username: str
    role: str
    student_class: str | None     # last education level the student used

# Single MCQ shape
class MCQQuestion(BaseModel):
    question: str
    options: list[str]        # always 4 items
    correct_answer: str       # exact text of the correct option

# What the student sees — no correct_answer, so the key can't be read in DevTools
class MCQQuestionPublic(BaseModel):
    question: str
    options: list[str]

# Request — what frontend sends
class QuizRequest(BaseModel):
    note_id: int
    topic: Topic

# Response — what frontend gets back
class QuizResponse(BaseModel):
    quiz_id: int
    topic: str
    questions: list[MCQQuestionPublic]
    total_questions: int
    message: str 

# One answer the student submits
class SubmittedAnswer(BaseModel):
    question: str = Field(max_length=1000)       # must match exactly what was generated
    user_answer: str = Field(max_length=1000)    # what the student picked

# Full submission request
class QuizSubmitRequest(BaseModel):
    quiz_id: int
    answers: list[SubmittedAnswer] = Field(max_length=20)

# Per question result — was it right or wrong?
class QuestionResult(BaseModel):
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool

# Full evaluation response
class QuizSubmitResponse(BaseModel):
    quiz_id: int
    topic: str
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    score_percentage: float
    results: list[QuestionResult]   # breakdown per question
    message: str

class TopicAverage(BaseModel):
    topic:str
    average_score:float

class AnalyticsResponse(BaseModel):
    strong:list[str]
    weak:list[str]
    topic_breakdown:list[TopicAverage]

class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    session_id: int | None = None    # None = start a new session
    message: str = Field(min_length=1, max_length=4000)
    note_id: int | None = None       # optional — link chat to a specific note

class ChatResponse(BaseModel):
    session_id: int
    reply: str
    messages: list[ChatMessage]      # full conversation so far

class PDFUploadResponse(BaseModel):
    material_id: int
    filename: str
    total_chunks: int
    message: str

class ImageAnalysisResponse(BaseModel):
    material_id:int
    filename: str
    question: str
    answer: str
    session_id: int      # tutor session the image Q&A was added to
    message: str

class MaterialResponse(BaseModel):
    material_id: int
    filename: str
    file_type: str
    total_chunks: int
    uploaded_at: datetime | None

class AudioTranscriptResponse(BaseModel):
    filename: str
    transcript: str
    message: str

class VideoAnalysisResponse(BaseModel):
    filename: str
    transcript: str
    frame_descriptions: list[str]
    combined_summary: str
    total_frames_analyzed: int
    message: str