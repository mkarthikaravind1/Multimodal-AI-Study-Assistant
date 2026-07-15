from typing import cast
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
import io
from pypdf import PdfReader
import easyocr
import numpy as np
from pdf2image import convert_from_bytes    

from database import get_db
from models import UploadedMaterial, User
from schemas import PDFUploadResponse,ImageAnalysisResponse
from auth import get_current_user
from Services.embedding_service import chunk_text, add_pdf_chunks_to_vectorstore
from Services.vision_service import analyze_image
from Services.audio_service import transcribe_audio
from schemas import AudioTranscriptResponse
import tempfile
import os
from Services.video_service import analyze_video
from schemas import VideoAnalysisResponse

router = APIRouter(prefix="/upload", tags=["Upload"])
reader = easyocr.Reader(['en'])     #english

@router.post("/pdf", response_model=PDFUploadResponse)
def upload_pdf(file: UploadFile = File(...),db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    # Step 1 — Validate file type
    if file.filename is None or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Step 2 — Read file bytes
    file_bytes = file.file.read()

    #Step 3 — Extract text from PDF using PyPDF
    pdf_reader = PdfReader(io.BytesIO(file_bytes))

    full_text = ""
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:                       # some pages might be empty/images
            full_text += page_text + "\n"

    # OCR fallback
    if not full_text.strip():
        images = convert_from_bytes(file_bytes)

        for image in images:
            image_np = np.array(image)
            result = cast(list[str], reader.readtext(image_np, detail=0))
            page_text = " ".join(result)
            full_text += page_text + "\n"

    if not full_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from PDF. It may be scanned/image-based."
        )

    # Step 4 — Chunk the text
    chunks = chunk_text(full_text)

    # Step 5 — Save metadata to MySQL first (to get material_id)
    new_material = UploadedMaterial(
        user_id=current_user.user_id,
        filename=file.filename,
        file_type="pdf",
        total_chunks=len(chunks),
        uploaded_at=datetime.utcnow()
    )
    db.add(new_material)
    db.commit()
    db.refresh(new_material)

    # Step 6 — Store chunks in ChromaDB
    add_pdf_chunks_to_vectorstore(
        material_id=cast(int,new_material.material_id),   
        chunks=chunks,
        user_id=cast(int,current_user.user_id),
        filename=file.filename                   
    )

    return PDFUploadResponse(
        material_id=new_material.material_id,   # type: ignore
        filename=file.filename,                  # type: ignore
        total_chunks=len(chunks),
        message=f"PDF uploaded and indexed successfully. {len(chunks)} chunks stored."
    )

@router.post("/image", response_model=ImageAnalysisResponse)
def upload_image(
    file: UploadFile = File(...),
    question: str = Form(default="Explain this image in detail."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Only JPEG, PNG, and WebP images accepted. Got: {file.content_type}"
        )
 
    image_bytes = file.file.read()
 
    # Step 1 — Get vision LLM answer
    answer = analyze_image(image_bytes, question)
 
    # Step 2 — Build a text chunk from question + answer and store in ChromaDB
    # This makes the image analysis retrievable by the tutor via RAG
    combined_text = (
        f"Image: {file.filename}\n"
        f"Question asked: {question}\n"
        f"Visual analysis: {answer}"
    )
    chunks = chunk_text(combined_text)
 
    # Step 3 — Save metadata to MySQL to get material_id
    new_material = UploadedMaterial(
        user_id=current_user.user_id,
        filename=file.filename,
        file_type="image",
        total_chunks=len(chunks),
        uploaded_at=datetime.utcnow()
    )
    db.add(new_material)
    db.commit()
    db.refresh(new_material)
 
    # Step 4 — Store in ChromaDB
    add_pdf_chunks_to_vectorstore(
        material_id=cast(int, new_material.material_id),
        chunks=chunks,
        user_id=cast(int, current_user.user_id),
        filename=str(file.filename),
        source="image"
    )
 
    return ImageAnalysisResponse(
        material_id=cast(int, new_material.material_id),
        filename=file.filename,         # type: ignore
        question=question,
        answer=answer,
        message="Image analysed and stored in context successfully."
    )
# @router.post("/image", response_model=ImageAnalysisResponse)
# def upload_image(
#     file: UploadFile = File(...),
#     question: str = Form(default="Explain this image in detail."),
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     # Step 1 — Validate file type
#     allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
#     if file.content_type not in allowed_types:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Only JPEG, PNG, and WebP images accepted. Got: {file.content_type}"
#         )

#     # Step 2 — Read image bytes
#     image_bytes = file.file.read()

#     # Step 3 — Send to Vision LLM
#     answer = analyze_image(image_bytes, question)

#     # Step 4 — Return response
#     return ImageAnalysisResponse(
#         filename=file.filename,     # type: ignore
#         question=question,
#         answer=answer
#     )

@router.post("/audio", response_model=AudioTranscriptResponse)
def upload_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Step 1 — Validate file type
    allowed_types = [
        "audio/mpeg",       # .mp3
        "audio/wav",        # .wav
        "audio/mp4",        # .m4a
        "audio/x-m4a",
        "audio/webm",       # .webm (browser recorded format)
        "audio/ogg",        # .ogg
        "video/webm"        # some browsers send this for audio recordings
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file.content_type}. "
                   f"Accepted: mp3, wav, m4a, webm, ogg"
        )

    # Step 2 — Read audio bytes
    audio_bytes = file.file.read()

    # Step 3 — Transcribe via Whisper
    transcript = transcribe_audio(audio_bytes, file.filename)   # type: ignore

    # Step 4 — Return transcript
    # Frontend puts this text into the chat input box
    # User reviews it and sends through /chat normally
    return AudioTranscriptResponse(
        filename=file.filename,     # type: ignore
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

    # Step 2 — Save video to temp file
    # moviepy and opencv need a file PATH, not bytes
    # so we must write to disk first
    with tempfile.NamedTemporaryFile(
        suffix=".mp4",
        delete=False
    ) as temp_video:
        temp_video.write(file.file.read())
        temp_video_path = temp_video.name

    try:
        # Step 3 — Full video analysis (audio + frames)
        print(f"[Video] Starting analysis of {file.filename}...")
        result = analyze_video(temp_video_path, file.filename)   # type: ignore

        # Step 4 — Store combined summary in ChromaDB for RAG
        combined_text = result["combined_summary"]
        chunks = chunk_text(combined_text)

        # Save to MySQL first to get material_id
        new_material = UploadedMaterial(
            user_id=current_user.user_id,
            filename=file.filename,             # type: ignore
            file_type="video",
            total_chunks=len(chunks),
            uploaded_at=datetime.utcnow()
        )
        db.add(new_material)
        db.commit()
        db.refresh(new_material)

        # Store in ChromaDB
        add_pdf_chunks_to_vectorstore(
            material_id=new_material.material_id,   # type: ignore
            chunks=chunks,
            user_id=cast(int,current_user.user_id),
            filename=file.filename ,                  # type: ignore
            source="video"
        )

        return VideoAnalysisResponse(
            filename=file.filename,                          # type: ignore
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