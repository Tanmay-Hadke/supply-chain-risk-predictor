def get_subgraph(graph, company):
    rows = graph.run("""
        MATCH (t:Company {name:$name})
        OPTIONAL MATCH (s:Company)-[:SUPPLIES_TO]->(t)
        OPTIONAL MATCH (s)-[:HEADQUARTERED_IN|OPERATES_IN]->(co:Country)
        OPTIONAL MATCH (e:Event)-[:LOCATED_IN]->(co)
        RETURN t.name AS company,
               collect(DISTINCT s.name)    AS suppliers,
               collect(DISTINCT co.name)   AS countries,
               collect(DISTINCT e.title)[..5]  AS events,
               collect(DISTINCT e.disruption_signals)[..5] AS signals
    """, name=company)
    return rows[0] if rows else None

def get_risk_paths(graph, company):
    return graph.run("""
        MATCH (c:Company {name:$name})
            <-[:SUPPLIES_TO]-(s:Company)
            -[:HEADQUARTERED_IN|OPERATES_IN]->(co:Country)
            <-[:LOCATED_IN]-(e:Event)
        WHERE size(e.disruption_signals) > 0
        RETURN s.name AS supplier, co.name AS country,
               e.title AS event_title, e.disruption_signals AS signals
        LIMIT 10
    """, name=company)

def subgraph_to_text(sg):
    if not sg:
        return "No graph data found."
    lines = [f"COMPANY: {sg['company']}"]
    if sg['suppliers']:
        lines.append(f"SUPPLIERS: {', '.join(sg['suppliers'])}")
    if sg['countries']:
        lines.append(f"COUNTRIES: {', '.join(sg['countries'])}")
    if sg['events']:
        lines.append("RECENT EVENTS:")
        for e in sg['events']:
            if e: lines.append(f"  - {e}")
    flat = [s for sig in sg['signals'] for s in (sig if isinstance(sig,list) else [sig]) if s]
    if flat:
        lines.append(f"RISK SIGNALS: {', '.join(set(flat))}")
    return "\n".join(lines)