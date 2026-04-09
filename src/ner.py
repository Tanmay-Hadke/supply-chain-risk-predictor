import spacy
from spacy.matcher import PhraseMatcher

DISRUPTION_KEYWORDS = [
    "shutdown", "closure", "shortage", "delay", "disruption",
    "blockage", "congestion", "flood", "earthquake", "strike",
    "sanctions", "tariff", "export ban", "factory fire",
    "power outage", "chip shortage", "port closed",
]

_nlp, _matcher = None, None

def _load():
    global _nlp, _matcher
    if _nlp is None:
        _nlp = spacy.load("en_core_web_trf")
        _matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
        patterns = [_nlp.make_doc(kw) for kw in DISRUPTION_KEYWORDS]
        _matcher.add("DISRUPTION", patterns)
    return _nlp, _matcher

def extract_entities(text):
    nlp, matcher = _load()
    doc = nlp(text[:1000])
    entities = {"companies": [], "locations": [], "disruptions": []}
    for ent in doc.ents:
        if ent.label_ == "ORG":
            entities["companies"].append(ent.text.strip())
        elif ent.label_ in ("GPE", "LOC"):
            entities["locations"].append(ent.text.strip())
    matches = matcher(doc)
    for _, start, end in matches:
        entities["disruptions"].append(doc[start:end].text.lower())
    for k in entities:
        entities[k] = list(set(entities[k]))
    return entities