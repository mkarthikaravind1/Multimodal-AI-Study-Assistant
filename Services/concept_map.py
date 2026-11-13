"""
Concept maps / mind maps from a lesson, a PDF or a video.

The model returns a small graph — never Mermaid code (hand-written Mermaid from
an 8B model breaks on the first stray bracket). The frontend turns the
validated graph into Mermaid itself, so one graph gives both views:

  mind map     — the tree (each node's parent)
  concept map  — the tree with relation labels on the edges, plus cross-links

Stored graph shape:
  {"central": "Photosynthesis",
   "nodes": [{"id": "n1", "label": "Chlorophyll", "parent": "root",
              "relation": "uses", "detail": "Green pigment that absorbs light"}],
   "links": [{"from": "n1", "to": "n4", "label": "powers"}]}
  "root" is the central idea. Parents always come before their children.
"""
import os
import re
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MAX_SOURCE_CHARS = 10000
MAX_NODES = 30
MIN_NODES = 3
MAX_LINKS = 12
MAX_DEPTH = 4
MAX_LABEL = 60
MAX_RELATION = 30
MAX_DETAIL = 200


class MapError(Exception):
    """The model's output couldn't be turned into a usable map."""


def _text(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip()


def clean_graph(data: dict, fallback_title: str) -> dict:
    """Validates the model's graph: unique ids, parents before children, depth ≤ 4, no dangling links."""
    if not isinstance(data, dict):
        raise MapError("The AI returned an invalid map. Please try again.")
    central = _text(data.get("central"), MAX_LABEL) or _text(fallback_title, MAX_LABEL) or "Main idea"

    raw_nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    id_map: dict[str, str] = {"root": "root"}
    depth: dict[str, int] = {"root": 0}
    nodes: list[dict] = []
    seen_labels = {central.lower()}
    for item in raw_nodes:
        if not isinstance(item, dict) or len(nodes) >= MAX_NODES:
            continue
        label = _text(item.get("label"), MAX_LABEL)
        if len(label) < 2 or label.lower() in seen_labels:
            continue
        raw_id = str(item.get("id", "")).strip() or f"_auto{len(nodes)}"
        if raw_id in id_map:
            continue
        parent = id_map.get(str(item.get("parent", "root")).strip(), "root")   # unknown / later parent → root
        if depth[parent] >= MAX_DEPTH:
            parent = "root"
        new_id = f"n{len(nodes) + 1}"
        id_map[raw_id] = new_id
        depth[new_id] = depth[parent] + 1
        seen_labels.add(label.lower())
        nodes.append({
            "id": new_id,
            "label": label,
            "parent": parent,
            "relation": _text(item.get("relation"), MAX_RELATION),
            "detail": _text(item.get("detail"), MAX_DETAIL),
        })

    if len(nodes) < MIN_NODES:
        raise MapError("The AI couldn't find enough ideas for a map. Please try again.")

    tree_edges = {(n["parent"], n["id"]) for n in nodes}
    links, seen_links = [], set()
    raw_links = data.get("links") if isinstance(data.get("links"), list) else []
    for item in raw_links:
        if not isinstance(item, dict) or len(links) >= MAX_LINKS:
            continue
        a = id_map.get(str(item.get("from", "")).strip())
        b = id_map.get(str(item.get("to", "")).strip())
        if not a or not b or a == b:
            continue
        key = tuple(sorted((a, b)))
        if key in seen_links or (a, b) in tree_edges or (b, a) in tree_edges:
            continue
        seen_links.add(key)
        links.append({"from": a, "to": b, "label": _text(item.get("label"), MAX_RELATION)})

    return {"central": central, "nodes": nodes, "links": links}


def generate_graph(content: str, title: str, source_kind: str = "lesson notes", language_note: str = "") -> dict:
    prompt = f"""
    Build a concept map of the {source_kind} below for a student revising "{title}".

    - "central": the main topic in 1-4 words.
    - "nodes": 10-25 key ideas. Each has:
        "id" (short unique id like "a", "b2"), "label" (1-5 words),
        "parent" ("root" for a main branch, otherwise the id of an EARLIER node),
        "relation" (1-3 words describing how it connects to its parent, e.g. "uses", "is a type of", "produces"),
        "detail" (one short sentence explaining it).
      Use 3-6 main branches, each with 1-5 children. At most 3 levels below the root.
    - "links": up to 8 extra cross-connections between ideas on DIFFERENT branches,
      {{"from": id, "to": id, "label": "1-3 words"}}.
    - Only ideas that are actually in the material. Labels must be short — no full sentences.

    Material:
    \"\"\"{content[:MAX_SOURCE_CHARS]}\"\"\"

    Return JSON exactly like:
    {{"central": "Photosynthesis",
      "nodes": [{{"id": "a", "label": "Light reactions", "parent": "root", "relation": "stage", "detail": "Capture light energy as ATP and NADPH."}},
                {{"id": "a1", "label": "Chlorophyll", "parent": "a", "relation": "uses", "detail": "Pigment that absorbs red and blue light."}}],
      "links": [{{"from": "a1", "to": "b", "label": "powers"}}]}}
    """
    if language_note:
        prompt += f"\n    LANGUAGE of central, label, relation and detail: {language_note} Keep the JSON keys and ids in English.\n"

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You make clear, accurate concept maps for students. Respond with JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2500,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content or "")
    except json.JSONDecodeError as e:
        raise MapError("The AI returned an invalid map. Please try again.") from e
    return clean_graph(data, title)


def title_from_note(title: str) -> str:
    """'Notes on Photosynthesis' → 'Photosynthesis' (fix-up / simplified prefixes too)."""
    return re.sub(r"^(Notes on |Simplified Notes: |Fix-up Notes: )", "", title).split(" (round")[0]
