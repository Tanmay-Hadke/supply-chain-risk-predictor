from newsapi import NewsApiClient
from datetime import datetime, timedelta

QUERIES = [
    "supply chain disruption", "semiconductor shortage",
    "port congestion delay", "factory shutdown flood earthquake",
]

def fetch_articles(api_key, days_back=7):
    client = NewsApiClient(api_key=api_key)
    from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    articles = []
    for q in QUERIES:
        try:
            resp = client.get_everything(q=q, from_param=from_date,
                                         language='en', sort_by='relevancy',
                                         page_size=15)
            articles.extend(resp.get('articles', []))
        except Exception as e:
            print(f"Warning: query '{q}' failed — {e}")
    seen, unique = set(), []
    for a in articles:
        if a.get('title') and a['title'] not in seen:
            seen.add(a['title'])
            content = a.get('content') or a.get('description') or ''
            unique.append({
                'title': a['title'],
                'text':  a['title'] + '. ' + content,
                'source': a.get('source', {}).get('name', 'Unknown'),
                'published_at': a.get('publishedAt', ''),
                'url': a.get('url', ''),
            })
    return unique