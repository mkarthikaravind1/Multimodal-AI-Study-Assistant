#schemas.py
from pydantic import BaseModel

# class RegisterRequest(BaseModel):
#     username: str
#     password: str
#     student_class: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    #role: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token:str
    token_type:str = "bearer"

class LessonRequest(BaseModel):
    topic: str
    student_class: str

class LessonResponse(BaseModel):
    note_id: int
    title: str
    content: str
    topic: str
    student_class: str
    message: str

# Single MCQ shape
class MCQQuestion(BaseModel):
    question: str
    options: list[str]        # always 4 items
    correct_answer: str       # exact text of the correct option

# Request — what frontend sends
class QuizRequest(BaseModel):
    note_id: int
    topic: str

# Response — what frontend gets back
class QuizResponse(BaseModel):
    quiz_id: int
    topic: str
    questions: list[MCQQuestion]
    total_questions: int
    message: str 

# One answer the student submits
class SubmittedAnswer(BaseModel):
    question: str       # must match exactly what was generated
    user_answer: str    # what the student picked

# Full submission request
class QuizSubmitRequest(BaseModel):
    quiz_id: int
    answers: list[SubmittedAnswer]

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

class WeakTopicRequest(BaseModel):
    topic: str
    student_class: str

class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    session_id: int | None = None    # None = start a new session
    message: str
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
    message: str

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