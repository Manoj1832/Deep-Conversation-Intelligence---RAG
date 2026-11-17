# HerAI — Production Incident & Rollback Guide

**Version**: 1.0.0  
**Purpose**: Deterministic reversion procedures for frontend releases, backend microservices, database schemas, and vector index anomalies.

---

## 1. Incident Severity & Rollback Triggers

Initiate immediate rollback under any of the following critical conditions:
1. **Security Vulnerability / Token Exposure**: Any incident exposing raw API keys or cross-tenant memory retrieval.
2. **Crash-Loop / HTTP 5xx Elevation**: Backend 5xx error rate exceeds 2% over a 5-minute window.
3. **SSE Streaming Failure**: Real-time chat streaming breaks globally across client sessions.
4. **Data Corruption**: Schema mismatch or database write failure preventing memory state updates.

---

## 2. Frontend Rollback Procedures (Vercel & Docker)

### 2.1 Vercel Instant Rollback (Recommended)
Vercel keeps immutable build snapshots of every production deployment.
1. Navigate to the **Vercel Project Dashboard** -> **Deployments**.
2. Locate the previous healthy deployment (e.g., `Deploy #41 - Passed`).
3. Click the three dots `...` and select **Promote to Production** (or click **Instant Rollback**).
4. *Via CLI*:
   ```bash
   vercel rollback <deployment-url-or-id>
   ```
5. Production traffic redirects to the healthy snapshot within < 5 seconds.

### 2.2 Containerized Next.js Rollback (Cloud Run / Docker)
If running standalone Next.js container:
```bash
# Roll back Cloud Run traffic to the previous healthy revision
gcloud run services update-traffic herai-frontend \
  --to-revisions=herai-frontend-v1-0-prev=100 \
  --region=us-central1
```

---

## 3. Backend Rollback Procedures (FastAPI / Cloud Run)

### 3.1 Cloud Run Zero-Downtime Traffic Rollback
Cloud Run maintains all previous immutable revisions:
1. List available revisions:
   ```bash
   gcloud run revisions list --service=herai-backend --region=us-central1
   ```
2. Instantly route 100% of incoming requests back to the previous stable revision:
   ```bash
   gcloud run services update-traffic herai-backend \
     --to-revisions=herai-backend-00012-abc=100 \
     --region=us-central1
   ```
3. Verification:
   ```bash
   curl -f -s https://<backend-url>/api/v1/health | jq .version
   ```

### 3.2 Docker Compose Standalone Rollback
```bash
cd /home/manoj/Documents/HerAI
# Pull or checkout previous stable commit
git checkout tags/v1.0.0-stable
docker compose down
docker compose up -d --build backend
```

---

## 4. Database Rollback Procedures (Supabase PostgreSQL)

> [!CAUTION]
> Never execute destructive database rollbacks without validating backup integrity. Supabase is the single source of truth for all relationship memories.

### 4.1 Schema Rollback via Supabase CLI
If a newly pushed migration introduces errors:
1. Review the failing migration in `supabase/migrations/`.
2. Generate an inverse migration script that restores previous table schemas or constraints.
3. Apply the fix:
   ```bash
   supabase db push
   ```

### 4.2 Point-In-Time Recovery (PITR)
For disastrous data corruption:
1. Open **Supabase Dashboard** -> **Database** -> **Backups**.
2. Select **Point in Time Recovery (PITR)**.
3. Choose a restoration timestamp preceding the incident by 5 minutes.
4. Execute restoration to a staging instance, verify data fidelity, and switch production connection strings.

---

## 5. Vector Index Disaster Recovery & Full Rebuild (Qdrant)

Because Qdrant is treated as a **rebuildable vector index**, vector corruption can be completely healed from Supabase PostgreSQL without data loss.

### 5.1 Rebuilding the Vector Collection from Scratch
If Qdrant collection `herai_memories` experiences index divergence or corruption:
```bash
cd /home/manoj/Documents/HerAI
source backend/.venv/bin/activate

# Execute deterministic collection rebuild script
python -c "
from backend.app.memory_engine.memory_indexer import MemoryIndexer
indexer = MemoryIndexer()
print('Clearing corrupted collection...')
indexer.recreate_collection()
print('Rebuilding vectors from approved relationship memories...')
count = indexer.reindex_all_memories()
print(f'Successfully restored {count} memories to Qdrant Cloud.')
"
```

---

## 6. Recovery Objectives (RTO / RPO)

| Subsystem | Metric | Target | Disaster Recovery Mechanism |
| :--- | :--- | :--- | :--- |
| **Frontend** | RTO (Recovery Time) | < 30 seconds | Vercel Instant Rollback / CDN edge switch |
| **Backend API** | RTO (Recovery Time) | < 60 seconds | Cloud Run revision traffic split |
| **Database** | RPO (Data Loss Window) | < 5 minutes | Supabase Write-Ahead Log (WAL) PITR |
| **Vector Store** | RTO (Full Rebuild) | < 5 minutes | Deterministic reindex from Supabase |
