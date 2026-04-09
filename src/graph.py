import hashlib
from neo4j import GraphDatabase

KNOWN_SUPPLY_CHAINS = [
    ("Apple","TSMC","semiconductors"), ("Apple","Foxconn","assembly"),
    ("NVIDIA","TSMC","GPUs"), ("Samsung","ASML","lithography"),
    ("Toyota","Denso","auto parts"), ("Tesla","Panasonic","batteries"),
    ("Boeing","Spirit AeroSystems","fuselage"),
]
KNOWN_LOCATIONS = [
    ("TSMC","Taiwan"), ("Foxconn","China"), ("Foxconn","India"),
    ("Samsung","South Korea"), ("Toyota","Japan"),
    ("Tesla","United States"), ("Panasonic","Japan"),
]

class SupplyChainGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def run(self, query, **params):
        with self.driver.session() as s:
            return [r.data() for r in s.run(query, **params)]

    def setup_constraints(self):
        for c in [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Country) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event)   REQUIRE e.id   IS UNIQUE",
        ]:
            self.run(c)

    def ingest_article(self, article, entities):
        eid = hashlib.md5(article['url'].encode()).hexdigest()[:12]
        with self.driver.session() as s:
            s.run("MERGE (e:Event {id:$id}) SET e.title=$title, e.source=$src, "
                  "e.published_at=$pub, e.url=$url, e.disruption_signals=$sigs",
                  id=eid, title=article['title'], src=article['source'],
                  pub=article['published_at'], url=article['url'],
                  sigs=entities['disruptions'])
            for c in entities['companies'][:5]:
                s.run("MERGE (c:Company {name:$n}) WITH c MATCH (e:Event {id:$id})"
                      " MERGE (c)-[:MENTIONED_IN]->(e)", n=c, id=eid)
            for l in entities['locations'][:5]:
                s.run("MERGE (co:Country {name:$n}) WITH co MATCH (e:Event {id:$id})"
                      " MERGE (e)-[:LOCATED_IN]->(co)", n=l, id=eid)
            for c in entities['companies'][:5]:
                for l in entities['locations'][:5]:
                    s.run("MATCH (c:Company {name:$c}) MATCH (co:Country {name:$l})"
                          " MERGE (c)-[:OPERATES_IN]->(co)", c=c, l=l)

    def seed_known_data(self):
        with self.driver.session() as s:
            for buyer, supplier, product in KNOWN_SUPPLY_CHAINS:
                s.run("MERGE (b:Company {name:$b}) MERGE (s:Company {name:$s})"
                      " MERGE (s)-[:SUPPLIES_TO {product:$p}]->(b)",
                      b=buyer, s=supplier, p=product)
            for company, country in KNOWN_LOCATIONS:
                s.run("MERGE (c:Company {name:$c}) MERGE (co:Country {name:$co})"
                      " MERGE (c)-[:HEADQUARTERED_IN]->(co)", c=company, co=country)