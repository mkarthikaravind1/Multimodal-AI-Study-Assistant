from typing import cast
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import io
import os
import shutil
import mimetypes
import tempfile
from pathlib import Path
from fastapi.responses import FileResponse
import numpy as np
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError

from database import get_db, utcnow, as_utc
from models import UploadedMaterial, User
from schemas import (
    PDFUploadResponse, ImageAnalysisResponse, AudioTranscriptResponse,
    VideoAnalysisResponse, MaterialResponse,
)
from auth import get_current_user
from Services.language import language_note
from Services.embedding_service import (
    chunk_text, chunk_timed_segments, add_pdf_chunks_to_vectorstore, delete_material_vectors,
)
from Services.citations import format_timestamp
from Services.vision_service import analyze_image
from Services.audio_service import transcribe_audio
from Services.video_service import analyze_video
from Routers.tutor import load_or_new_session, save_session

router = APIRouter(prefix="/upload", tags=["Upload"])

MB = 1024 * 1024
MAX_PDF_BYTES   = 20 * MB
MAX_IMAGE_BYTES = 4 * MB     # Groq vision rejects base64 images much larger than this
MAX_AUDIO_BYTES = 25 * MB    # Groq Whisper upload limit
MAX_VIDEO_BYTES = 200 * MB

# Original files are kept here so citations can open them (PDF page, video timestamp).
# Git-ignored. Layout: uploads/<user_id>/<material_id><ext>
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

# ── EasyOCR is heavy (model download + ~1-2 s load), and only needed for
#    scanned PDFs, so it's loaded on first use instead of at server startup.
_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'])     # english
    return _ocr_reader


def read_upload(file: UploadFile, max_bytes: int, label: str) -> bytes:
    """
    Reads at most max_bytes + 1 bytes so an oversized upload is rejected
    without loading the whole file into memory.
    """
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"{label} is too large. Maximum size is {max_bytes // MB} MB."
        )
    if not data:
        raise HTTPException(status_code=400, detail=f"{label} is empty.")
    return data


def extract_pdf_pages(file_bytes: bytes) -> list[str]:
    """
    Text of every page (index 0 = page 1), with an OCR fallback for scanned
    PDFs. Raises HTTPException with a readable message if nothing can be read.
    Shared by PDF uploads and the exam planner's syllabus upload.
    """
    try:
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        page_texts = [page.extract_text() or "" for page in pdf_reader.pages]
    except PdfReadError:
        raise HTTPException(status_code=400, detail="This file is not a valid PDF or is corrupted.")

    # OCR fallback for scanned / image-only PDFs
    if not "".join(page_texts).strip():
        try:
            images = convert_from_bytes(file_bytes)
        except PDFInfoNotInstalledError:
            raise HTTPException(
                status_code=500,
                detail="This PDF has no text layer and OCR is unavailable: Poppler is not installed on the server."
            )

        reader = get_ocr_reader()
        page_texts = [
            " ".join(cast(list[str], reader.readtext(np.array(image), detail=0)))
            for image in images
        ]

    if not "".join(page_texts).strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any text from this PDF."
        )
    return page_texts


def save_material_and_index(
    db: Session,
    user_id: int,
    filename: str,
    file_type: str,
    chunks: list[str],
    chunk_meta: list[dict] | None = None,
    file_bytes: bytes | None = None,
    source_path: str | None = None,
) -> UploadedMaterial:
    """
    Saves the MySQL row, the ChromaDB vectors and (optionally) the original
    file together. The row is only committed once everything else succeeded;
    if any step fails, all of it is rolled back so the stores never disagree.

    chunk_meta : per-chunk citation info, e.g. {"page": 3} or {"start_sec": 75.0}
    file_bytes / source_path : the original upload, kept for clickable citations
    """
    material = UploadedMaterial(
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        total_chunks=len(chunks),
        uploaded_at=utcnow()
    )
    db.add(material)
    db.flush()      # assigns material_id without committing

    material_id = cast(int, material.material_id)
    stored_file: Path | None = None
    try:
        add_pdf_chunks_to_vectorstore(
            material_id=material_id,
            chunks=chunks,
            user_id=user_id,
            filename=filename,
            source=file_type,
            chunk_meta=chunk_meta,
        )

        if file_bytes is not None or source_path is not None:
            ext = os.path.splitext(filename)[1].lower() or ""
            stored_file = UPLOAD_DIR / str(user_id) / f"{material_id}{ext}"
            stored_file.parent.mkdir(parents=True, exist_ok=True)
            if file_bytes is not None:
                stored_file.write_bytes(file_bytes)
            else:
                shutil.copyfile(cast(str, source_path), stored_file)
            material.stored_path = str(stored_file.relative_to(UPLOAD_DIR))   # type: ignore

        db.commit()
    except Exception:
        db.rollback()
        try:
            delete_material_vectors(material_id, file_type)
        except Exception:
            pass
        if stored_file is not None and stored_file.exists():
            stored_file.unlink()
        raise

    db.refresh(material)
    return material


@router.post("/pdf", response_model=PDFUploadResponse)
def upload_pdf(file: UploadFile = File(...),db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    # Step 1 — Validate file type (case-insensitive: Notes.PDF is fine)
    filename = file.filename or ""
    if not (filename.lower().endswith(".pdf") or file.content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Step 2 — Read file bytes (size-limited)
    file_bytes = read_upload(file, MAX_PDF_BYTES, "PDF")

    # Step 3 — Extract text page by page (page numbers are kept for citations)
    page_texts = extract_pdf_pages(file_bytes)

    # Step 4 — Chunk each page separately so every chunk knows its page number
    chunks: list[str] = []
    chunk_meta: list[dict] = []
    for page_number, page_text in enumerate(page_texts, start=1):
        for chunk in chunk_text(page_text):
            chunks.append(chunk)
            chunk_meta.append({"page": page_number})

    material = save_material_and_index(
        db, cast(int, current_user.user_id), filename, "pdf", chunks,
        chunk_meta=chunk_meta, file_bytes=file_bytes,
    )

    return PDFUploadResponse(
        material_id=material.material_id,   # type: ignore
        filename=filename,
        total_chunks=len(chunks),
        message=f"PDF uploaded and indexed successfully. {len(chunks)} chunks stored."
    )


@router.post("/image", response_model=ImageAnalysisResponse)
def upload_image(
    file: UploadFile = File(...),
    question: str = Form(default="Explain this image in detail.", max_length=2000),
    session_id: int | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Only JPEG, PNG, and WebP images accepted. Got: {file.content_type}"
        )

    image_bytes = read_upload(file, MAX_IMAGE_BYTES, "Image")
    filename = file.filename or "image"
    user_id = cast(int, current_user.user_id)

    # Validate the session BEFORE the (slow, paid) vision call
    session = load_or_new_session(db, session_id, user_id)

    # Step 1 — Get vision LLM answer (send the real MIME type)
    # (the reply-language instruction goes to the model only — the stored question stays as typed)
    lang = language_note(current_user.preferred_language, question)     # type: ignore
    answer = analyze_image(image_bytes, f"{question}\n\n{lang}", mime_type=cast(str, file.content_type))

    # Step 2 — Store question + answer in ChromaDB so the tutor can retrieve it later
    combined_text = (
        f"Image: {filename}\n"
        f"Question asked: {question}\n"
        f"Visual analysis: {answer}"
    )
    material = save_material_and_index(
        db, user_id, filename, "image", chunk_text(combined_text), file_bytes=image_bytes
    )

    # Step 3 — Add the exchange to the tutor conversation, so follow-up
    #          questions in chat ("explain that diagram more") have context
    history = list(session.messages or [])      # type: ignore
    history.append({"role": "user", "content": f"[Uploaded image: {filename}] {question}"})
    history.append({"role": "assistant", "content": answer})
    session = save_session(db, session, history)

    return ImageAnalysisResponse(
        material_id=cast(int, material.material_id),
        filename=filename,
        question=question,
        answer=answer,
        session_id=cast(int, session.session_id),
        message="Image analysed and stored in context successfully."
    )


@router.post("/audio", response_model=AudioTranscriptResponse)
def upload_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    # Step 1 — Validate file type (ignore codec suffix like "audio/webm;codecs=opus")
    allowed_types = [
        "audio/mpeg",       # .mp3
        "audio/wav",        # .wav
        "audio/mp4",        # .m4a / Safari recordings
        "audio/x-m4a",
        "audio/webm",       # .webm (Chrome recordings)
        "audio/ogg",        # .ogg (Firefox recordings)
        "video/webm"        # some browsers send this for audio recordings
    ]
    base_type = (file.content_type or "").split(";")[0].strip()

    if base_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file.content_type}. "
                   f"Accepted: mp3, wav, m4a, webm, ogg"
        )

    # Step 2 — Read audio bytes
    audio_bytes = read_upload(file, MAX_AUDIO_BYTES, "Audio")

    # Step 3 — Transcribe via Whisper
    transcript = transcribe_audio(audio_bytes, file.filename or "recording.webm")

    # Step 4 — Return transcript
    # Frontend puts this text into the chat input box
    # User reviews it and sends through /chat normally
    return AudioTranscriptResponse(
        filename=file.filename or "recording",
        transcript=transcript,
        message="Audio transcribed successfully. Use transcript to ask your question."
    )


@router.post("/video", response_model=VideoAnalysisResponse)
def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Step 1 — Validate file type
    allowed_types = ["video/mp4", "video/mpeg", "video/webm", "video/quicktime"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: {file.content_type}. "
                   f"Accepted: mp4, mpeg, webm, mov"
        )

    filename = file.filename or "video.mp4"

    # Step 2 — Save video to temp file
    # moviepy and opencv need a file PATH, not bytes
    video_bytes = read_upload(file, MAX_VIDEO_BYTES, "Video")
    with tempfile.NamedTemporaryFile(
        suffix=os.path.splitext(filename)[1] or ".mp4",
        delete=False
    ) as temp_video:
        temp_video.write(video_bytes)
        temp_video_path = temp_video.name
    del video_bytes

    try:
        # Step 3 — Full video analysis (audio + frames)
        print(f"[Video] Starting analysis of {filename}...")
        try:
            result = analyze_video(temp_video_path, filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Step 4 — Index for RAG, keeping timestamps for clickable citations:
        #   • transcript chunks, each with the time its speech starts
        #   • frame descriptions, each with the time of the frame
        #   • the overall summary (no single timestamp)
        chunks: list[str] = []
        chunk_meta: list[dict] = []
        for text, start in chunk_timed_segments(result["segments"]):
            chunks.append(text)
            chunk_meta.append({"start_sec": round(start, 1)})
        for frame in result["timed_frames"]:
            chunks.append(f"On screen at {format_timestamp(frame['start'])}: {frame['text']}")
            chunk_meta.append({"start_sec": round(frame["start"], 1)})
        if result["has_audio"] and not result["segments"]:
            # Whisper returned text without segments — still index it, untimed
            for text in chunk_text(result["transcript"]):
                chunks.append(text)
                chunk_meta.append({})
        for text in chunk_text(result["combined_summary"]):
            chunks.append(text)
            chunk_meta.append({})

        save_material_and_index(
            db, cast(int, current_user.user_id), filename, "video", chunks,
            chunk_meta=chunk_meta, source_path=temp_video_path,
        )

        return VideoAnalysisResponse(
            filename=filename,
            transcript=result["transcript"],
            frame_descriptions=result["frame_descriptions"],
            combined_summary=result["combined_summary"],
            total_frames_analyzed=len(result["frame_descriptions"]),
            message=(
                f"Video analyzed successfully. "
                f"Transcript + {len(result['frame_descriptions'])} frames processed. "
                f"Content indexed for Q&A."
            )
        )

    finally:
        # Always clean up temp file even if something crashes
        os.unlink(temp_video_path)


# ── Uploaded materials: list + delete (delete also removes the vectors,
#    so deleted content can no longer show up in tutor answers) ──────────────

@router.get("/materials", response_model=list[MaterialResponse])
def list_materials(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    materials = db.query(UploadedMaterial).filter(
        UploadedMaterial.user_id == current_user.user_id
    ).order_by(UploadedMaterial.uploaded_at.desc()).all()
    return [
        MaterialResponse(
            material_id=m.material_id,          # type: ignore
            filename=m.filename,                # type: ignore
            file_type=m.file_type,              # type: ignore
            total_chunks=m.total_chunks,        # type: ignore
            uploaded_at=as_utc(m.uploaded_at),  # type: ignore
        )
        for m in materials
    ]


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    material = db.query(UploadedMaterial).filter(
        UploadedMaterial.material_id == material_id,
        UploadedMaterial.user_id == current_user.user_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    delete_material_vectors(material_id, cast(str, material.file_type))
    if material.stored_path:
        stored = UPLOAD_DIR / str(material.stored_path)
        if stored.exists():
            stored.unlink()
    db.delete(material)
    db.commit()
    return {"message": f"Deleted {material.filename}"}


@router.get("/materials/{material_id}/file")
def get_material_file(material_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Streams the original uploaded file — only to its owner.
    Used by clickable citations (PDF opened at a page, video at a timestamp).
    """
    material = db.query(UploadedMaterial).filter(
        UploadedMaterial.material_id == material_id,
        UploadedMaterial.user_id == current_user.user_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    if not material.stored_path:
        raise HTTPException(
            status_code=404,
            detail="The original file isn't stored (it was uploaded before citations were added)."
        )

    path = (UPLOAD_DIR / str(material.stored_path)).resolve()
    if UPLOAD_DIR.resolve() not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="File not found on the server")

    media_type = mimetypes.guess_type(str(material.filename))[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
