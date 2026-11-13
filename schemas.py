#schemas.py
from datetime import date, datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints, field_validator

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

LanguageCode = Literal["en", "hi", "ta", "hinglish", "tanglish", "auto"]

class MeResponse(BaseModel):
    username: str
    role: str
    student_class: str | None     # last education level the student used
    preferred_language: LanguageCode = "en"

class ProfileUpdate(BaseModel):
    preferred_language: LanguageCode

QuestionType = Literal["mcq", "true_false", "fill_blank", "numerical"]
Difficulty = Literal["easy", "medium", "hard", "mixed"]

# What the student sees — never the answer or explanations, so the key can't be read in DevTools
class QuestionPublic(BaseModel):
    question: str
    type: QuestionType = "mcq"
    options: list[str] = []          # mcq: 4 · true_false: ["True", "False"] · typed answers: []
    difficulty: str | None = None    # easy | medium | hard
    unit: str | None = None          # numerical answers, e.g. "m/s"

# Request — what frontend sends
class QuizRequest(BaseModel):
    note_id: int
    topic: Topic
    question_types: list[QuestionType] = Field(
        default=["mcq", "true_false", "fill_blank"], min_length=1, max_length=4
    )
    difficulty: Difficulty = "medium"
    count: int = Field(default=5, ge=3, le=10)

    @field_validator("question_types", mode="before")
    @classmethod
    def _dedupe_types(cls, value):
        # ["mcq", "mcq", "true_false"] → ["mcq", "true_false"] (before the max-4 length check)
        return list(dict.fromkeys(value)) if isinstance(value, list) else value

# Response — what frontend gets back
class QuizResponse(BaseModel):
    quiz_id: int
    topic: str
    questions: list[QuestionPublic]
    total_questions: int
    difficulty: str = "medium"
    message: str 

# One answer the student submits
class SubmittedAnswer(BaseModel):
    question: str = Field(max_length=1000)       # must match exactly what was generated
    user_answer: str = Field(max_length=1000)    # what the student picked

# Full submission request
class QuizSubmitRequest(BaseModel):
    quiz_id: int
    answers: list[SubmittedAnswer] = Field(max_length=20)

# Per question result — was it right or wrong, and why?
class QuestionResult(BaseModel):
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    type: str = "mcq"
    difficulty: str | None = None
    unit: str | None = None
    explanation: str | None = None   # why the correct answer is correct
    why_wrong: str | None = None     # why the option YOU picked is wrong (mcq / true-false)
    note: str | None = None          # e.g. "Accepted — small spelling difference"

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

# ── Handwritten solution checking ─────────────────────────────────────────────
class SolutionStep(BaseModel):
    text: str
    status: Literal["correct", "error", "follows_error", "unclear"]
    comment: str
    correction: str

class SolutionCheckOut(BaseModel):
    check_id: int
    topic: str | None
    problem: str | None
    expected_answer: str | None
    final_answer: str | None
    filename: str
    steps: list[SolutionStep]
    verdict: Literal["correct", "incorrect", "incomplete", "unreadable"]
    score: int | None                # 0-10 (None when the photo couldn't be read)
    first_error_step: int | None     # 0-based index into steps
    error_type: str | None           # arithmetic | algebra | sign | concept | ...
    summary: str
    hint: str
    correct_answer: str
    answer_matches_expected: bool | None
    rechecks: int
    flashcard_added: bool = False
    created_at: datetime | None
    updated_at: datetime | None

class SolutionSummary(BaseModel):
    check_id: int
    title: str                       # problem (shortened) or file name
    topic: str | None
    verdict: str
    score: int | None
    created_at: datetime | None

SolutionStepText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

class SolutionRecheckRequest(BaseModel):
    """The student's corrected transcription — steps they say were misread."""
    steps: list[SolutionStepText] = Field(min_length=1, max_length=40)
    problem: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    final_answer: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


# ── Exam planner ──────────────────────────────────────────────────────────────
PlanTopicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]

class PlanTopicIn(BaseModel):
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    topic: PlanTopicName
    size: int = Field(default=2, ge=1, le=3)       # 1 small · 2 medium · 3 large

class PlanTopicOut(BaseModel):
    unit: str
    topic: str
    size: int
    score: float | None              # recent quiz/viva score on a matching topic
    matched_topic: str | None        # the history topic it was matched with
    status: Literal["weak", "ok", "strong", "new"]
    weight: float                    # time multiplier (weak topics get more)
    minutes: int = 0                 # learning time planned (0 before a plan exists)

class SyllabusExtractResponse(BaseModel):
    exam_name: str
    topics: list[PlanTopicOut]
    syllabus_filename: str | None

class PlanCreate(BaseModel):
    exam_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    exam_date: date
    start_date: date                 # the student's "today" (their local date)
    minutes_per_day: int = Field(default=120, ge=30, le=720)
    rest_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(default=[], max_length=6)
    topics: list[PlanTopicIn] = Field(min_length=1, max_length=40)
    syllabus_filename: Annotated[str, StringConstraints(max_length=255)] | None = None

class PlanItem(BaseModel):
    id: str
    topic: str
    kind: Literal["learn", "practice", "review", "revise", "quiz", "mock"]
    minutes: int
    done: bool

class PlanDay(BaseModel):
    date: date
    rest: bool
    exam: bool
    items: list[PlanItem]

class PlanProgress(BaseModel):
    done_minutes: int
    total_minutes: int
    done_items: int
    total_items: int

class PlanOut(BaseModel):
    plan_id: int
    exam_name: str
    exam_date: date
    start_date: date
    minutes_per_day: int
    rest_days: list[int]
    topics: list[PlanTopicOut]
    days: list[PlanDay]
    syllabus_filename: str | None
    progress: PlanProgress
    created_at: datetime | None
    updated_at: datetime | None

class PlanSummary(BaseModel):
    plan_id: int
    exam_name: str
    exam_date: date
    topics: int
    progress: PlanProgress
    created_at: datetime | None

class PlanItemUpdate(BaseModel):
    done: bool

class ReplanRequest(BaseModel):
    today: date                      # the student's local date


# ── Concept maps / mind maps ──────────────────────────────────────────────────
class MapNode(BaseModel):
    id: str
    label: str
    parent: str                      # "root" or an earlier node's id
    relation: str
    detail: str

class MapLink(BaseModel):
    model_config = {"populate_by_name": True}
    from_: str = Field(alias="from")
    to: str
    label: str

class MapGraph(BaseModel):
    central: str
    nodes: list[MapNode]
    links: list[MapLink]

class ConceptMapRequest(BaseModel):
    source_type: Literal["note", "material"]
    source_id: int
    regenerate: bool = False         # False → return the saved map if there is one

class ConceptMapOut(BaseModel):
    map_id: int
    source_type: str
    source_id: int
    source_kind: str                 # lesson | pdf | video
    title: str
    graph: MapGraph
    created_at: datetime | None
    updated_at: datetime | None

class ConceptMapSummary(BaseModel):
    map_id: int
    source_type: str
    source_id: int
    title: str
    nodes: int
    created_at: datetime | None

class MapSourceNote(BaseModel):
    note_id: int
    title: str
    map_id: int | None

class MapSourceMaterial(BaseModel):
    material_id: int
    filename: str
    file_type: str
    map_id: int | None

class MapSources(BaseModel):
    notes: list[MapSourceNote]
    materials: list[MapSourceMaterial]
