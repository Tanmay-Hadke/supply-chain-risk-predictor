# Supply Chain Disruption Predictor

> **Knowledge Graph + Graph RAG + LLM reasoning** to detect supply chain risks
> from live news — before they hit your factory floor.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Neo4j](https://img.shields.io/badge/Neo4j-Aura-green)
![LangChain](https://img.shields.io/badge/LangChain-0.1-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-1.33-red)

---

## What it does

Given a company name (e.g. *Apple*, *Toyota*, *Boeing*), this system:

1. **Ingests** live supply chain news via NewsAPI
2. **Extracts** entities (companies, countries, events) using spaCy NER
3. **Builds** a knowledge graph in Neo4j — nodes are entities, edges are relationships
4. **Traverses** the graph with multi-hop Cypher queries (Graph RAG)
5. **Generates** an explainable risk report using Llama 3 via Groq

The result: a traceable risk chain like  
`Apple ← TSMC (Taiwan) ← [power outage event]` → **Risk: 8/10**

---

## Why this matters

Supply chain disruptions cost **$184 billion** globally in 2023 alone.  
The signal always exists in public news 24–72 hours before impact.  
This system surfaces it automatically — for 10,000+ companies simultaneously.

Real crises this would have flagged early:
- COVID-19 semiconductor shortage (2020) — $500B+ impact
- Ever Given Suez Canal blockage (2021) — $9.6B/day
- Russia-Ukraine neon gas shortage (2022) — chip fab input crisis

---

## Tech stack

| Layer | Technology | Purpose |
|---|---|---|
| Data ingestion | NewsAPI | Live supply chain news |
| NER | spaCy `en_core_web_trf` | Extract companies, locations, events |
| Knowledge Graph | Neo4j Aura | Store entities + relationships |
| Graph RAG | Cypher queries | Multi-hop subgraph retrieval |
| LLM reasoning | Llama 3 70B via Groq | Risk synthesis + scoring |
| UI | Streamlit | Interactive dashboard |

---

## Quickstart

### 1. Clone and install
\`\`\`bash
git clone https://github.com/Tanmay-Hadke/supply-chain-risk-predictor.git
cd supply-chain-risk-predictor
pip install -r requirements.txt
python -m spacy download en_core_web_trf
\`\`\`

### 2. Set up secrets
\`\`\`bash
cp .env.example .env
# Edit .env and fill in your API keys
\`\`\`

Free accounts needed:
- [NewsAPI](https://newsapi.org/register) — news ingestion
- [Neo4j Aura](https://neo4j.com/cloud/aura-free/) — graph database
- [Groq](https://console.groq.com) — LLM inference (Llama 3, free)

### 3. Run
\`\`\`bash
streamlit run app.py
\`\`\`

Or open `notebooks/supply_chain_predictor.ipynb` in Google Colab.

---

## Project structure

\`\`\`
supply-chain-risk-predictor/
├── app.py                        # Streamlit UI
├── src/
│   ├── ingest.py                 # NewsAPI ingestion
│   ├── ner.py                    # spaCy NER pipeline
│   ├── graph.py                  # Neo4j graph operations
│   ├── retriever.py              # Graph RAG — subgraph retrieval
│   └── llm.py                    # LangChain + Groq reasoning chain
├── notebooks/
│   └── supply_chain_predictor.ipynb
├── data/
│   └── seed_supply_chains.json   # Known supplier relationships
└── requirements.txt
\`\`\`

---

## Key concepts demonstrated

- **Graph RAG** — subgraph retrieval as LLM context vs flat vector search
- **Multi-hop reasoning** — traversing Company → Supplier → Country → Event
- **Named Entity Recognition** — spaCy transformer pipeline for news NLP
- **Knowledge Graph construction** — Neo4j Cypher schema design
- **LangChain orchestration** — system/human prompt chaining with structured output

---

## Roadmap / extensions

- [ ] GDELT integration for real-time streaming (no API limit)
- [ ] Tier-2/3 supplier auto-discovery from 10-K filings
- [ ] Node embeddings for semantic graph search
- [ ] Temporal risk weighting (recent events score higher)
- [ ] Calibrated probability scores via logistic regression

---
