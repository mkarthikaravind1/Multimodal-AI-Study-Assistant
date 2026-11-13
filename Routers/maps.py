"""
Concept maps / mind maps.

GET    /maps/sources     lessons + uploaded PDFs/videos that can be mapped (and their saved map, if any)
POST   /maps             make (or fetch the saved) map for a lesson or upload; regenerate=true makes a new one
GET    /maps             the user's maps
GET    /maps/{id}        one map
DELETE /maps/{id}
"""
from typing import cast
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, utcnow, as_utc
from models import ConceptMap, Note, UploadedMaterial, User
from schemas import (
    ConceptMapRequest, ConceptMapOut, ConceptMapSummary, MapSources, MapSourceNote, MapSourceMaterial,
)
from Services.concept_map import generate_graph, title_from_note, MapError
from Services.embedding_service import get_material_text
from Services.language import language_note

router = APIRouter(prefix="/maps", tags=["Concept maps"])

MAPPABLE_TYPES = ("pdf", "video")       # images are a single picture — not much to map
MIN_SOURCE_CHARS = 200


def _kind(db: Session, m: ConceptMap) -> str:
    if m.source_type == "note":
        return "lesson"
    material = db.get(UploadedMaterial, m.source_id)
    return cast(str, material.file_type) if material else "pdf"


def _out(db: Session, m: ConceptMap) -> ConceptMapOut:
    return ConceptMapOut(
        map_id=cast(int, m.map_id),
        source_type=cast(str, m.source_type),
        source_id=cast(int, m.source_id),
        source_kind=_kind(db, m),
        title=cast(str, m.title),
        graph=m.graph,                          # type: ignore
        created_at=as_utc(m.created_at),        # type: ignore
        updated_at=as_utc(m.updated_at),        # type: ignore
    )


def _get_map(db: Session, map_id: int, user_id: int) -> ConceptMap:
    m = db.query(ConceptMap).filter(ConceptMap.map_id == map_id, ConceptMap.user_id == user_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Map not found")
    return m


@router.get("/sources", response_model=MapSources)
def map_sources(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.user_id
    saved = {
        (m.source_type, m.source_id): m.map_id
        for m in db.query(ConceptMap).filter(ConceptMap.user_id == user_id).all()
    }
    notes = db.query(Note).filter(Note.user_id == user_id).order_by(Note.created_at.desc()).all()
    materials = db.query(UploadedMaterial).filter(
        UploadedMaterial.user_id == user_id, UploadedMaterial.file_type.in_(MAPPABLE_TYPES)
    ).order_by(UploadedMaterial.uploaded_at.desc()).all()
    return MapSources(
        notes=[MapSourceNote(note_id=n.note_id, title=n.title, map_id=saved.get(("note", n.note_id)))      # type: ignore
               for n in notes],
        materials=[MapSourceMaterial(material_id=m.material_id, filename=m.filename, file_type=m.file_type,  # type: ignore
                                     map_id=saved.get(("material", m.material_id)))
                   for m in materials],
    )


@router.post("", response_model=ConceptMapOut)
def make_map(request: ConceptMapRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = cast(int, current_user.user_id)
    existing = db.query(ConceptMap).filter(
        ConceptMap.user_id == user_id,
        ConceptMap.source_type == request.source_type,
        ConceptMap.source_id == request.source_id,
    ).first()

    # Ownership is checked even when a saved map exists
    if request.source_type == "note":
        note = db.query(Note).filter(Note.note_id == request.source_id, Note.user_id == user_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Lesson not found")
        title = title_from_note(cast(str, note.title))
        content, kind = cast(str, note.content), "lesson notes"
    else:
        material = db.query(UploadedMaterial).filter(
            UploadedMaterial.material_id == request.source_id, UploadedMaterial.user_id == user_id
        ).first()
        if not material:
            raise HTTPException(status_code=404, detail="Upload not found")
        if material.file_type not in MAPPABLE_TYPES:
            raise HTTPException(status_code=400, detail="Maps can be made from lessons, PDFs and videos.")
        title = cast(str, material.filename).rsplit(".", 1)[0]
        kind = "video transcript and on-screen content" if material.file_type == "video" else "document"
        content = ""
        if not existing or request.regenerate:
            content = get_material_text(cast(int, material.material_id), user_id, cast(str, material.file_type))

    if existing and not request.regenerate:
        return _out(db, existing)

    if len(content.strip()) < MIN_SOURCE_CHARS:
        raise HTTPException(status_code=400, detail="There isn't enough text in this to make a map.")

    try:
        graph = generate_graph(
            content, title, kind,
            # labels in the student's language ("auto": the language of the material)
            language_note=language_note(current_user.preferred_language, content),    # type: ignore
        )
    except MapError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if existing:
        existing.graph = graph                  # type: ignore
        existing.title = title[:255]            # type: ignore
        existing.updated_at = utcnow()          # type: ignore
        m = existing
    else:
        m = ConceptMap(
            user_id=user_id, source_type=request.source_type, source_id=request.source_id,
            title=title[:255], graph=graph, created_at=utcnow(),
        )
        db.add(m)
    db.commit()
    db.refresh(m)
    return _out(db, m)


@router.get("", response_model=list[ConceptMapSummary])
def list_maps(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    maps = db.query(ConceptMap).filter(
        ConceptMap.user_id == current_user.user_id
    ).order_by(ConceptMap.created_at.desc()).all()
    return [
        ConceptMapSummary(
            map_id=m.map_id, source_type=m.source_type, source_id=m.source_id,     # type: ignore
            title=m.title, nodes=len((m.graph or {}).get("nodes", [])),            # type: ignore
            created_at=as_utc(m.created_at),                                       # type: ignore
        )
        for m in maps
    ]


@router.get("/{map_id}", response_model=ConceptMapOut)
def get_map(map_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _out(db, _get_map(db, map_id, cast(int, current_user.user_id)))


@router.delete("/{map_id}")
def delete_map(map_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    m = _get_map(db, map_id, cast(int, current_user.user_id))
    db.delete(m)
    db.commit()
    return {"message": "Map deleted"}
