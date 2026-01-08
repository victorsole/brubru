#!/usr/bin/env python3
"""Check requirement counts in database"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

from core.database import SessionLocal
from models.eu_law import LawRequirement, LawCluster, ClusterLaw

db = SessionLocal()

# Check total requirements
count = db.query(LawRequirement).count()
print(f'Total requirements in database: {count}')

# Check requirements with cluster_id
with_cluster = db.query(LawRequirement).filter(LawRequirement.cluster_id.isnot(None)).count()
print(f'Requirements with cluster_id: {with_cluster}')

# Show some examples
print('\nSample requirements:')
examples = db.query(LawRequirement).limit(5).all()
for req in examples:
    print(f'  ID {req.id}: law_id={req.law_id}, cluster_id={req.cluster_id}, text={req.requirement_text[:50]}...')

# Check clusters
print('\nCluster requirement counts:')
clusters = db.query(LawCluster).all()
for cluster in clusters[:10]:  # First 10 clusters
    req_count = db.query(LawRequirement).filter(LawRequirement.cluster_id == cluster.id).count()
    law_count = db.query(ClusterLaw).filter(ClusterLaw.cluster_id == cluster.id).count()
    print(f'  {cluster.name}: {law_count} laws, {req_count} requirements')

db.close()
