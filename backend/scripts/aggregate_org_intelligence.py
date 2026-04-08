"""
Aggregate Org Intelligence

Scans all user activity tables and populates/updates org_intelligence
for personalised AI chatbot context.

Usage:
    python3.12 scripts/aggregate_org_intelligence.py              # All users with activity
    python3.12 scripts/aggregate_org_intelligence.py --user EMAIL  # Single user
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

# Policy cluster keywords (simplified version of knowledge_loader clusters)
CLUSTER_KEYWORDS = {
    'energy': ['energy', 'hydrogen', 'renewable', 'solar', 'wind', 'nuclear', 'gas', 'electricity',
               'ets', 'electrification', 'battery', 'repowereu', 'red iii', 'energy efficiency'],
    'digital': ['digital', 'ai act', 'artificial intelligence', 'data', 'cybersecurity', 'gdpr',
                'dsa', 'dma', 'platform', 'chip', 'semiconductor', 'privacy', 'software'],
    'climate': ['climate', 'environment', 'emissions', 'carbon', 'biodiversity', 'circular',
                'waste', 'green deal', 'fit for 55', 'csrd', 'taxonomy', 'nature restoration',
                'cbam', 'sustainability', 'pollution', 'packaging'],
    'health': ['health', 'pharmaceutical', 'medicine', 'medical', 'ehds', 'biotech', 'clinical',
               'patient', 'hospital', 'vaccine', 'antimicrobial'],
    'finance': ['financial', 'banking', 'insurance', 'investment', 'mifid', 'psd', 'basel',
                'mica', 'crypto', 'capital market', 'solvency', 'credit'],
    'trade': ['trade', 'export', 'import', 'tariff', 'customs', 'mercosur', 'dumping',
              'intellectual property', 'wto', 'fta'],
    'agriculture': ['agriculture', 'farming', 'cap', 'fisheries', 'food', 'pesticide', 'wine',
                    'organic', 'animal welfare', 'aquaculture'],
    'transport': ['transport', 'mobility', 'railway', 'aviation', 'maritime', 'logistics',
                  'automotive', 'road', 'shipping', 'euro 7'],
    'defence': ['defence', 'defense', 'military', 'security', 'nato', 'space', 'satellite'],
    'social': ['employment', 'labour', 'education', 'equality', 'disability', 'housing',
               'poverty', 'migration', 'consumer', 'minimum wage', 'platform workers'],
    'research': ['research', 'innovation', 'horizon', 'erc', 'university', 'science', 'r&d'],
}

# Commissioner/MEP/committee patterns for key_contacts extraction
CONTACT_PATTERNS = [
    r'(?:commissioner|comisario|commissaire)\s+(\w+(?:\s+\w+)?)',
    r'(?:rapporteur|ponente)\s+(\w+(?:\s+\w+)?)',
    r'(?:mep|eurodiputado|eurodeputee)\s+(\w+(?:\s+\w+)?)',
    r'(?:committee|comite|comision)\s+(ITRE|ENVI|ECON|IMCO|TRAN|AGRI|PECH|LIBE|JURI|EMPL|INTA|AFCO|BUDG|CONT|DEVE|DROI|FEMM|CULT|REGI|SEDE|AFET)',
]


def classify_text(text: str) -> list:
    """Classify text into policy clusters by keyword matching."""
    text_lower = text.lower()
    scores = {}
    for cluster, keywords in CLUSTER_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[cluster] = score
    return sorted(scores, key=scores.get, reverse=True)[:5]


def extract_contacts(text: str) -> list:
    """Extract mentioned contacts (Commissioners, MEPs, committees) from text."""
    contacts = set()
    for pattern in CONTACT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            contacts.add(match.group(1).strip())
    return list(contacts)[:10]


def extract_topics(texts: list) -> dict:
    """Extract top topics from a list of query texts."""
    word_counter = Counter()
    # Common EU topic phrases to look for
    topic_phrases = [
        'ai act', 'artificial intelligence', 'gdpr', 'data protection', 'digital services act',
        'digital markets act', 'cbam', 'carbon border', 'ets', 'emissions trading',
        'green deal', 'fit for 55', 'csrd', 'taxonomy', 'nature restoration',
        'pharmaceutical', 'medical devices', 'ehds', 'health data',
        'mifid', 'banking union', 'psd3', 'mica', 'crypto',
        'cap', 'common agricultural', 'fisheries', 'food safety',
        'transport', 'aviation', 'maritime', 'rail',
        'defence', 'safe', 'rearm', 'csdp',
        'minimum wage', 'platform workers', 'disability',
        'horizon europe', 'erc', 'innovation',
        'trade', 'mercosur', 'customs',
        'energy', 'hydrogen', 'renewable', 'nuclear', 'electrification',
    ]

    for text in texts:
        text_lower = text.lower()
        for phrase in topic_phrases:
            if phrase in text_lower:
                word_counter[phrase] += 1

    return dict(word_counter.most_common(10))


def aggregate_user(cur, user_id: str, email: str):
    """Aggregate all activity for a single user."""

    # 1. Chat queries
    cur.execute("""
        SELECT cm.content, cm.created_at
        FROM chat_messages cm
        JOIN chats c ON cm.chat_id = c.id
        WHERE c.user_id = %s AND cm.role = 'user'
        ORDER BY cm.created_at DESC
    """, (user_id,))
    queries = cur.fetchall()
    query_texts = [q[0] for q in queries]
    query_count = len(queries)
    last_query_at = queries[0][1] if queries else None

    # 2. Tracked legislative files
    cur.execute("""
        SELECT lc.title
        FROM user_carriage_tracks uct
        JOIN legislative_carriages lc ON uct.carriage_id = lc.id
        WHERE uct.user_id = %s
    """, (user_id,))
    tracked_files = list(set(r[0] for r in cur.fetchall() if r[0]))[:15]

    # 3. Amendments
    cur.execute("""
        SELECT DISTINCT document_filename, procedure_reference
        FROM amendments
        WHERE user_id = %s
    """, (user_id,))
    amendment_rows = cur.fetchall()
    amended_files = list(set(r[0] or r[1] or '' for r in amendment_rows if r[0] or r[1]))[:10]
    amendment_count = len(amendment_rows)

    # 4. Generated documents
    cur.execute("""
        SELECT title, document_type
        FROM user_documents
        WHERE user_id = %s AND document_type != 'uploaded'
    """, (user_id,))
    doc_rows = cur.fetchall()
    generated_docs = list(set(r[0] for r in doc_rows if r[0]))[:10]
    document_count = len(doc_rows)

    # 5. Compliance analyses
    cur.execute("""
        SELECT COUNT(*) FROM compliance_analyses WHERE user_id = %s
    """, (user_id,))
    compliance_count = cur.fetchone()[0]

    # 6. User profile data
    cur.execute("""
        SELECT organization, country, policy_interests FROM users WHERE id = %s
    """, (user_id,))
    user_row = cur.fetchone()
    sector = user_row[0] if user_row else None
    country = user_row[1] if user_row else None
    profile_interests = user_row[2] if user_row else None

    # 7. Tender profile (if exists)
    cur.execute("""
        SELECT sectors_description, company_name FROM tender_profiles WHERE user_id = %s
    """, (user_id,))
    tender_row = cur.fetchone()
    if tender_row:
        if tender_row[0] and not sector:
            sector = tender_row[0][:200]
        elif tender_row[1] and not sector:
            sector = tender_row[1][:200]

    # Derive policy areas from all activity
    all_text = ' '.join(query_texts[:50])  # Last 50 queries
    all_text += ' '.join(tracked_files)
    all_text += ' '.join(amended_files)
    if profile_interests:
        if isinstance(profile_interests, list):
            all_text += ' '.join(profile_interests)
        elif isinstance(profile_interests, str):
            all_text += ' ' + profile_interests

    policy_areas = classify_text(all_text)

    # Extract contacts from queries
    contacts = extract_contacts(' '.join(query_texts[:30]))

    # Extract top topics
    top_topics = extract_topics(query_texts[:100])

    # Upsert
    cur.execute("""
        INSERT INTO org_intelligence
        (user_id, policy_areas, tracked_files, amended_files, generated_docs,
         key_contacts, sector, country, query_count, amendment_count,
         document_count, compliance_count, top_topics, last_query_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            policy_areas = EXCLUDED.policy_areas,
            tracked_files = EXCLUDED.tracked_files,
            amended_files = EXCLUDED.amended_files,
            generated_docs = EXCLUDED.generated_docs,
            key_contacts = EXCLUDED.key_contacts,
            sector = EXCLUDED.sector,
            country = EXCLUDED.country,
            query_count = EXCLUDED.query_count,
            amendment_count = EXCLUDED.amendment_count,
            document_count = EXCLUDED.document_count,
            compliance_count = EXCLUDED.compliance_count,
            top_topics = EXCLUDED.top_topics,
            last_query_at = EXCLUDED.last_query_at,
            updated_at = NOW()
    """, (
        user_id, policy_areas, tracked_files, amended_files, generated_docs,
        contacts, sector, country, query_count, amendment_count,
        document_count, compliance_count, json.dumps(top_topics), last_query_at,
    ))

    return {
        'email': email,
        'policy_areas': policy_areas,
        'query_count': query_count,
        'tracked': len(tracked_files),
        'amendments': amendment_count,
        'docs': document_count,
        'topics': len(top_topics),
    }


def main():
    parser = argparse.ArgumentParser(description='Aggregate org intelligence for all users')
    parser.add_argument('--user', type=str, help='Single user email to aggregate')
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()

    if args.user:
        cur.execute("SELECT id::text, email FROM users WHERE email = %s", (args.user,))
        users = cur.fetchall()
    else:
        # All users with at least 1 chat query
        cur.execute("""
            SELECT DISTINCT u.id::text, u.email
            FROM users u
            JOIN chats c ON c.user_id = u.id
            JOIN chat_messages cm ON cm.chat_id = c.id
            WHERE cm.role = 'user'
        """)
        users = cur.fetchall()

    print(f'[START] Aggregating org intelligence for {len(users)} users')

    for user_id, email in users:
        try:
            result = aggregate_user(cur, user_id, email)
            areas = ', '.join(result['policy_areas'][:3]) if result['policy_areas'] else 'none'
            print(f'  [OK] {email}: {result["query_count"]} queries, areas={areas}, '
                  f'{result["tracked"]} tracked, {result["amendments"]} amendments')
        except Exception as e:
            print(f'  [WARN] {email}: {e}')
            conn.rollback()
            continue

    conn.commit()

    # Summary
    cur.execute("SELECT COUNT(*) FROM org_intelligence")
    total = cur.fetchone()[0]
    print(f'\n[OK] {total} user profiles in org_intelligence')

    conn.close()


if __name__ == '__main__':
    main()
