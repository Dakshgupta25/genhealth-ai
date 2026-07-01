# GenHealth AI — Complete Production Build Prompts
## (Send Part by Part to Antigravity / Claude)

---
> **HOW TO USE:**
> 1. Send **PART 1** first → sets up project structure + backend
> 2. Send **PART 2** → OCR, NLP, ML/DL pipelines
> 3. Send **PART 3** → Frontend (based on your existing index.html prototype)
> 4. Send **PART 4** → Family linking system + Doctor Portal
> 5. Send **PART 5** → GitHub setup, deployment config, final integration
>
> Always attach your `index.html` when sending Part 3.

---

# ═══════════════════════════════════════════════
# PART 1 — PROJECT ARCHITECTURE + BACKEND SETUP
# ═══════════════════════════════════════════════

```
You are building the complete backend for **GenHealth AI** — a generational health intelligence platform. This is Part 1 of a 5-part build. Set up the full project structure and backend API.

---

## PROJECT STRUCTURE TO CREATE

```
genhealth-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Settings, env vars
│   │   ├── database.py                # SQLAlchemy + MongoDB setup
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── family.py
│   │   │   ├── health_record.py
│   │   │   ├── prescription.py
│   │   │   ├── risk_prediction.py
│   │   │   └── doctor.py
│   │   │
│   │   ├── schemas/                   # Pydantic schemas
│   │   │   ├── user.py
│   │   │   ├── family.py
│   │   │   ├── health_record.py
│   │   │   ├── prescription.py
│   │   │   └── risk.py
│   │   │
│   │   ├── routers/                   # API route handlers
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── family.py
│   │   │   ├── records.py
│   │   │   ├── upload.py
│   │   │   ├── insights.py
│   │   │   ├── risk.py
│   │   │   ├── recommendations.py
│   │   │   ├── doctor.py
│   │   │   └── invite.py
│   │   │
│   │   ├── services/                  # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── family_service.py
│   │   │   ├── record_service.py
│   │   │   ├── insight_service.py
│   │   │   └── notification_service.py
│   │   │
│   │   └── middleware/
│   │       ├── auth_middleware.py
│   │       └── rate_limiter.py
│   │
│   ├── ml/                            # ML/DL modules (see Part 2)
│   │   ├── ocr/
│   │   ├── nlp/
│   │   ├── risk_models/
│   │   └── generational/
│   │
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── frontend/
│   ├── index.html                     # (existing prototype, enhanced in Part 3)
│   ├── assets/
│   │   ├── css/
│   │   ├── js/
│   │   │   ├── api.js                 # API client layer
│   │   │   ├── auth.js
│   │   │   ├── upload.js
│   │   │   ├── family.js
│   │   │   ├── risk.js
│   │   │   └── charts.js
│   │   └── images/
│   └── pages/
│       ├── login.html
│       ├── signup.html
│       ├── onboarding.html
│       └── doctor.html
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── README.md
├── .gitignore
└── docker-compose.yml
```

---

## BACKEND TECH STACK

- **Framework:** FastAPI (Python 3.11+)
- **Primary DB:** PostgreSQL (structured records, users, relations)
- **Secondary DB:** MongoDB (unstructured OCR output, raw extracted data)
- **Cache:** Redis (session tokens, invite codes, rate limiting)
- **File Storage:** AWS S3 (or local MinIO for dev) for prescription images/PDFs
- **Auth:** JWT (access + refresh tokens), bcrypt password hashing
- **Email:** SendGrid (for invite emails, OTP)
- **Task Queue:** Celery + Redis (async OCR/ML processing)
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic

---

## DATABASE SCHEMA

### PostgreSQL Tables

**users**
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(255) NOT NULL,
  date_of_birth DATE,
  gender VARCHAR(10),
  blood_group VARCHAR(5),
  phone VARCHAR(20),
  profile_image_url TEXT,
  role VARCHAR(20) DEFAULT 'patient',  -- patient | doctor | admin
  is_verified BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

**family_members**
```sql
CREATE TABLE family_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  related_user_id UUID REFERENCES users(id),  -- NULL if not on platform
  name VARCHAR(255) NOT NULL,
  relationship VARCHAR(50) NOT NULL,  -- father|mother|sibling|child|grandparent|spouse|other
  gender VARCHAR(10),
  date_of_birth DATE,
  is_deceased BOOLEAN DEFAULT FALSE,
  invite_status VARCHAR(20) DEFAULT 'pending',  -- pending|accepted|declined|not_invited
  invite_token VARCHAR(255),
  invite_sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**health_records**
```sql
CREATE TABLE health_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
  family_member_id UUID REFERENCES family_members(id),
  record_type VARCHAR(50) NOT NULL,  -- prescription|lab_report|diagnosis|imaging
  source_file_url TEXT,
  source_file_type VARCHAR(10),
  extraction_status VARCHAR(20) DEFAULT 'pending',  -- pending|processing|done|failed
  confidence_score FLOAT,
  raw_ocr_text TEXT,
  structured_data JSONB,
  is_verified_by_user BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  record_date DATE
);
```

**extracted_entities**
```sql
CREATE TABLE extracted_entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id UUID REFERENCES health_records(id) ON DELETE CASCADE,
  entity_type VARCHAR(50),  -- disease|medicine|dosage|doctor|hospital|date|test_result
  entity_value TEXT NOT NULL,
  confidence FLOAT,
  icd10_code VARCHAR(20),  -- for diseases
  atc_code VARCHAR(20),    -- for medicines (ATC classification)
  start_index INT,
  end_index INT,
  user_corrected BOOLEAN DEFAULT FALSE,
  corrected_value TEXT
);
```

**risk_predictions**
```sql
CREATE TABLE risk_predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  disease_name VARCHAR(255) NOT NULL,
  icd10_code VARCHAR(20),
  probability FLOAT NOT NULL,
  risk_level VARCHAR(20) NOT NULL,  -- low|moderate|high
  contributing_factors JSONB,  -- [{factor, weight, source}]
  model_version VARCHAR(20),
  generated_at TIMESTAMP DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE
);
```

**family_invites**
```sql
CREATE TABLE family_invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inviter_id UUID REFERENCES users(id),
  invitee_email VARCHAR(255),
  invitee_phone VARCHAR(20),
  family_member_id UUID REFERENCES family_members(id),
  token VARCHAR(255) UNIQUE NOT NULL,
  relationship VARCHAR(50),
  status VARCHAR(20) DEFAULT 'pending',  -- pending|accepted|declined|expired
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**doctor_access**
```sql
CREATE TABLE doctor_access (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID REFERENCES users(id),
  doctor_id UUID REFERENCES users(id),
  access_level VARCHAR(20) DEFAULT 'read',
  granted_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE,
  consent_text TEXT,
  revoked_at TIMESTAMP
);
```

---

## API ENDPOINTS TO BUILD

### Auth Routes (`/api/v1/auth/`)
```
POST   /signup              → Register user
POST   /login               → Login, return JWT tokens
POST   /refresh             → Refresh access token
POST   /logout              → Invalidate tokens
POST   /verify-email        → Verify email via OTP
POST   /forgot-password     → Send reset link
POST   /reset-password      → Reset with token
GET    /me                  → Get current user profile
PATCH  /me                  → Update profile
```

### Family Routes (`/api/v1/family/`)
```
GET    /members             → List all family members
POST   /members             → Add a family member (manual)
PATCH  /members/:id         → Update family member
DELETE /members/:id         → Remove family member
POST   /invite              → Send invite link/OTP to family member
GET    /invite/:token       → Validate invite token (public)
POST   /invite/:token/accept → Accept invite, link accounts
GET    /tree                → Get full family tree structure
GET    /shared-risks        → Hereditary risk patterns across family
```

### Records Routes (`/api/v1/records/`)
```
GET    /                    → List records (paginated, filterable)
GET    /:id                 → Get single record detail
POST   /upload              → Upload file, trigger OCR pipeline
PATCH  /:id/verify          → User confirms/corrects extracted data
DELETE /:id                 → Delete record
GET    /timeline            → Chronological health timeline
GET    /family              → Family members' records (with permission)
GET    /entities            → All extracted entities (diseases, meds)
```

### Risk Routes (`/api/v1/risk/`)
```
GET    /profile             → User's full risk profile
GET    /predictions         → List all risk predictions
POST   /generate            → Trigger risk model re-run
GET    /predictions/:disease → Single disease risk detail
GET    /family-risk         → Family-level hereditary risk map
GET    /watchlist           → Top flagged future risks
```

### Insights Routes (`/api/v1/insights/`)
```
GET    /health-score        → Computed health score (0–100)
GET    /trends              → Disease frequency over time
GET    /heatmap             → Recurrence heatmap data
GET    /summary             → AI-generated health summary
GET    /recommendations     → Personalized recommendations list
```

### Doctor Routes (`/api/v1/doctor/`)
```
POST   /login               → Doctor login (role-based)
GET    /patients            → Doctor's patient list
GET    /patients/:id        → Patient summary
GET    /patients/:id/relevant → Context-aware relevant records
GET    /patients/:id/family-risk → Generational risk summary
POST   /session/extend      → Extend active session
```

---

## IMPLEMENTATION DETAILS

### 1. Auth Service (auth_service.py)
- JWT: access token (15 min expiry), refresh token (7 days, stored in Redis)
- Bcrypt rounds: 12
- Email OTP: 6-digit, 10 min expiry, stored in Redis
- Role-based access decorator: `@require_role(['patient', 'doctor'])`

### 2. Family Service (family_service.py)
- `generate_invite_token()`: 32-byte URL-safe token, stored in Redis with 72h expiry
- `link_accounts(inviter_id, invitee_id, relationship)`: creates bidirectional relationship
- `get_family_tree(user_id)`: recursive tree builder returning nested JSON
- `detect_hereditary_patterns(user_id)`: aggregates diseases across family members, counts occurrences per generation

### 3. Record Service (record_service.py)
- On upload: save file to S3, create record with status 'pending', trigger Celery task
- Celery task: run OCR → NLP → store extracted_entities → update status to 'done'
- `get_timeline(user_id)`: joins records + entities, ordered by record_date

### 4. File: requirements.txt
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
alembic==1.13.1
asyncpg==0.29.0
motor==3.4.0                  # async MongoDB
redis==5.0.4
celery==5.3.6
boto3==1.34.0                 # S3
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
sendgrid==6.11.0
pydantic-settings==2.2.1
pillow==10.3.0
python-dotenv==1.0.1
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.6
```

### 5. File: .env.example
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost/genhealth
MONGODB_URL=mongodb://localhost:27017/genhealth
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-256-bit-secret-key-here
ALGORITHM=HS256
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_BUCKET_NAME=genhealth-records
SENDGRID_API_KEY=your-sendgrid-key
FROM_EMAIL=noreply@genhealth.ai
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

### 6. File: docker-compose.yml
```yaml
version: '3.9'
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, mongodb, redis]
    volumes: ["./backend:/app"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info
    env_file: .env
    depends_on: [redis, postgres]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: genhealth
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes: [pgdata:/var/lib/postgresql/data]
    ports: ["5432:5432"]

  mongodb:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: [mongodata:/data/db]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
  mongodata:
```

### 7. File: README.md (setup instructions)
Include:
- Prerequisites (Python 3.11, Docker, Node.js)
- Setup steps: clone → cp .env.example .env → docker-compose up
- Database migrations: `alembic upgrade head`
- Run dev server
- API docs: http://localhost:8000/docs
- Frontend: open frontend/index.html or serve with `python -m http.server 3000`

### 8. File: .gitignore
Include: __pycache__, .env, *.pyc, node_modules, .DS_Store, uploads/, *.egg-info, .venv, dist/, build/

---

## IMPORTANT NOTES
- All endpoints must return consistent JSON: `{"success": true, "data": {...}, "message": "..."}`
- All errors: `{"success": false, "error": "...", "code": "ERROR_CODE"}`
- Add CORS middleware allowing the frontend origin
- Add request logging middleware
- Write docstrings for every function
- Include at minimum 3 unit tests per router file

Build all of this now. Generate every file completely. Do not use placeholder comments like "# TODO" — write the full implementation.
```

---

# ═══════════════════════════════════════════════
# PART 2 — OCR + NLP + ML/DL PIPELINES
# ═══════════════════════════════════════════════

```
This is Part 2 of the GenHealth AI build. The backend structure from Part 1 is already set up. Now build all ML, DL, OCR, and NLP modules inside the `backend/ml/` directory.

---

## WHAT TO BUILD IN THIS PART

```
backend/ml/
├── ocr/
│   ├── __init__.py
│   ├── extractor.py           # Main OCR orchestrator
│   ├── preprocessor.py        # Image preprocessing
│   └── pdf_handler.py         # PDF → image conversion
│
├── nlp/
│   ├── __init__.py
│   ├── entity_extractor.py    # NER for medical entities
│   ├── normalizer.py          # Map to ICD-10, ATC codes
│   ├── date_parser.py         # Extract and normalize dates
│   └── medical_vocab.py       # Medical terminology lookups
│
├── risk_models/
│   ├── __init__.py
│   ├── feature_engineer.py    # Build feature vectors from records
│   ├── diabetes_model.py      # Diabetes risk model
│   ├── hypertension_model.py  # Hypertension risk model
│   ├── thyroid_model.py       # Thyroid disorder risk model
│   ├── heart_model.py         # Cardiovascular risk model
│   ├── risk_classifier.py     # Combines all models → risk profile
│   └── model_registry.py     # Load/save trained models
│
├── generational/
│   ├── __init__.py
│   ├── pattern_detector.py    # Find hereditary patterns in family tree
│   ├── heritability_scorer.py # Compute hereditary risk weight
│   └── family_graph.py        # Graph-based family risk traversal
│
├── training/
│   ├── train_diabetes.py
│   ├── train_hypertension.py
│   ├── train_thyroid.py
│   └── train_heart.py
│
├── models_store/              # Saved .pkl / .h5 model files (gitignored, download via script)
│   └── download_models.py
│
└── utils/
    ├── confidence.py
    └── medical_constants.py
```

---

## MODULE 1: OCR PIPELINE

### backend/ml/ocr/preprocessor.py
```
Build an image preprocessor for prescription photos using OpenCV and Pillow.

Functions to implement:

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Full preprocessing pipeline for prescription images.
    Steps:
    1. Load image (handle JPEG, PNG, WEBP, HEIC via pillow-heif)
    2. Convert to grayscale
    3. Deskew: detect rotation angle using Hough transform, correct
    4. Denoise: apply cv2.fastNlMeansDenoising
    5. Adaptive thresholding: cv2.adaptiveThreshold (ADAPTIVE_THRESH_GAUSSIAN_C)
    6. Morphological operations: erode then dilate (kernel 1x1) to sharpen text
    7. Scale to at least 300 DPI (resize if smaller)
    8. Return processed numpy array
    """

def detect_document_corners(image: np.ndarray) -> np.ndarray:
    """
    Detect 4 corners of a document in photo (for perspective correction).
    Use cv2.findContours + cv2.approxPolyDP.
    Apply perspective transform to get top-down view.
    """

def enhance_for_handwriting(image: np.ndarray) -> np.ndarray:
    """
    Additional enhancement for handwritten prescriptions:
    - Increase contrast using CLAHE
    - Apply bilateral filter to preserve edges
    """
```

### backend/ml/ocr/extractor.py
```
Build the main OCR extraction module.

Dependencies: pytesseract, easyocr, pdf2image

class OCRExtractor:
    def __init__(self):
        # Initialize EasyOCR reader for English + Hindi (for Indian prescriptions)
        self.easy_reader = easyocr.Reader(['en', 'hi'], gpu=False)
        self.tesseract_config = '--oem 3 --psm 6 -l eng+hin'

    def extract_from_image(self, image_path: str) -> dict:
        """
        Run dual OCR (Tesseract + EasyOCR) and merge results.
        
        1. Preprocess image using preprocessor.py
        2. Run Tesseract: get text + word-level bounding boxes + confidence
        3. Run EasyOCR: get text + bounding boxes + confidence
        4. Merge: for each region, pick result with higher confidence
        5. Post-process: fix common OCR errors (0→O, 1→I in medical context)
        6. Return: {
             "raw_text": str,
             "words": [{"text": str, "bbox": [...], "confidence": float}],
             "overall_confidence": float,
             "language_detected": str
           }
        """

    def extract_from_pdf(self, pdf_path: str) -> dict:
        """
        Convert PDF to images (300 DPI via pdf2image), run extract_from_image
        on each page, merge all text preserving page order.
        """

    def _merge_ocr_results(self, tesseract_result, easyocr_result) -> dict:
        """
        Use IOU (Intersection over Union) of bounding boxes to align results.
        For overlapping regions, pick the one with higher word-level confidence.
        """

    def _fix_medical_ocr_errors(self, text: str) -> str:
        """
        Fix common OCR errors in medical context:
        - '0mg' → 'Omg' fix (never replace 0 after a digit with O)
        - 'mcq' → 'mcg' (micrograms common misread)
        - 'bd' stays 'bd' (twice daily)
        - Apply regex corrections from medical_constants.py
        """
```

---

## MODULE 2: NLP PIPELINE

### backend/ml/nlp/entity_extractor.py
```
Build a medical Named Entity Recognition (NER) system.

Use TWO approaches and combine them:

APPROACH A — Rule-based (fast, high precision for common patterns):
- Regex + medical vocabulary matching
- Drug name dictionary lookup (use OpenFDA drug list)
- Disease keyword matching with ICD-10 vocabulary

APPROACH B — ML-based (transformer model for complex cases):
- Use: `medicalai/ClinicalBERT` from HuggingFace (or `blaze999/Medical-NER`)
- Fine-tuned on medical NER datasets (BC5CDR, i2b2)
- Entities: DISEASE, MEDICINE, DOSAGE, FREQUENCY, DOCTOR, HOSPITAL, DATE, TEST, TEST_RESULT

class MedicalEntityExtractor:
    
    ENTITY_TYPES = {
        'DISEASE': {'color': '#EF4444', 'icon': '🔴'},
        'MEDICINE': {'color': '#3B82F6', 'icon': '💊'},
        'DOSAGE': {'color': '#8B5CF6', 'icon': '⚖️'},
        'FREQUENCY': {'color': '#EC4899', 'icon': '🔁'},
        'DOCTOR': {'color': '#8B5CF6', 'icon': '👨‍⚕️'},
        'HOSPITAL': {'color': '#6366F1', 'icon': '🏥'},
        'DATE': {'color': '#64748B', 'icon': '📅'},
        'TEST': {'color': '#F59E0B', 'icon': '🧪'},
        'TEST_RESULT': {'color': '#F59E0B', 'icon': '📊'},
    }

    def __init__(self):
        # Load ClinicalBERT NER pipeline
        # Load medical vocabulary dictionaries
        # Compile regex patterns

    def extract(self, text: str) -> dict:
        """
        Returns:
        {
          "entities": [
            {
              "text": "Hypothyroidism",
              "type": "DISEASE",
              "start": 12,
              "end": 26,
              "confidence": 0.96,
              "normalized": "Hypothyroidism",
              "icd10_code": "E03.9",
              "source": "ml"  # or "rule"
            },
            ...
          ],
          "medicines": [...],
          "diseases": [...],
          "dates": [...],
          "doctors": [...],
          "structured_summary": { ... }
        }
        """

    def _rule_based_extract(self, text: str) -> list:
        """
        Patterns to implement:
        - Dosage: regex r'\b\d+\.?\d*\s*(mg|mcg|ml|IU|units?|g|kg)\b'
        - Frequency: r'\b(once|twice|thrice|od|bd|tds|qid|sos|prn|daily|weekly)\b'
        - Dates: r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b'
        - Drug names: match against loaded drug dictionary (case-insensitive)
        """

    def _ml_based_extract(self, text: str) -> list:
        """
        Run ClinicalBERT NER pipeline.
        Aggregate subword tokens back to full words.
        Filter by confidence > 0.7.
        """

    def _merge_and_deduplicate(self, rule_entities, ml_entities) -> list:
        """
        Merge results. For overlapping spans, prefer ML if confidence > 0.85,
        else prefer rule-based. Remove duplicates by span overlap.
        """

    def extract_structured_prescription(self, entities: list) -> dict:
        """
        Convert entity list into structured prescription dict:
        {
          "conditions": [...],
          "medications": [{"name": ..., "dosage": ..., "frequency": ..., "duration": ...}],
          "doctor": {"name": ..., "hospital": ...},
          "date": ...,
          "tests": [...],
          "follow_up": ...
        }
        """
```

### backend/ml/nlp/normalizer.py
```
Map extracted entities to standard medical codes.

class MedicalNormalizer:

    def normalize_disease(self, disease_text: str) -> dict:
        """
        Map disease text to ICD-10 code.
        Method:
        1. Try exact match in ICD-10 lookup table (load from WHO ICD-10 CSV)
        2. Try fuzzy match using rapidfuzz (threshold: 85%)
        3. Try UMLS concept mapping if available
        Returns: {"display": str, "icd10_code": str, "confidence": float}
        """

    def normalize_medicine(self, medicine_text: str) -> dict:
        """
        Map medicine to ATC code and generic name.
        Use OpenFDA drug database for lookups.
        Returns: {"brand_name": str, "generic_name": str, "atc_code": str, "drug_class": str}
        """

    def normalize_date(self, date_text: str) -> str:
        """
        Convert any date format to ISO 8601 (YYYY-MM-DD).
        Handle: DD/MM/YYYY, MM-DD-YYYY, '12 Jun 2025', '12th June 2025', etc.
        Use dateutil.parser with dayfirst=True for Indian date formats.
        """
```

---

## MODULE 3: ML/DL RISK PREDICTION MODELS

### backend/ml/risk_models/feature_engineer.py
```
Build the feature engineering pipeline that converts raw health records into ML-ready feature vectors.

class HealthFeatureEngineer:

    FEATURES = {
        # Personal features
        'age': float,
        'gender_male': int,           # 1/0
        'bmi': float,                 # if available
        'blood_group': str,
        
        # Medical history features (derived from records)
        'has_diabetes_history': int,
        'has_hypertension_history': int,
        'has_thyroid_history': int,
        'has_heart_history': int,
        'disease_count': int,
        'unique_medicines_count': int,
        'record_count': int,
        'years_of_history': float,
        
        # Lab values (latest available)
        'latest_blood_sugar_fasting': float,
        'latest_hba1c': float,
        'latest_tsh': float,
        'latest_systolic_bp': float,
        'latest_cholesterol': float,
        'latest_bmi': float,
        
        # Recurrence features
        'diabetes_recurrence_count': int,
        'hypertension_recurrence_count': int,
        'thyroid_med_count': int,
        
        # Generational / family features
        'parent_diabetes': int,       # 1 if any parent has diabetes
        'grandparent_diabetes': int,
        'family_diabetes_count': int, # total affected family members
        'parent_hypertension': int,
        'grandparent_heart_disease': int,
        'family_heart_count': int,
        'parent_thyroid': int,
        'family_thyroid_count': int,
        'family_cancer_count': int,
        
        # Lifestyle signals (from recommendation acknowledgment)
        'exercise_regularity': float,  # 0–1 if tracked
        'diet_quality_score': float,
    }

    def build_features(self, user_id: str, db_session) -> dict:
        """
        Query user records, extracted entities, and family records.
        Build and return the complete feature vector as a dict.
        Handle missing values by imputing with population medians.
        """

    def build_family_features(self, user_id: str, db_session) -> dict:
        """
        Traverse the family graph for this user.
        Count disease occurrences per relationship type (parent=2x weight, grandparent=1x).
        Returns the generational feature sub-dict.
        """
```

### backend/ml/risk_models/diabetes_model.py
```
Build a Diabetes Risk Prediction model.

Use an ENSEMBLE approach combining:
1. XGBoost classifier (tabular data, handles missing values)
2. A small neural network (PyTorch) for interaction effects
3. Final prediction: weighted average (0.6 XGBoost + 0.4 Neural Net)

Input features (subset of HealthFeatureEngineer output):
- age, gender_male, bmi, family_diabetes_count, parent_diabetes, grandparent_diabetes,
  latest_blood_sugar_fasting, latest_hba1c, has_diabetes_history, disease_count,
  exercise_regularity, diet_quality_score

class DiabetesRiskModel:

    def __init__(self):
        self.xgb_model = None    # XGBClassifier
        self.nn_model = None     # PyTorch DiabetesNet
        self.scaler = None       # StandardScaler for neural net input
        self.feature_names = [...] # ordered list matching training

    def predict(self, features: dict) -> dict:
        """
        Returns:
        {
          "probability": 0.62,
          "risk_level": "high",        # low < 0.30, moderate 0.30–0.60, high > 0.60
          "contributing_factors": [
            {"factor": "Parent has Type 2 Diabetes", "weight": 0.28, "source": "family"},
            {"factor": "Fasting blood sugar: 118 mg/dL", "weight": 0.22, "source": "lab"},
            {"factor": "Paternal grandfather had Diabetes", "weight": 0.15, "source": "family"},
            {"factor": "Sedentary lifestyle indicator", "weight": 0.10, "source": "lifestyle"}
          ],
          "model_confidence": 0.87,
          "xgb_probability": 0.65,
          "nn_probability": 0.57
        }
        """

    def get_feature_importance(self, features: dict) -> list:
        """
        Use SHAP values (shap library) on the XGBoost model.
        Return top 5 features with their SHAP values as contributing_factors.
        """

class DiabetesNet(nn.Module):
    """
    PyTorch neural network for diabetes prediction.
    Architecture:
    - Input: feature_count neurons
    - Hidden 1: 64 neurons, ReLU, BatchNorm, Dropout(0.3)
    - Hidden 2: 32 neurons, ReLU, BatchNorm, Dropout(0.2)
    - Hidden 3: 16 neurons, ReLU
    - Output: 1 neuron, Sigmoid
    """
```

### Build identical model files for:
- `hypertension_model.py` — features: age, gender, family BP history, latest BP readings, salt intake, stress indicators
- `thyroid_model.py` — features: gender (female 3x weight), family thyroid history, TSH levels, iodine intake region
- `heart_model.py` — features: age, family heart history, cholesterol, BP, diabetes status, smoking signals

### backend/ml/risk_models/risk_classifier.py
```
Orchestrates all individual models → unified risk profile.

class RiskClassifier:

    def __init__(self):
        self.models = {
            'diabetes': DiabetesRiskModel(),
            'hypertension': HypertensionRiskModel(),
            'thyroid': ThyroidRiskModel(),
            'heart_disease': HeartRiskModel(),
        }
        self.feature_engineer = HealthFeatureEngineer()

    def generate_full_risk_profile(self, user_id: str, db_session) -> dict:
        """
        1. Build feature vector
        2. Run all disease models
        3. Compute overall health score:
           health_score = 100 - sum(prob * weight for each disease)
           weights: diabetes=25, hypertension=25, heart=30, thyroid=20
        4. Generate watchlist: diseases with probability > 0.4
        5. Return complete risk profile
        """

    def compute_health_score(self, predictions: dict) -> int:
        """Score from 0-100. Higher = healthier."""

    def generate_watchlist(self, predictions: dict) -> list:
        """Diseases predicted > 40% probability, sorted by probability."""
```

---

## MODULE 4: GENERATIONAL ANALYSIS

### backend/ml/generational/pattern_detector.py
```
Detect hereditary health patterns across family generations.

class HereditaryPatternDetector:

    # Diseases with known strong hereditary components
    HEREDITARY_DISEASES = {
        'type_2_diabetes': {'heritability': 0.72, 'icd10_prefix': 'E11'},
        'hypertension': {'heritability': 0.54, 'icd10_prefix': 'I10'},
        'hypothyroidism': {'heritability': 0.67, 'icd10_prefix': 'E03'},
        'hyperthyroidism': {'heritability': 0.79, 'icd10_prefix': 'E05'},
        'coronary_artery_disease': {'heritability': 0.56, 'icd10_prefix': 'I25'},
        'depression': {'heritability': 0.40, 'icd10_prefix': 'F32'},
        'breast_cancer': {'heritability': 0.30, 'icd10_prefix': 'C50'},
        'colorectal_cancer': {'heritability': 0.35, 'icd10_prefix': 'C18'},
        'asthma': {'heritability': 0.65, 'icd10_prefix': 'J45'},
        'osteoporosis': {'heritability': 0.60, 'icd10_prefix': 'M80'},
    }

    # Relationship weights (how much a relative's condition raises your risk)
    RELATIONSHIP_WEIGHTS = {
        'parent': 2.0,
        'sibling': 1.8,
        'grandparent': 1.0,
        'aunt_uncle': 0.5,
        'child': 1.5,
        'spouse': 0.1,
    }

    def detect_patterns(self, user_id: str, family_records: list) -> dict:
        """
        For each hereditary disease:
        1. Check how many family members have it
        2. Apply relationship weights
        3. Calculate weighted_family_risk_score
        4. Flag if score > threshold (1.5 = high, 0.8 = moderate)
        
        Returns:
        {
          "patterns": [
            {
              "disease": "Type 2 Diabetes",
              "icd10": "E11",
              "affected_members": [
                {"name": "Father", "relationship": "parent", "weight": 2.0},
                {"name": "Paternal Grandfather", "relationship": "grandparent", "weight": 1.0}
              ],
              "weighted_score": 3.0,
              "risk_flag": "high",
              "heritability": 0.72,
              "generation_span": 2
            }
          ],
          "hereditary_risk_boost": {   # Added to individual model predictions
            "diabetes": 0.18,
            "hypertension": 0.10
          }
        }
        """

    def build_generation_map(self, family_tree: dict) -> dict:
        """
        Map each family member to a generation number:
        - Grandparents: generation -2
        - Parents: generation -1
        - User: generation 0
        - Children: generation +1
        - Grandchildren: generation +2
        """
```

### backend/ml/generational/family_graph.py
```
Graph-based family relationship traversal using NetworkX.

class FamilyHealthGraph:

    def __init__(self):
        self.graph = nx.DiGraph()

    def build_from_db(self, user_id: str, db_session):
        """
        Load all family_members records.
        Build directed graph: edges from parent → child with relationship label.
        Attach health record summary to each node.
        """

    def get_ancestors(self, user_id: str, max_depth: int = 3) -> list:
        """Return all ancestor nodes up to max_depth generations."""

    def get_shared_conditions(self, user_id: str) -> dict:
        """
        For the user and all ancestors/siblings, find conditions appearing in ≥ 2 nodes.
        Return dict of condition → [affected members]
        """

    def visualize_risk_overlay(self, user_id: str) -> dict:
        """
        Return JSON representation of family tree with risk data for frontend visualization.
        Nodes: id, name, relationship, conditions[], risk_level
        Edges: source, target, relationship_type
        """
```

---

## TRAINING SCRIPTS

### backend/ml/training/train_diabetes.py
```
Training script for the diabetes model.

Dataset: Use Pima Indians Diabetes Dataset (sklearn.datasets or local CSV).
Augment with synthetic generational features.

Steps:
1. Load dataset
2. Add synthetic family history columns (random but statistically realistic)
3. Split: 80% train, 10% val, 10% test
4. Train XGBoost with hyperparameter tuning (Optuna, 50 trials)
5. Train DiabetesNet (PyTorch, 50 epochs, Adam optimizer, LR scheduler)
6. Evaluate: AUC-ROC, precision, recall, F1
7. Save: models_store/diabetes_xgb.pkl, models_store/diabetes_nn.pth, models_store/diabetes_scaler.pkl
8. Print: classification report + confusion matrix

Target metrics: AUC-ROC > 0.82, F1 > 0.75

Include the same script structure for hypertension, thyroid, and heart disease.
```

---

## ADDITIONAL REQUIREMENTS

- All ML modules must have proper Python logging (import logging)
- Handle missing features gracefully: impute with median, do not crash
- Every class must have a `__repr__` and a `health_check()` method that returns model status
- Add `backend/ml/utils/medical_constants.py` with:
  - ICD-10 code lookup dict (top 200 common conditions)
  - ATC drug classification dict (top 500 drugs)
  - Common OCR error correction dict
  - Indian hospital/doctor title patterns for NER
- Add `requirements_ml.txt` separately:
  ```
  torch==2.3.0
  transformers==4.41.0
  xgboost==2.0.3
  scikit-learn==1.4.2
  shap==0.45.0
  easyocr==1.7.1
  pytesseract==0.3.10
  opencv-python==4.9.0.80
  pillow==10.3.0
  pdf2image==1.17.0
  rapidfuzz==3.9.3
  python-dateutil==2.9.0
  spacy==3.7.4
  networkx==3.3
  optuna==3.6.1
  numpy==1.26.4
  pandas==2.2.2
  ```

Build all files completely with full implementation.
```

---

# ═══════════════════════════════════════════════
# PART 3 — FRONTEND ENHANCEMENT + API INTEGRATION
# ═══════════════════════════════════════════════

```
This is Part 3 of the GenHealth AI build. The backend (Part 1) and ML pipelines (Part 2) are complete.

I am attaching `index.html` — the existing UI prototype. Your job is to:
1. Split it into a proper multi-file frontend
2. Wire every screen to the real backend API
3. Add the Family Linking UI (invite flow)
4. Enhance the OCR upload to use the real pipeline
5. Make risk charts pull from real API data

---

## FRONTEND FILE STRUCTURE TO CREATE

```
frontend/
├── index.html              # Main SPA shell (keep existing design, enhance)
├── pages/
│   ├── login.html
│   ├── signup.html
│   └── onboarding.html
├── assets/
│   ├── css/
│   │   ├── base.css        # CSS variables, reset, typography
│   │   ├── layout.css      # Sidebar, header, bottom nav, shell
│   │   ├── components.css  # Cards, badges, chips, buttons, modals
│   │   └── pages.css       # Page-specific styles
│   └── js/
│       ├── config.js       # API_BASE_URL, constants
│       ├── api.js          # All API calls, token management
│       ├── auth.js         # Login/signup/logout flow
│       ├── upload.js       # File upload + OCR progress + entity display
│       ├── family.js       # Family tree, invite flow
│       ├── risk.js         # Risk profile, prediction display
│       ├── charts.js       # SVG charts (radar, gauge, bar, heatmap)
│       ├── records.js      # Records list, filter, detail view
│       ├── recommendations.js
│       └── app.js          # Main SPA router, nav, init
```

---

## FILE: assets/js/config.js
```javascript
const CONFIG = {
  API_BASE: 'http://localhost:8000/api/v1',
  TOKEN_KEY: 'genhealth_access_token',
  REFRESH_KEY: 'genhealth_refresh_token',
  USER_KEY: 'genhealth_user',
  DARK_MODE_KEY: 'genhealth_dark',
  VERSION: '1.0.0',
};
```

---

## FILE: assets/js/api.js
Build a complete API client class:

```javascript
class GenHealthAPI {
  constructor(baseURL) { ... }

  // Token management
  getToken() { return localStorage.getItem(CONFIG.TOKEN_KEY); }
  setTokens(access, refresh) { ... }
  clearTokens() { ... }

  // Core request method with auto-refresh
  async request(method, path, body, isFormData) {
    // Add Authorization: Bearer header
    // On 401: try refresh token → retry once → redirect to login
    // Return parsed JSON or throw error
  }

  // Auth
  async login(email, password) { ... }
  async signup(data) { ... }
  async refreshToken() { ... }
  async getMe() { ... }
  async updateProfile(data) { ... }

  // Family
  async getFamilyMembers() { ... }
  async addFamilyMember(data) { ... }
  async sendFamilyInvite(memberId, method, contact) { ... }
  async acceptInvite(token) { ... }
  async getFamilyTree() { ... }
  async getSharedRisks() { ... }

  // Records
  async getRecords(filters) { ... }
  async getRecord(id) { ... }
  async uploadPrescription(file, metadata) { ... }  // multipart/form-data
  async verifyRecord(id, corrections) { ... }
  async getTimeline() { ... }

  // Risk
  async getRiskProfile() { ... }
  async getRiskPredictions() { ... }
  async generateRisk() { ... }  // trigger re-run
  async getWatchlist() { ... }

  // Insights
  async getHealthScore() { ... }
  async getTrends() { ... }
  async getRecommendations() { ... }

  // Doctor portal
  async doctorLogin(email, password) { ... }
  async getPatients() { ... }
  async getPatientSummary(patientId) { ... }
  async getRelevantRecords(patientId, complaint) { ... }
}

const api = new GenHealthAPI(CONFIG.API_BASE);
```

---

## FILE: assets/js/upload.js
Wire the upload screen to the real API:

```javascript
class PrescriptionUploader {

  constructor() {
    this.file = null;
    this.pollInterval = null;
  }

  init() {
    // Setup drag-and-drop handlers
    // Setup file input change handler
    // Setup camera capture on mobile
  }

  handleFile(file) {
    // Validate: type (image/jpeg, image/png, image/webp, application/pdf)
    // Validate: size < 20MB
    // Show preview thumbnail
    // Enable upload button
  }

  async upload() {
    // Show processing state with animated DNA helix spinner
    // POST to /api/v1/records/upload
    // Poll GET /api/v1/records/:id every 2 seconds until status = 'done'
    // On done: render extracted entities
  }

  renderEntities(entities) {
    // Show each entity as a colored chip:
    // Disease = red, Medicine = blue, Date = grey, Doctor = purple
    // Each chip is editable (click to edit text)
    // Show confidence score per entity
    // "Confirm & Save" button calls verifyRecord API
  }

  pollStatus(recordId) {
    // Poll every 2s, show step-by-step progress:
    // Step 1: "Uploading file..." 
    // Step 2: "Running OCR..."
    // Step 3: "Extracting medical entities..."
    // Step 4: "Mapping to medical codes..."
    // Step 5: "Done!"
  }
}
```

---

## FAMILY LINKING SYSTEM UI

This is a critical feature. Build a complete invite-and-link flow.

### Add Family Member Modal (2 paths):

**Path A — Manual (family member not on GenHealth):**
1. Form: Name, Relationship, Gender, DOB, Is Deceased toggle
2. Save → family member added without account link
3. Option to "Invite to GenHealth" → shows Path B

**Path B — Invite Existing Person:**
```
┌─────────────────────────────────────┐
│  Invite [Father] to GenHealth       │
│                                     │
│  Choose how to invite:              │
│                                     │
│  📧 Email                           │
│  ┌─────────────────────────────┐    │
│  │ Enter email address          │    │
│  └─────────────────────────────┘    │
│                                     │
│  📱 WhatsApp / SMS                  │
│  ┌─────────────────────────────┐    │
│  │ Enter phone number           │    │
│  └─────────────────────────────┘    │
│                                     │
│  🔗 Share Link                      │
│  [Copy Link] [QR Code]              │
│                                     │
│  [Send Invite]                      │
└─────────────────────────────────────┘
```

**Invite Status Badges on Family Tree Nodes:**
- ⏳ Invite Sent (yellow)
- ✅ Linked (green)
- ❌ Declined (red)
- ➕ Not Invited (grey, with invite button)

**When invitee opens the invite link:**
- Landing page: "Aryan Sharma has added you as their Father on GenHealth AI"
- Shows: what data will be shared, privacy explanation
- Options: "Create Account & Link" or "Link Existing Account"
- After accepting: both accounts show as linked, health data syncs

### Family Tree Component (SVG-based):
```javascript
class FamilyTreeRenderer {
  
  render(treeData, containerId) {
    // Build SVG family tree
    // Generations as horizontal rows
    // Each node: circle (60px) + avatar initials + name below + condition badges
    // Connecting lines: parent-child lines, spouse horizontal line
    // Color node border by risk level (green/amber/red)
    // DNA pulse animation on nodes with hereditary risk
    // Click node → show member health summary panel
    // Invite button on unlinked nodes
  }

  renderNode(member) {
    // SVG group: circle + text + badges + invite overlay
  }

  renderConnections(members) {
    // SVG paths for family relationships
  }
}
```

---

## ENHANCED RISK PAGE

Wire to real API and enhance charts:

```javascript
// charts.js — all built with vanilla SVG, no libraries

function drawRadarChart(containerId, data) {
  // SVG radar chart with 6 axes
  // Animate from zero on first load
  // Hover tooltip showing exact probability
  // Data: [{axis: 'Diabetes', value: 0.62}, ...]
}

function drawHealthGauge(containerId, score) {
  // Animated arc gauge (0-100)
  // Color: green 80+, amber 50-79, red <50
  // Center text: score + "Health Score"
  // Animate arc draw on load
}

function drawTrendLine(containerId, data) {
  // SVG line chart for disease probability over time
  // X: months, Y: probability %
  // Dot at each data point with tooltip
}

function drawHeatmap(containerId, data) {
  // Calendar heatmap (GitHub-style)
  // 52 weeks × 7 days grid
  // Color intensity = health event density
}
```

---

## IMPORTANT FRONTEND REQUIREMENTS

1. **Token Storage:** Access token in localStorage, auto-refresh before expiry
2. **Loading States:** Every API call must show a skeleton loader, not a blank screen
3. **Error States:** Network errors show a toast + retry button
4. **Empty States:** Every list has an illustrated empty state with a CTA
5. **Offline Detection:** Show banner "You're offline — showing cached data" using navigator.onLine
6. **Form Validation:** Inline validation on all forms (email format, password strength meter, required fields)
7. **Mobile Camera:** On upload page, mobile shows camera icon that opens device camera
8. **PWA Manifest:** Add manifest.json for "Add to Home Screen" on mobile
9. **Accessibility:** All icons have aria-label, all forms have labels, focus rings visible

Build all files completely. The existing index.html design system (colors, typography, components) must be preserved exactly — only add API wiring and new components.
```

---

# ═══════════════════════════════════════════════
# PART 4 — DOCTOR PORTAL + SECURITY + NOTIFICATIONS
# ═══════════════════════════════════════════════

```
This is Part 4 of the GenHealth AI build. Parts 1–3 are complete (backend, ML, frontend). Now build:
1. Complete Doctor Portal
2. Session-based access control
3. In-app notification system
4. Data privacy controls
5. Audit logging

---

## DOCTOR PORTAL BACKEND

### backend/app/routers/doctor.py

Doctor login is role-based — same users table, role='doctor'.

Endpoints:
```
POST /api/v1/doctor/login
  → Validates role='doctor', returns doctor JWT

GET /api/v1/doctor/patients
  → Returns list of patients who have granted this doctor access
  → Include: name, age, last record date, chief complaint (from last session)

GET /api/v1/doctor/patients/:patient_id/summary
  → Compact health summary:
    - Demographics (age, gender, blood group)
    - Active conditions (last 12 months)
    - Current medications
    - Last 3 lab results
    - Top 2 risks with probabilities
    - Generational insight if any hereditary disease detected
  → Only returns if doctor_access record is active for this doctor+patient

GET /api/v1/doctor/patients/:patient_id/relevant?complaint=<text>
  → Take the complaint text, run NLP to extract medical keywords
  → Score each record for relevance to complaint keywords
  → Return top 5 records sorted by relevance score
  → Include: record summary, date, confidence score, why it's relevant

POST /api/v1/doctor/session/extend
  → Reset expires_at to +1 hour from now

DELETE /api/v1/doctor/patients/:patient_id/access
  → Doctor can voluntarily end their own access session
```

### backend/services/context_service.py
```python
class ClinicalContextService:
    
    def get_relevant_records(self, patient_id: str, complaint: str, doctor_id: str) -> list:
        """
        1. Extract keywords from complaint using spaCy NLP
        2. Match keywords against extracted_entities for this patient
        3. Score each record: 
           - Exact disease match: +3
           - Related disease (same ICD chapter): +2  
           - Same medicine class: +1
           - Recent (< 6 months): +1 bonus
        4. Sort by score descending
        5. Return top 5 with relevance_reason string
        """
    
    def generate_patient_summary(self, patient_id: str) -> dict:
        """
        Build the context-aware patient summary card for doctors.
        Include generational_insight if any hereditary pattern detected.
        """
```

---

## DOCTOR PORTAL FRONTEND

### frontend/pages/doctor.html

Separate page (not in main SPA) — doctors open this URL.

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│  🏥 GenHealth AI — Doctor Portal           [Dr. Name ▼]│
│────────────────────────────────────────────────────────│
│  [Patient Search: "Search by name or ID..."]           │
│════════════════════════════════════════════════════════│
│  [Patient List Sidebar 280px]  │  [Patient Detail]     │
│                                │                       │
│  ● Aryan Sharma, 24M           │  PATIENT: Aryan Sharma│
│    Last visit: 12 Jun          │  24M · B+ · Delhi     │
│    Risk: Moderate              │                       │
│  ● Priya Mehta, 38F            │  Chief Complaint:     │
│    Last visit: 8 Jun           │  [Type here...]  [⚡]  │
│                                │                       │
│                                │  🧬 HEREDITARY ALERT  │
│                                │  Thyroid + Diabetes   │
│                                │  detected in family   │
│                                │                       │
│                                │  RELEVANT RECORDS (3) │
│                                │  ┌──────────────────┐ │
│                                │  │ Hypothyroidism   │ │
│                                │  │ Jun 2025 · 94%   │ │
│                                │  └──────────────────┘ │
│                                │                       │
│                                │  [Full Timeline ▼]    │
│                                │  [Print Summary] [PDF]│
│────────────────────────────────│───────────────────────│
│  Session: 47 min remaining  [Extend Session]  [End]    │
└────────────────────────────────────────────────────────┘
```

**Implement:**
- Patient search with debounced API calls (300ms)
- Chief complaint input → click ⚡ → loads relevant records
- Hereditary Alert banner (teal, DNA icon) if generational risk detected
- Relevant record cards with relevance reason tooltip
- Session countdown timer (60 min default, extend button)
- Auto-logout when session expires with warning at 5 min
- Print-friendly CSS for summary print
- Consent badge: "Patient granted access on [date] until [date]"

---

## NOTIFICATION SYSTEM

### backend/app/models/notification.py
```python
class Notification(Base):
    id: UUID
    user_id: UUID
    type: str  # invite_received|invite_accepted|risk_updated|record_processed|doctor_accessed|reminder
    title: str
    body: str
    data: dict  # extra context (record_id, invite_token, etc.)
    is_read: bool = False
    created_at: datetime
```

### backend/app/routers/notifications.py
```
GET  /api/v1/notifications          → List (paginated, unread first)
PATCH /api/v1/notifications/:id/read → Mark as read
PATCH /api/v1/notifications/read-all → Mark all read
DELETE /api/v1/notifications/:id     → Delete
```

**Notification triggers (in respective services):**
- Family invite sent → notify invitee via email + in-app
- Invite accepted → notify inviter in-app
- Record OCR complete → notify user in-app
- Risk prediction updated → notify user in-app
- Doctor accessed records → notify patient in-app (audit trail)

### Frontend notification panel:
```javascript
class NotificationPanel {
  // Bell icon with unread count badge
  // Dropdown panel (max-height 400px, scrollable)
  // Poll for new notifications every 30s (or use WebSocket if time allows)
  // Each notification: icon (by type) + title + body + time ago + read indicator
  // Click notification → navigate to relevant screen
}
```

---

## DATA PRIVACY CONTROLS

### backend/app/routers/privacy.py
```
GET    /api/v1/privacy/consent          → List all active doctor access grants
DELETE /api/v1/privacy/consent/:id      → Revoke doctor access
GET    /api/v1/privacy/audit-log        → Full audit log (who accessed what when)
POST   /api/v1/privacy/export           → Queue data export (async, email when ready)
DELETE /api/v1/privacy/account          → Delete account (multi-step: confirm OTP first)
GET    /api/v1/privacy/encryption-status → Returns encryption details
```

### backend/app/middleware/audit_logger.py
```python
class AuditLogger:
    """
    Automatically log all data access events to audit_log table.
    Log on every: record read, family data read, risk profile read, doctor access.
    Fields: user_id, actor_id, actor_role, action, resource_type, resource_id, ip_address, timestamp
    """
```

### Encryption implementation:
- All PII fields encrypted at rest using SQLAlchemy-Utils EncryptedType (AES-256)
- Encrypt: full_name, email, date_of_birth, phone, raw_ocr_text
- S3 server-side encryption (SSE-S3) for all uploaded files
- HTTPS enforced (add redirect middleware)

---

## CONSENT FLOW (GRANT DOCTOR ACCESS)

From the patient Settings → Privacy page:

```
┌──────────────────────────────────────┐
│  Grant Doctor Access                 │
│                                      │
│  Doctor's Email or ID:               │
│  [dr.meera@apollo.com         ]      │
│                                      │
│  Access Duration:                    │
│  ○ 1 hour (single consultation)      │
│  ○ 1 day                             │
│  ○ 1 week                            │
│  ○ 1 month                           │
│                                      │
│  What can they see?                  │
│  ☑ My health records                 │
│  ☑ My risk profile                   │
│  ☑ Family history (generational)     │
│  ☐ Raw prescription images           │
│                                      │
│  ⚠️ The doctor will be notified and  │
│  can view your data until the        │
│  access period ends. You can revoke  │
│  access at any time.                 │
│                                      │
│  [Cancel]          [Grant Access]    │
└──────────────────────────────────────┘
```

Build all files completely.
```

---

# ═══════════════════════════════════════════════
# PART 5 — GITHUB SETUP + DEPLOYMENT + FINAL INTEGRATION
# ═══════════════════════════════════════════════

```
This is Part 5 — the final part of GenHealth AI. Set up GitHub, CI/CD, deployment configuration, and final integration testing.

---

## GITHUB REPOSITORY SETUP

### .github/workflows/ci.yml
```yaml
name: GenHealth AI CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: genhealth_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements.txt
      - run: pip install -r backend/requirements_ml.txt
      - run: |
          cd backend
          alembic upgrade head
          pytest tests/ -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install ruff black isort
      - run: ruff check backend/
      - run: black --check backend/
```

### .github/workflows/deploy.yml
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t genhealth-api ./backend
      - name: Deploy (configure for your platform: Railway, Render, or AWS)
        run: echo "Add your deployment commands here"
```

---

## README.md (Complete)

Write a comprehensive README with:

```markdown
# GenHealth AI 🧬
### Generational Health Intelligence Platform

> AI-powered platform that tracks your family's health across generations, predicts hereditary disease risks, and enables smarter medical decisions.

## ✨ Features
- 📄 OCR + NLP prescription parsing (Tesseract + EasyOCR + ClinicalBERT)
- 🧠 ML/DL disease risk prediction (XGBoost + PyTorch ensemble)
- 🧬 Generational health analysis (family graph-based hereditary detection)
- 👨‍👩‍👧 Family linking via invite link / QR / email / WhatsApp
- 👨‍⚕️ Doctor portal with context-aware record surfacing
- 📊 Interactive health dashboard with real-time risk insights
- 🔒 AES-256 encryption, consent-based access, full audit log

## 🛠 Tech Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI, PostgreSQL, MongoDB, Redis, Celery |
| OCR | Tesseract, EasyOCR, OpenCV |
| NLP | ClinicalBERT (HuggingFace), spaCy, custom NER |
| ML/DL | XGBoost, PyTorch, SHAP (explainability) |
| Frontend | Vanilla JS SPA, SVG charts, CSS Grid |
| Infrastructure | Docker, AWS S3, SendGrid |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker + Docker Compose
- Node.js 20+ (optional, for dev tooling)

### Setup
```bash
git clone https://github.com/yourusername/genhealth-ai
cd genhealth-ai

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Download ML models
docker-compose exec api python backend/ml/models_store/download_models.py

# OR train from scratch (takes ~20 min)
docker-compose exec api python backend/ml/training/train_diabetes.py
```

### Access
- **Frontend:** Open `frontend/index.html` in browser
- **API Docs:** http://localhost:8000/docs
- **API ReDoc:** http://localhost:8000/redoc

## 📁 Project Structure
[include the full tree from Part 1]

## 🧬 ML Model Details
[explain each model, features used, accuracy metrics]

## 🔒 Privacy & Security
[explain encryption, consent model, audit logging]

## 🤝 Contributing
[standard contributing guide]

## 📄 License
MIT
```

---

## FINAL INTEGRATION: End-to-End Test Script

### tests/test_integration.py
```python
"""
Full end-to-end integration test covering the complete GenHealth AI flow.
"""

async def test_complete_user_journey():
    """
    1. Sign up new user (Aryan Sharma)
    2. Complete onboarding (profile + health vitals)
    3. Add family members (Father, Mother, Paternal Grandfather)
    4. Send invite to Father (mock email)
    5. Accept invite as Father (link accounts)
    6. Upload prescription image (use test_prescription.jpg)
    7. Poll until OCR complete
    8. Verify extracted entities
    9. Generate risk predictions
    10. Check risk profile: diabetes should be HIGH (family history)
    11. Get recommendations
    12. Grant doctor access
    13. Login as doctor
    14. Search patient
    15. Submit chief complaint "fatigue and weight gain"
    16. Verify relevant records returned (thyroid records should surface)
    17. Revoke doctor access
    18. Verify doctor can no longer access records
    19. Delete test user
    """

async def test_ocr_accuracy():
    """Test OCR on sample prescriptions, verify entity extraction accuracy > 85%."""

async def test_risk_model_consistency():
    """Verify risk models return consistent results for same input."""

async def test_family_invite_flow():
    """Full invite → accept → link → verify bidirectional data access."""
```

---

## DEPLOYMENT CHECKLIST

Create `DEPLOYMENT.md`:

```markdown
## Pre-Deployment Checklist

### Backend
- [ ] All environment variables set in production
- [ ] Database migrations run: `alembic upgrade head`
- [ ] ML models downloaded or trained: `python download_models.py`
- [ ] S3 bucket created with correct permissions
- [ ] SendGrid sender verified
- [ ] Redis maxmemory policy set to allkeys-lru
- [ ] HTTPS certificate configured
- [ ] CORS origin set to production frontend URL

### Frontend
- [ ] CONFIG.API_BASE updated to production URL
- [ ] PWA manifest icons generated
- [ ] All console.log removed (or gated behind DEBUG flag)

### Security
- [ ] SECRET_KEY is a random 256-bit value (never the example value)
- [ ] Database not exposed to public internet
- [ ] Rate limiting enabled
- [ ] Audit logging enabled
- [ ] Backup strategy configured for PostgreSQL

### Performance
- [ ] Celery workers scaled appropriately
- [ ] Redis connection pooling configured
- [ ] Database connection pooling configured (max_connections)
- [ ] S3 CloudFront CDN for prescription images
```

---

## SAMPLE DATA SEEDER

### backend/scripts/seed_demo_data.py
```python
"""
Seeds the database with realistic demo data for development/demo purposes.
Creates:
- 1 patient user: Aryan Sharma (aryan@example.com / demo123)
- 1 doctor user: Dr. Meera Iyer (dr.meera@example.com / demo123)  
- Family members: Father (Arjun, T2D, HTN), Mother (Priya, Hypothyroidism),
  Paternal Grandfather (Ram, T2D, Heart, deceased)
- 5 health records with extracted entities
- Risk predictions (diabetes: 62% high, thyroid: 48% moderate, etc.)
- 3 recommendations
- 1 active doctor access grant
Run: python backend/scripts/seed_demo_data.py
"""
```

Build all files completely. After building everything, output a summary of:
- All files created
- All API endpoints exposed
- How to run the full stack locally in one command
- Known limitations and next steps
```

---

## 📌 QUICK REFERENCE — WHAT EACH PART BUILDS

| Part | What's Built | Send When |
|---|---|---|
| **Part 1** | Full backend: FastAPI, PostgreSQL schema, all API routes, Docker setup | First |
| **Part 2** | ML/DL: OCR engine, NLP NER, risk prediction models (XGBoost+PyTorch), family graph | After Part 1 |
| **Part 3** | Frontend wiring: attach your index.html to real API, upload flow, family tree UI | After Part 2, attach index.html |
| **Part 4** | Doctor portal, notifications, audit log, privacy controls, consent flow | After Part 3 |
| **Part 5** | GitHub CI/CD, README, integration tests, deployment config, seed data | Last |
