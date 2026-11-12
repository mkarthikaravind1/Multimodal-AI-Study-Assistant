#schemas.py
from datetime import datetime
from typing import Annotated, Literal
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
    loop_round: int = 1             # 1 = original quiz, 2+ = self-healing retest
    passed: bool = False            # score >= 70
    flashcards_added: int = 0       # wrong answers turned into flashcards
    message: str

# ── Self-healing learning loop ────────────────────────────────────────────────
class RemediateRequest(BaseModel):
    quiz_id: int                     # the submitted quiz that scored below 70%

class LessonLite(BaseModel):
    note_id: int
    title: str
    content: str

class RemediationResponse(BaseModel):
    loop_round: int                  # round number of the NEW retest quiz
    missed_count: int
    note: LessonLite                 # targeted fix-up notes
    quiz: QuizResponse               # retest on the same concepts
    message: str

class Attempt(BaseModel):
    quiz_id: int
    score: float
    submitted_at: datetime | None
    loop_round: int

class TopicProgress(BaseModel):
    topic: str
    status: str                      # mastered | recovered | in_recovery | needs_work
    recent_average: float            # average of the last 3 attempts (drives strong/weak)
    latest_score: float
    latest_quiz_id: int
    attempts: list[Attempt]          # oldest → newest

class TopicAverage(BaseModel):
    topic:str
    average_score:float

class AnalyticsResponse(BaseModel):
    strong:list[str]
    weak:list[str]
    topic_breakdown:list[TopicAverage]

class Citation(BaseModel):
    """A clickable source the tutor cited, e.g. [S1]."""
    id: str                          # "S1", "S2", … — matches the tag in the reply text
    type: str                        # note | pdf | image | video
    label: str                       # "lecture.pdf · p. 4", "talk.mp4 · 03:42", "Notes on Graphs"
    filename: str | None = None
    material_id: int | None = None   # uploaded file → GET /upload/materials/{id}/file
    note_id: int | None = None       # lesson → opens it on the Lessons page
    page: int | None = None          # PDF page (1-based)
    start_sec: float | None = None   # video position
    timestamp: str | None = None     # "03:42"

class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str
    sources: list[Citation] = []     # only on assistant messages that cited something

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

# ── Viva / oral exam ──────────────────────────────────────────────────────────
class VivaStartRequest(BaseModel):
    note_id: int
    num_questions: int = Field(default=5, ge=3, le=8)

class VivaAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=3000)

class VivaGradedQuestion(BaseModel):
    question: str
    answer: str
    score: int                       # 0-10
    feedback: str
    ideal_answer: str
    missed_points: list[str]

class VivaState(BaseModel):
    """Full state of a viva — used to start, resume and review one."""
    viva_id: int
    note_id: int
    topic: str
    total_questions: int
    graded: list[VivaGradedQuestion] # questions answered so far, in order
    current_index: int | None        # index of the next question (None when finished)
    current_question: str | None
    finished: bool
    total_score: int | None          # set when finished
    max_score: int
    started_at: datetime | None
    completed_at: datetime | None

class VivaAnswerResponse(BaseModel):
    result: VivaGradedQuestion       # grading of the answer just given
    question_index: int
    state: VivaState                 # updated state (next question or finished)
    flashcard_added: bool = False    # weak answers (< 6/10) become a flashcard

class VivaSummary(BaseModel):
    viva_id: int
    topic: str
    answered: int
    total_questions: int
    total_score: int | None
    max_score: int
    finished: bool
    started_at: datetime | None

# ── Flashcards (spaced repetition) ────────────────────────────────────────────
CardFront = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
CardBack = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]

class FlashcardOut(BaseModel):
    card_id: int
    front: str
    back: str
    topic: str | None
    source: str                      # note | mistake | viva | manual
    note_id: int | None
    due_at: datetime
    interval_days: int
    repetitions: int
    lapses: int
    ease_factor: float
    previews: dict[str, str] | None = None   # {"again": "10m", "hard": "1d", "good": "1d", "easy": "4d"}

class FlashcardCreate(BaseModel):
    front: CardFront
    back: CardBack
    topic: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None

class FlashcardUpdate(BaseModel):
    front: CardFront | None = None
    back: CardBack | None = None

class FlashcardGenerateRequest(BaseModel):
    note_id: int
    count: int = Field(default=8, ge=3, le=15)

class FlashcardGenerateResponse(BaseModel):
    added: list[FlashcardOut]
    skipped_duplicates: int
    message: str

class ReviewRequest(BaseModel):
    rating: Literal["again", "hard", "good", "easy"]

class FlashcardStats(BaseModel):
    total: int
    due_now: int
    new: int                         # never reviewed
    learning: int                    # reviewed, interval < 21 days
    mastered: int                    # interval >= 21 days
    reviewed_today: int
    next_due_at: datetime | None     # when the next card becomes due (if none due now)

class DueCards(BaseModel):
    cards: list[FlashcardOut]
    stats: FlashcardStats
