import streamlit as st
import os
import re
import hashlib
from collections import Counter

from newsapi import NewsApiClient
from neo4j import GraphDatabase
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
import spacy
from spacy.matcher import PhraseMatcher

# ── Secrets ───────────────────────────────────────────────────────────────────
NEWS_API_KEY   = os.environ.get("NEWS_API_KEY", "")
NEO4J_URI      = os.environ.get("NEO4J_URI", "")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
NEO4J_USER     = "eb10e102"

# ── Neo4j ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_query(query, params=None):
    with get_driver().session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]

# ── spaCy ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def load_nlp():
    nlp = spacy.load("en_core_web_trf")
    DISRUPTION_KEYWORDS = [
        "shutdown", "closure", "shortage", "delay", "disruption",
        "blockage", "congestion", "flood", "earthquake", "strike",
        "sanctions", "tariff", "export ban", "factory fire",
        "power outage", "chip shortage", "port closed"
    ]
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(kw) for kw in DISRUPTION_KEYWORDS]
    matcher.add("DISRUPTION", patterns)
    return nlp, matcher

# ── NER ───────────────────────────────────────────────────────────────────────
def extract_entities(text):
    nlp, matcher = load_nlp()
    doc = nlp(text[:1000])
    entities = {"companies": [], "locations": [], "events": [], "disruptions": []}
    for ent in doc.ents:
        if ent.label_ == "ORG":
            entities["companies"].append(ent.text.strip())
        elif ent.label_ in ("GPE", "LOC"):
            entities["locations"].append(ent.text.strip())
        elif ent.label_ == "EVENT":
            entities["events"].append(ent.text.strip())
    matches = matcher(doc)
    for _, start, end in matches:
        entities["disruptions"].append(doc[start:end].text.lower())
    for key in entities:
        entities[key] = list(set(entities[key]))
    return entities

# ── News ingestion ────────────────────────────────────────────────────────────
def fetch_and_ingest_news():
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    queries = [
        "supply chain disruption", "semiconductor shortage",
        "port congestion delay", "factory shutdown flood earthquake",
    ]
    all_articles = []
    for q in queries:
        try:
            resp = newsapi.get_everything(q=q, language="en",
                                          sort_by="relevancy", page_size=15)
            all_articles.extend(resp.get("articles", []))
        except Exception:
            pass

    seen, unique = set(), []
    for a in all_articles:
        if a.get("title") and a["title"] not in seen:
            seen.add(a["title"])
            content = a.get("content") or a.get("description") or ""
            unique.append({
                "title": a["title"],
                "text":  a["title"] + ". " + content,
                "source": a.get("source", {}).get("name", "Unknown"),
                "published_at": a.get("publishedAt", ""),
                "url": a.get("url", ""),
            })

    # Ingest into Neo4j
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Country) REQUIRE l.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event)   REQUIRE e.id   IS UNIQUE",
    ]
    for c in constraints:
        run_query(c)

    for article in unique:
        entities = extract_entities(article["text"])
        event_id = hashlib.md5(article["url"].encode()).hexdigest()[:12]
        with get_driver().session() as session:
            session.run("""
                MERGE (e:Event {id: $event_id})
                SET e.title=$title, e.source=$source,
                    e.published_at=$published_at, e.url=$url,
                    e.disruption_signals=$disrupts
            """, event_id=event_id, title=article["title"],
                 source=article["source"], published_at=article["published_at"],
                 url=article["url"], disrupts=entities["disruptions"])
            for company in entities["companies"][:5]:
                session.run("""
                    MERGE (c:Company {name:$name})
                    WITH c MATCH (e:Event {id:$eid})
                    MERGE (c)-[:MENTIONED_IN]->(e)
                """, name=company, eid=event_id)
            for loc in entities["locations"][:5]:
                session.run("""
                    MERGE (co:Country {name:$name})
                    WITH co MATCH (e:Event {id:$eid})
                    MERGE (e)-[:LOCATED_IN]->(co)
                """, name=loc, eid=event_id)
            for company in entities["companies"][:5]:
                for loc in entities["locations"][:5]:
                    session.run("""
                        MATCH (c:Company {name:$company})
                        MATCH (co:Country {name:$loc})
                        MERGE (c)-[:OPERATES_IN]->(co)
                    """, company=company, loc=loc)

    # Seed known supply chains
    known_chains = [
        ("Apple","TSMC","semiconductors"), ("Apple","Foxconn","assembly"),
        ("NVIDIA","TSMC","GPUs"), ("Samsung","ASML","lithography"),
        ("Toyota","Denso","auto parts"), ("Tesla","Panasonic","batteries"),
        ("Boeing","Spirit AeroSystems","fuselage"),
    ]
    known_locs = [
        ("TSMC","Taiwan"), ("Foxconn","China"), ("Foxconn","India"),
        ("Samsung","South Korea"), ("Toyota","Japan"),
        ("Tesla","United States"), ("Panasonic","Japan"),
    ]
    with get_driver().session() as session:
        for buyer, supplier, product in known_chains:
            session.run("""
                MERGE (b:Company {name:$buyer})
                MERGE (s:Company {name:$supplier})
                MERGE (s)-[:SUPPLIES_TO {product:$product}]->(b)
            """, buyer=buyer, supplier=supplier, product=product)
        for company, country in known_locs:
            session.run("""
                MERGE (c:Company {name:$company})
                MERGE (co:Country {name:$country})
                MERGE (c)-[:HEADQUARTERED_IN]->(co)
            """, company=company, country=country)

    return len(unique)

# ── Graph queries ─────────────────────────────────────────────────────────────
def get_company_subgraph(company_name, depth=2):
    """
    Retrieve a subgraph around a company:
    - Its direct suppliers
    - Countries those suppliers operate in
    - Recent disruption events in those countries
    - Risk signals attached to events
    """
    result = run_query("""
        MATCH (target:Company {name: $name})

        OPTIONAL MATCH (supplier:Company)-[:SUPPLIES_TO]->(target)
        OPTIONAL MATCH (supplier)-[:HEADQUARTERED_IN|OPERATES_IN]->(country:Country)
        OPTIONAL MATCH (event:Event)-[:LOCATED_IN]->(country)

        RETURN
            target.name                          AS company,
            collect(DISTINCT supplier.name)      AS suppliers,
            collect(DISTINCT country.name)       AS countries,
            collect(DISTINCT event.title)[..5]   AS recent_events,
            collect(DISTINCT event.disruption_signals)[..5] AS risk_signals
    """, params={'name': company_name})

    return result[0] if result else None

def subgraph_to_context(subgraph):
    if not subgraph:
        return "No graph data found for this company."
    lines = [f"COMPANY: {subgraph['company']}"]
    if subgraph["suppliers"]:
        lines.append(f"KNOWN SUPPLIERS: {', '.join(subgraph['suppliers'])}")
    if subgraph["countries"]:
        lines.append(f"SUPPLIER COUNTRIES: {', '.join(subgraph['countries'])}")
    if subgraph["recent_events"]:
        lines.append("RECENT NEWS EVENTS:")
        for evt in subgraph["recent_events"][:5]:
            if evt:
                lines.append(f"  - {evt}")
    flat_signals = []
    for sig in subgraph.get("risk_signals", []):
        if isinstance(sig, list):
            flat_signals.extend(sig)
        elif sig:
            flat_signals.append(sig)
    if flat_signals:
        lines.append(f"DETECTED RISK SIGNALS: {', '.join(set(flat_signals))}")
    return "\n".join(lines)

def find_risk_paths(company_name):
    """
    Multi-hop: Company → Supplier → Country → Event
    Returns all risk paths as readable strings.
    """
    paths = run_query("""
        MATCH path = (c:Company {name: $name})
            <-[:SUPPLIES_TO]-(supplier:Company)
            -[:HEADQUARTERED_IN|OPERATES_IN]->(country:Country)
            <-[:LOCATED_IN]-(event:Event)
        WHERE size(event.disruption_signals) > 0
        RETURN 
            supplier.name       AS supplier,
            country.name        AS country,
            event.title         AS event_title,
            event.disruption_signals AS signals
        LIMIT 10
    """, params={'name': company_name})
    
    return paths

# ── LLM ───────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_llm():
    return ChatGroq(groq_api_key=GROQ_API_KEY,
                    model_name="llama-3.1-8b-instant", temperature=0.1)

SYSTEM_PROMPT = """You are a supply chain risk analyst.
Given a knowledge graph context about a company, its suppliers, their countries,
and recent news events with risk signals, you must:
1. Give an overall risk score (1-10)
2. List the top 3 specific risks with evidence
3. Identify the most critical supplier → country → event chain
4. Give 3 actionable mitigation recommendations
Be specific. Reference actual names from the context. Do not hallucinate."""

def assess_supply_chain_risk(company_name):
    subgraph   = get_company_subgraph(company_name)
    context    = subgraph_to_context(subgraph)
    risk_paths = find_risk_paths(company_name)
    path_text  = ""
    if risk_paths:
        path_text = "\nRISK CHAIN PATHS:\n"
        for p in risk_paths[:5]:
            path_text += (f"  {company_name} ← {p['supplier']} "
                          f"(in {p['country']}) ← "
                          f"[{p['event_title'][:60]}] "
                          f"signals: {p['signals']}\n")
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Analyse risk for {company_name}.\n\n"
                              f"CONTEXT:\n{context}{path_text}")
    ]
    return get_llm().invoke(messages).content

def extract_risk_score(text):
    for pattern in [
        r'[Oo]verall [Rr]isk [Ss]core[:\s]+(\d+(?:\.\d+)?)',
        r'[Rr]isk [Ss]core[:\s]+(\d+(?:\.\d+)?)/10',
        r'\*\*(\d+(?:\.\d+)?)/10\*\*',
        r'Score:\s*(\d+(?:\.\d+)?)',
    ]:
        m = re.search(pattern, text)
        if m:
            return float(m.group(1))
    return None

# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Supply Chain Risk Predictor", layout="wide")
st.title("Supply Chain Disruption Predictor")
st.caption("Knowledge Graph + Graph RAG + Llama 3")

with st.sidebar:
    st.subheader("Data pipeline")
    if st.button("Fetch & ingest news", use_container_width=True):
        with st.spinner("Fetching news and building graph..."):
            n = fetch_and_ingest_news()
        st.success(f"Ingested {n} articles into Neo4j")

    st.divider()
    st.subheader("Analyse a company")
    company = st.text_input("Company name", placeholder="e.g. Apple, Toyota")
    for preset in ["Apple", "Toyota", "NVIDIA", "Boeing", "Tesla"]:
        if st.button(preset, use_container_width=True):
            company = preset
            st.session_state["company"] = preset
    run_btn = st.button("Run risk assessment", type="primary",
                         use_container_width=True)

company = st.session_state.get("company", company)

if run_btn and company:
    col1, col2 = st.columns(2)
    with col1:
        with st.spinner("Querying knowledge graph..."):
            subgraph = get_company_subgraph(company)
            context  = subgraph_to_context(subgraph)
        st.subheader("Graph context")
        st.code(context, language="text")
        paths = find_risk_paths(company)
        if paths:
            st.subheader("Multi-hop risk paths")
            for p in paths[:5]:
                st.markdown(f"**{company}** ← **{p['supplier']}**"
                            f" (in {p['country']}) ← _{p['event_title'][:70]}_")
    with col2:
        with st.spinner("LLM generating risk report..."):
            report = assess_supply_chain_risk(company)
            score  = extract_risk_score(report)
        if score is not None:
            color = "red" if score >= 7 else "orange" if score >= 4 else "green"
            st.metric("Risk score", f"{score:.1f} / 10",
                      delta="High" if score >= 7 else
                            "Medium" if score >= 4 else "Low")
        st.subheader("Full risk assessment")
        st.markdown(report)
elif not company:
    st.info("Run 'Fetch & ingest news' first, then enter a company name in the sidebar.")