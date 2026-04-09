import re
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

SYSTEM_PROMPT = """You are a supply chain risk analyst.
Given a knowledge graph context with a company's suppliers, their countries,
and recent disruption events, produce:
1. Overall risk score (1-10)
2. Top 3 specific risks with evidence from the context
3. Most critical supplier → country → event chain
4. 3 actionable mitigation recommendations
Be specific. Only use facts present in the context."""

def get_llm(api_key):
    return ChatGroq(groq_api_key=api_key,
                    model_name="llama3-70b-8192", temperature=0.1)

def assess_risk(llm, company, context, paths):
    path_text = ""
    if paths:
        path_text = "\nRISK PATHS:\n" + "\n".join(
            f"  {company} ← {p['supplier']} (in {p['country']}) ← [{p['event_title'][:60]}] signals:{p['signals']}"
            for p in paths[:5]
        )
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Analyse {company}.\n\nCONTEXT:\n{context}{path_text}")
    ])
    return response.content

def extract_score(text):
    for pat in [r'[Rr]isk [Ss]core[:\s]+(\d+(?:\.\d+)?)/10',
                r'[Oo]verall.*?(\d+(?:\.\d+)?)/10',
                r'\*\*(\d+(?:\.\d+)?)/10\*\*']:
        m = re.search(pat, text)
        if m: return float(m.group(1))
    return None