# 📚 Multimodal AI Study Assistant

An AI-powered learning platform that helps students learn better by generating quizzes, analyzing performance, identifying weak topics, and creating personalized simplified notes.

---

##  Features

-  User Authentication (JWT)
-  Upload PDFs, Images, Videos, and Audio
-  Text Extraction (PDF parsing via `pypdf`, with OCR fallback for scanned pages)
-  Video Analysis (audio transcription + keyframe extraction via Vision LLM)
-  Voice Input (Whisper-based speech-to-text)
-  AI-generated Quizzes
-  Quiz Analytics Dashboard
-  Weak Topic Detection
-  Simplified Notes Generation
-  Semantic Search using Vector Embeddings (RAG)
-  AI Tutor Chat with RAG-based context retrieval
-  Admin Dashboard
-  Lesson Management

---

## 🛠 Tech Stack

### Frontend
- React.js
- Tailwind CSS
- Axios
- React Router
- Vite

### Backend
- FastAPI
- SQLAlchemy
- JWT Authentication (`python-jose`, `passlib`, `bcrypt`)

### AI Components
- Groq API (LLaMA for text generation, Whisper for audio transcription, Vision models for image/video frame analysis)
- Sentence Transformers
- ChromaDB
- EasyOCR
- pdf2image
- OpenCV
- moviepy

### Database
- MySQL (via PyMySQL)

---

## 📂 Project Structure

```text
MULTIMODAL AI ASSISTANT/

│
├── Frontend/
│   │
│   ├── src/
│   │   ├── api/
│   │   │   └── axios.js
│   │   │
│   │   ├── assets/
│   │   │
│   │   ├── components/
│   │   │
│   │   ├── context/
│   │   │
│   │   ├── pages/
│   │   │
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── main.jsx
│   │   └── index.css
│   │
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── eslint.config.js
│   ├── index.html
│   └── README.md
│
├── Routers/
│
├── Services/
│
├── auth.py
├── database.py
├── models.py
├── schemas.py
├── main.py
├── requirements.txt
├── .env
│
└── Chroma_DB/
```

---

## ⚙️ Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL server running locally
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) installed and added to PATH (required by `pdf2image` for scanned-PDF OCR fallback)
- On first run, EasyOCR will download its model weights — this can take a minute and may look like the app is hanging

### Clone Repository

```bash
git clone https://github.com/username/project-name.git

cd project-name
```

---

### Backend Setup

```bash
pip install -r requirements.txt

uvicorn main:app --reload
```

Tables are created automatically in MySQL on first run via `Base.metadata.create_all`, so no manual migration step is needed — just make sure the database itself exists and `DATABASE_URL` points to it.

Backend runs at

```text
http://localhost:8000
```

---

### Frontend Setup

```bash
cd Frontend

npm install

npm run dev
```

Frontend runs at

```text
http://localhost:5173
```

> **Note:** CORS in `main.py` is currently hardcoded to allow only `http://localhost:5173`. If your frontend runs on a different port or you deploy this elsewhere, update `allow_origins` in `main.py` accordingly.

---

## 🔑 Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=

SECRET_KEY=

DATABASE_URL=
```

## System Architecture

![System](Screenshots/architecture.png)

---

## 🚀 Workflow

The platform has two independent content pipelines that converge at a single retrieval layer for the AI Tutor.

### 1️⃣ Lesson Path

1. User selects a topic and education level
2. Groq generates structured notes (`generate_notes`)
3. Notes are saved as a `Note` record in MySQL
4. Notes are embedded and stored in ChromaDB (`source: note`)
5. Quizzes are generated from the note content (`/quiz/generate`)
6. Quiz is attempted and scored
7. Analytics are updated, identifying weak and strong topics
8. Weak topics can trigger simplified note regeneration (`easy_mode=True`), saved as a new `Note` and re-embedded

### 2️⃣ Upload Path

1. User uploads a PDF, image, video, or audio file
2. Content is extracted:
   - PDF → text extraction via `pypdf`, with EasyOCR as a fallback for scanned pages
   - Image → analyzed via Vision LLM
   - Video → audio transcription + keyframe analysis via Vision LLM
   - Audio → transcribed via Whisper (used directly as chat input, not embedded)
3. Extracted content is chunked and embedded into ChromaDB (`source: pdf / image / video`)

### 3️⃣ Tutor Chat (unifies both pipelines)

1. User asks a question, optionally with a new attachment
2. Semantic search retrieves relevant chunks from ChromaDB across both lesson notes and uploaded materials, scoped to the user
3. Retrieved context is injected into the Groq prompt with accurate source labeling
4. AI Tutor responds with an answer grounded in the student's own materials

---

## 📸 Screenshots

### Login Page

![Login](Screenshots/login.png)

### Dashboard Page

![Dashboard](Screenshots/dashboard.png)

### Lesson Page

![Lesson](Screenshots/lesson.png)

### Quiz Page

![Quiz](Screenshots/quiz.png)

### Analytics Dashboard

![Analytics](Screenshots/analytics.png)

### Tutor Page

![Tutor](Screenshots/tutor.png)

### Admin Page (accessible only for the admin)

![Admin](Screenshots/admin.png)

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register user |
| POST | `/login` | Login |
| POST | `/upload/pdf` | Upload and index a PDF |
| POST | `/upload/image` | Analyze and index an image |
| POST | `/upload/audio` | Transcribe audio (Whisper) |
| POST | `/upload/video` | Analyze video (transcript + frames) |
| POST | `/lessons/generate` | Generate an AI lesson on a topic |
| GET | `/lessons/all` | Get all lessons for the user |
| POST | `/lessons/regenerate-weak` | Simplify notes for a weak topic |
| POST | `/quiz/generate` | Generate a quiz from a lesson |
| POST | `/quiz/submit` | Submit answers and get scored results |
| GET | `/analytics` | User's quiz analytics (weak/strong topics) |
| POST | `/chat` | AI Tutor chat (RAG-based) |
| GET | `/admin/users` | List all users *(admin only)* |
| GET | `/admin/stats` | Platform usage stats *(admin only)* |

---

## 🎯 Future Improvements

- Multi-language support
- Mobile application
- Chatbot for Oral Quiz
- Dockerization

---

## 👨‍💻 Developed by

**Karthik Aravind M**

---
