from typing import cast
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import io
import os
import tempfile
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
from Services.embedding_service import chunk_text, add_pdf_chunks_to_vectorstore, delete_material_vectors
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


def save_material_and_index(
    db: Session, user_id: int, filename: str, file_type: str, chunks: list[str]
) -> UploadedMaterial:
    """
    Saves the MySQL row and the ChromaDB vectors together.
    The row is only committed once the vectors are stored; if either step
    fails, both are rolled back so MySQL and ChromaDB never disagree.
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
    try:
        add_pdf_chunks_to_vectorstore(
            material_id=material_id,
            chunks=chunks,
            user_id=user_id,
            filename=filename,
            source=file_type
        )
        db.commit()
    except Exception:
        db.rollback()
        try:
            delete_material_vectors(material_id, file_type)
        except Exception:
            pass
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

    # Step 3 — Extract text from PDF using PyPDF
    try:
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        full_text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:                       # some pages might be empty/images
                full_text += page_text + "\n"
    except PdfReadError:
        raise HTTPException(status_code=400, detail="This file is not a valid PDF or is corrupted.")

    # OCR fallback for scanned / image-only PDFs
    if not full_text.strip():
        try:
            images = convert_from_bytes(file_bytes)
        except PDFInfoNotInstalledError:
            raise HTTPException(
                status_code=500,
                detail="This PDF has no text layer and OCR is unavailable: Poppler is not installed on the server."
            )

        reader = get_ocr_reader()
        for image in images:
            result = cast(list[str], reader.readtext(np.array(image), detail=0))
            full_text += " ".join(result) + "\n"

    if not full_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any text from this PDF."
        )

    # Step 4 — Chunk, save to MySQL + ChromaDB together
    chunks = chunk_text(full_text)
    material = save_material_and_index(db, cast(int, current_user.user_id), filename, "pdf", chunks)

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
    answer = analyze_image(image_bytes, question, mime_type=cast(str, file.content_type))

    # Step 2 — Store question + answer in ChromaDB so the tutor can retrieve it later
    combined_text = (
        f"Image: {filename}\n"
        f"Question asked: {question}\n"
        f"Visual analysis: {answer}"
    )
    material = save_material_and_index(db, user_id, filename, "image", chunk_text(combined_text))

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

        # Step 4 — Index the summary AND the full transcript for RAG.
        #          The summary is good for overview questions; the transcript
        #          keeps the specific details the summary leaves out.
        chunks = chunk_text(result["combined_summary"])
        if result["has_audio"]:
            chunks += chunk_text(f"Transcript of {filename}: {result['transcript']}")

        save_material_and_index(db, cast(int, current_user.user_id), filename, "video", chunks)

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
    db.delete(material)
    db.commit()
    return {"message": f"Deleted {material.filename}"}
