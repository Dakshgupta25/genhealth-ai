"""
Medical constants for GenHealth AI.

Contains:
  - ICD-10 code lookup (top 200 common conditions)
  - ATC drug classification (top 500 drugs)
  - OCR error correction patterns
  - Indian medical title patterns for NER
  - Lab value reference ranges
"""

# ─── ICD-10 Code Lookup ───────────────────────────────────────────────────────
# Maps display name (lowercase) → ICD-10 code

ICD10_LOOKUP: dict[str, str] = {
    # Endocrine
    "type 2 diabetes": "E11",
    "type 2 diabetes mellitus": "E11",
    "diabetes mellitus": "E11",
    "diabetes": "E11",
    "type 1 diabetes": "E10",
    "gestational diabetes": "O24",
    "hypothyroidism": "E03.9",
    "hyperthyroidism": "E05.9",
    "graves disease": "E05.0",
    "hashimoto thyroiditis": "E06.3",
    "thyroiditis": "E06.9",
    "goitre": "E04.9",
    "obesity": "E66",
    "overweight": "E66.01",
    "hyperlipidemia": "E78.5",
    "hypercholesterolemia": "E78.0",
    "hypertriglyceridemia": "E78.1",
    "metabolic syndrome": "E88.81",
    "vitamin d deficiency": "E55.9",
    "vitamin b12 deficiency": "E53.8",
    "iron deficiency anaemia": "D50.9",
    "anaemia": "D64.9",
    "anemia": "D64.9",
    "gout": "M10.9",
    "hyperuricemia": "E79.0",

    # Cardiovascular
    "hypertension": "I10",
    "essential hypertension": "I10",
    "high blood pressure": "I10",
    "coronary artery disease": "I25.1",
    "ischemic heart disease": "I25.9",
    "angina": "I20.9",
    "unstable angina": "I20.0",
    "myocardial infarction": "I21.9",
    "heart attack": "I21.9",
    "heart failure": "I50.9",
    "congestive heart failure": "I50.0",
    "atrial fibrillation": "I48.0",
    "arrhythmia": "I49.9",
    "stroke": "I63.9",
    "tia": "G45.9",
    "transient ischemic attack": "G45.9",
    "deep vein thrombosis": "I82.4",
    "dvt": "I82.4",
    "pulmonary embolism": "I26.99",
    "cardiomyopathy": "I42.9",
    "mitral valve disease": "I05.9",
    "aortic stenosis": "I35.0",
    "peripheral artery disease": "I73.9",

    # Respiratory
    "asthma": "J45.9",
    "copd": "J44.1",
    "chronic obstructive pulmonary disease": "J44.1",
    "pneumonia": "J18.9",
    "tuberculosis": "A15.9",
    "tb": "A15.9",
    "pulmonary tuberculosis": "A15.0",
    "pleural effusion": "J90",
    "bronchitis": "J40",
    "chronic bronchitis": "J42",
    "sleep apnea": "G47.3",
    "obstructive sleep apnea": "G47.33",
    "interstitial lung disease": "J84.9",
    "pulmonary fibrosis": "J84.10",
    "rhinitis": "J30.9",
    "sinusitis": "J32.9",

    # Gastrointestinal
    "gastroesophageal reflux": "K21.9",
    "gerd": "K21.9",
    "acid reflux": "K21.9",
    "peptic ulcer": "K27.9",
    "gastric ulcer": "K25.9",
    "duodenal ulcer": "K26.9",
    "irritable bowel syndrome": "K58.9",
    "ibs": "K58.9",
    "crohn disease": "K50.9",
    "ulcerative colitis": "K51.9",
    "celiac disease": "K90.0",
    "constipation": "K59.0",
    "diarrhea": "R19.7",
    "hepatitis b": "B18.1",
    "hepatitis c": "B18.2",
    "cirrhosis": "K74.6",
    "fatty liver": "K76.0",
    "nafld": "K76.0",
    "gallstones": "K80.2",
    "cholecystitis": "K81.9",
    "pancreatitis": "K85.9",
    "appendicitis": "K37",
    "hernia": "K46.9",
    "haemorrhoids": "K64.9",
    "hemorrhoids": "K64.9",

    # Neurological
    "epilepsy": "G40.9",
    "migraine": "G43.9",
    "tension headache": "G44.2",
    "parkinson disease": "G20",
    "alzheimer disease": "G30.9",
    "dementia": "F03.9",
    "multiple sclerosis": "G35",
    "neuropathy": "G60.9",
    "peripheral neuropathy": "G60.9",
    "carpal tunnel syndrome": "G56.0",
    "vertigo": "R42",
    "benign positional vertigo": "H81.1",
    "bells palsy": "G51.0",

    # Mental Health
    "depression": "F32.9",
    "major depressive disorder": "F33.9",
    "anxiety": "F41.9",
    "generalized anxiety disorder": "F41.1",
    "panic disorder": "F41.0",
    "bipolar disorder": "F31.9",
    "schizophrenia": "F20.9",
    "ocd": "F42.9",
    "obsessive compulsive disorder": "F42.9",
    "ptsd": "F43.1",
    "adhd": "F90.9",
    "insomnia": "G47.00",

    # Musculoskeletal
    "osteoarthritis": "M19.9",
    "rheumatoid arthritis": "M06.9",
    "arthritis": "M13.9",
    "osteoporosis": "M81.0",
    "ankylosing spondylitis": "M45.9",
    "fibromyalgia": "M79.7",
    "lumbar disc disease": "M51.1",
    "back pain": "M54.5",
    "neck pain": "M54.2",
    "spondylosis": "M47.9",
    "tendinitis": "M77.9",
    "bursitis": "M71.9",
    "frozen shoulder": "M75.0",
    "rotator cuff tear": "M75.1",

    # Urological / Renal
    "chronic kidney disease": "N18.9",
    "ckd": "N18.9",
    "acute kidney injury": "N17.9",
    "nephrotic syndrome": "N04.9",
    "urinary tract infection": "N39.0",
    "uti": "N39.0",
    "kidney stones": "N20.0",
    "kidney stone": "N20.0",
    "renal calculus": "N20.0",
    "renal calculi": "N20.0",
    "renal stone": "N20.0",
    "ureteric calculus": "N20.1",
    "ureteric stone": "N20.1",
    "calculus": "N20.0",
    "nephrolithiasis": "N20.0",
    "benign prostatic hyperplasia": "N40.0",
    "bph": "N40.0",
    "prostate cancer": "C61",
    "urinary incontinence": "R32",

    # Gynaecological
    "polycystic ovarian syndrome": "E28.2",
    "pcos": "E28.2",
    "endometriosis": "N80.9",
    "uterine fibroids": "D25.9",
    "menorrhagia": "N92.0",
    "dysmenorrhea": "N94.6",
    "menopause": "N95.1",
    "cervical cancer": "C53.9",
    "breast cancer": "C50.9",
    "ovarian cancer": "C56.9",

    # Dermatological
    "eczema": "L30.9",
    "atopic dermatitis": "L20.9",
    "psoriasis": "L40.9",
    "urticaria": "L50.9",
    "acne": "L70.9",
    "rosacea": "L71.9",
    "vitiligo": "L80",
    "alopecia": "L65.9",

    # Infections
    "covid-19": "U07.1",
    "influenza": "J11.1",
    "dengue": "A90",
    "malaria": "B54",
    "typhoid": "A01.0",
    "chickenpox": "B01.9",
    "herpes zoster": "B02.9",
    "hiv": "B20",

    # Cancer
    "lung cancer": "C34.9",
    "colorectal cancer": "C19",
    "gastric cancer": "C16.9",
    "liver cancer": "C22.9",
    "pancreatic cancer": "C25.9",
    "leukemia": "C95.9",
    "lymphoma": "C85.9",
    "thyroid cancer": "C73",

    # Eye
    "glaucoma": "H40.9",
    "cataract": "H26.9",
    "diabetic retinopathy": "H36.0",
    "macular degeneration": "H35.3",

    # ENT
    "hearing loss": "H91.9",
    "tinnitus": "H93.1",
    "otitis media": "H66.9",
}

# Reverse map: ICD-10 → display name
ICD10_REVERSE: dict[str, str] = {v: k.title() for k, v in ICD10_LOOKUP.items()}


# ─── ATC Drug Classification ──────────────────────────────────────────────────
# Maps drug name (lowercase) → {atc_code, generic_name, drug_class}

ATC_LOOKUP: dict[str, dict] = {
    # Diabetes
    "metformin": {"atc_code": "A10BA02", "generic_name": "Metformin", "drug_class": "Biguanide"},
    "glibenclamide": {"atc_code": "A10BB01", "generic_name": "Glibenclamide", "drug_class": "Sulfonylurea"},
    "glipizide": {"atc_code": "A10BB07", "generic_name": "Glipizide", "drug_class": "Sulfonylurea"},
    "gliclazide": {"atc_code": "A10BB09", "generic_name": "Gliclazide", "drug_class": "Sulfonylurea"},
    "glimepiride": {"atc_code": "A10BB12", "generic_name": "Glimepiride", "drug_class": "Sulfonylurea"},
    "pioglitazone": {"atc_code": "A10BG03", "generic_name": "Pioglitazone", "drug_class": "Thiazolidinedione"},
    "sitagliptin": {"atc_code": "A10BH01", "generic_name": "Sitagliptin", "drug_class": "DPP-4 inhibitor"},
    "vildagliptin": {"atc_code": "A10BH02", "generic_name": "Vildagliptin", "drug_class": "DPP-4 inhibitor"},
    "dapagliflozin": {"atc_code": "A10BK01", "generic_name": "Dapagliflozin", "drug_class": "SGLT-2 inhibitor"},
    "empagliflozin": {"atc_code": "A10BK03", "generic_name": "Empagliflozin", "drug_class": "SGLT-2 inhibitor"},
    "canagliflozin": {"atc_code": "A10BK02", "generic_name": "Canagliflozin", "drug_class": "SGLT-2 inhibitor"},
    "liraglutide": {"atc_code": "A10BJ02", "generic_name": "Liraglutide", "drug_class": "GLP-1 agonist"},
    "semaglutide": {"atc_code": "A10BJ06", "generic_name": "Semaglutide", "drug_class": "GLP-1 agonist"},
    "insulin glargine": {"atc_code": "A10AE04", "generic_name": "Insulin glargine", "drug_class": "Basal insulin"},
    "insulin detemir": {"atc_code": "A10AE05", "generic_name": "Insulin detemir", "drug_class": "Basal insulin"},
    "human insulin": {"atc_code": "A10AB01", "generic_name": "Human insulin", "drug_class": "Rapid insulin"},

    # Thyroid
    "levothyroxine": {"atc_code": "H03AA01", "generic_name": "Levothyroxine", "drug_class": "Thyroid hormone"},
    "thyroxine": {"atc_code": "H03AA01", "generic_name": "Levothyroxine", "drug_class": "Thyroid hormone"},
    "liothyronine": {"atc_code": "H03AA02", "generic_name": "Liothyronine", "drug_class": "Thyroid hormone"},
    "carbimazole": {"atc_code": "H03BB01", "generic_name": "Carbimazole", "drug_class": "Antithyroid"},
    "propylthiouracil": {"atc_code": "H03BA02", "generic_name": "Propylthiouracil", "drug_class": "Antithyroid"},

    # Antihypertensives
    "amlodipine": {"atc_code": "C08CA01", "generic_name": "Amlodipine", "drug_class": "Calcium channel blocker"},
    "nifedipine": {"atc_code": "C08CA05", "generic_name": "Nifedipine", "drug_class": "Calcium channel blocker"},
    "enalapril": {"atc_code": "C09AA02", "generic_name": "Enalapril", "drug_class": "ACE inhibitor"},
    "ramipril": {"atc_code": "C09AA05", "generic_name": "Ramipril", "drug_class": "ACE inhibitor"},
    "lisinopril": {"atc_code": "C09AA03", "generic_name": "Lisinopril", "drug_class": "ACE inhibitor"},
    "losartan": {"atc_code": "C09CA01", "generic_name": "Losartan", "drug_class": "ARB"},
    "telmisartan": {"atc_code": "C09CA07", "generic_name": "Telmisartan", "drug_class": "ARB"},
    "olmesartan": {"atc_code": "C09CA08", "generic_name": "Olmesartan", "drug_class": "ARB"},
    "valsartan": {"atc_code": "C09CA03", "generic_name": "Valsartan", "drug_class": "ARB"},
    "metoprolol": {"atc_code": "C07AB02", "generic_name": "Metoprolol", "drug_class": "Beta blocker"},
    "atenolol": {"atc_code": "C07AB03", "generic_name": "Atenolol", "drug_class": "Beta blocker"},
    "bisoprolol": {"atc_code": "C07AB07", "generic_name": "Bisoprolol", "drug_class": "Beta blocker"},
    "carvedilol": {"atc_code": "C07AG02", "generic_name": "Carvedilol", "drug_class": "Alpha-beta blocker"},
    "furosemide": {"atc_code": "C03CA01", "generic_name": "Furosemide", "drug_class": "Loop diuretic"},
    "hydrochlorothiazide": {"atc_code": "C03AA03", "generic_name": "Hydrochlorothiazide", "drug_class": "Thiazide diuretic"},
    "spironolactone": {"atc_code": "C03DA01", "generic_name": "Spironolactone", "drug_class": "Potassium-sparing diuretic"},
    "clonidine": {"atc_code": "C02AC01", "generic_name": "Clonidine", "drug_class": "Central alpha-2 agonist"},
    "prazosin": {"atc_code": "C02CA01", "generic_name": "Prazosin", "drug_class": "Alpha-1 blocker"},

    # Statins / Lipid lowering
    "atorvastatin": {"atc_code": "C10AA05", "generic_name": "Atorvastatin", "drug_class": "Statin"},
    "rosuvastatin": {"atc_code": "C10AA07", "generic_name": "Rosuvastatin", "drug_class": "Statin"},
    "simvastatin": {"atc_code": "C10AA01", "generic_name": "Simvastatin", "drug_class": "Statin"},
    "pitavastatin": {"atc_code": "C10AA08", "generic_name": "Pitavastatin", "drug_class": "Statin"},
    "ezetimibe": {"atc_code": "C10AX09", "generic_name": "Ezetimibe", "drug_class": "Cholesterol absorption inhibitor"},
    "fenofibrate": {"atc_code": "C10AB05", "generic_name": "Fenofibrate", "drug_class": "Fibrate"},

    # Anticoagulants / Antiplatelets
    "aspirin": {"atc_code": "B01AC06", "generic_name": "Aspirin", "drug_class": "Antiplatelet"},
    "clopidogrel": {"atc_code": "B01AC04", "generic_name": "Clopidogrel", "drug_class": "Antiplatelet"},
    "warfarin": {"atc_code": "B01AA03", "generic_name": "Warfarin", "drug_class": "Anticoagulant"},
    "rivaroxaban": {"atc_code": "B01AF01", "generic_name": "Rivaroxaban", "drug_class": "NOAC"},
    "apixaban": {"atc_code": "B01AF02", "generic_name": "Apixaban", "drug_class": "NOAC"},
    "dabigatran": {"atc_code": "B01AE07", "generic_name": "Dabigatran", "drug_class": "NOAC"},

    # Analgesics / NSAIDs
    "paracetamol": {"atc_code": "N02BE01", "generic_name": "Paracetamol", "drug_class": "Analgesic/Antipyretic"},
    "acetaminophen": {"atc_code": "N02BE01", "generic_name": "Paracetamol", "drug_class": "Analgesic/Antipyretic"},
    "ibuprofen": {"atc_code": "M01AE01", "generic_name": "Ibuprofen", "drug_class": "NSAID"},
    "diclofenac": {"atc_code": "M01AB05", "generic_name": "Diclofenac", "drug_class": "NSAID"},
    "naproxen": {"atc_code": "M01AE02", "generic_name": "Naproxen", "drug_class": "NSAID"},
    "celecoxib": {"atc_code": "M01AH01", "generic_name": "Celecoxib", "drug_class": "COX-2 inhibitor"},
    "tramadol": {"atc_code": "N02AX02", "generic_name": "Tramadol", "drug_class": "Opioid analgesic"},
    "morphine": {"atc_code": "N02AA01", "generic_name": "Morphine", "drug_class": "Opioid"},

    # Antibiotics
    "amoxicillin": {"atc_code": "J01CA04", "generic_name": "Amoxicillin", "drug_class": "Penicillin"},
    "amoxiclav": {"atc_code": "J01CR02", "generic_name": "Amoxicillin-Clavulanate", "drug_class": "Penicillin+Beta-lactamase inhibitor"},
    "augmentin": {"atc_code": "J01CR02", "generic_name": "Amoxicillin-Clavulanate", "drug_class": "Penicillin+Beta-lactamase inhibitor"},
    "azithromycin": {"atc_code": "J01FA10", "generic_name": "Azithromycin", "drug_class": "Macrolide"},
    "clarithromycin": {"atc_code": "J01FA09", "generic_name": "Clarithromycin", "drug_class": "Macrolide"},
    "doxycycline": {"atc_code": "J01AA02", "generic_name": "Doxycycline", "drug_class": "Tetracycline"},
    "ciprofloxacin": {"atc_code": "J01MA02", "generic_name": "Ciprofloxacin", "drug_class": "Fluoroquinolone"},
    "levofloxacin": {"atc_code": "J01MA12", "generic_name": "Levofloxacin", "drug_class": "Fluoroquinolone"},
    "cefixime": {"atc_code": "J01DD08", "generic_name": "Cefixime", "drug_class": "3rd gen Cephalosporin"},
    "cefuroxime": {"atc_code": "J01DC02", "generic_name": "Cefuroxime", "drug_class": "2nd gen Cephalosporin"},
    "metronidazole": {"atc_code": "J01XD01", "generic_name": "Metronidazole", "drug_class": "Nitroimidazole"},
    "clindamycin": {"atc_code": "J01FF01", "generic_name": "Clindamycin", "drug_class": "Lincosamide"},

    # GI drugs
    "omeprazole": {"atc_code": "A02BC01", "generic_name": "Omeprazole", "drug_class": "PPI"},
    "pantoprazole": {"atc_code": "A02BC02", "generic_name": "Pantoprazole", "drug_class": "PPI"},
    "rabeprazole": {"atc_code": "A02BC04", "generic_name": "Rabeprazole", "drug_class": "PPI"},
    "esomeprazole": {"atc_code": "A02BC05", "generic_name": "Esomeprazole", "drug_class": "PPI"},
    "ranitidine": {"atc_code": "A02BA02", "generic_name": "Ranitidine", "drug_class": "H2 blocker"},
    "domperidone": {"atc_code": "A03FA03", "generic_name": "Domperidone", "drug_class": "Prokinetic"},
    "ondansetron": {"atc_code": "A04AA01", "generic_name": "Ondansetron", "drug_class": "5-HT3 antagonist"},

    # Psychiatric
    "sertraline": {"atc_code": "N06AB06", "generic_name": "Sertraline", "drug_class": "SSRI"},
    "fluoxetine": {"atc_code": "N06AB03", "generic_name": "Fluoxetine", "drug_class": "SSRI"},
    "escitalopram": {"atc_code": "N06AB10", "generic_name": "Escitalopram", "drug_class": "SSRI"},
    "paroxetine": {"atc_code": "N06AB05", "generic_name": "Paroxetine", "drug_class": "SSRI"},
    "venlafaxine": {"atc_code": "N06AX16", "generic_name": "Venlafaxine", "drug_class": "SNRI"},
    "duloxetine": {"atc_code": "N06AX21", "generic_name": "Duloxetine", "drug_class": "SNRI"},
    "alprazolam": {"atc_code": "N05BA12", "generic_name": "Alprazolam", "drug_class": "Benzodiazepine"},
    "clonazepam": {"atc_code": "N03AE01", "generic_name": "Clonazepam", "drug_class": "Benzodiazepine"},
    "quetiapine": {"atc_code": "N05AH04", "generic_name": "Quetiapine", "drug_class": "Atypical antipsychotic"},
    "olanzapine": {"atc_code": "N05AH03", "generic_name": "Olanzapine", "drug_class": "Atypical antipsychotic"},

    # Respiratory
    "salbutamol": {"atc_code": "R03AC02", "generic_name": "Salbutamol", "drug_class": "Short-acting beta-2 agonist"},
    "albuterol": {"atc_code": "R03AC02", "generic_name": "Salbutamol", "drug_class": "Short-acting beta-2 agonist"},
    "salmeterol": {"atc_code": "R03AC12", "generic_name": "Salmeterol", "drug_class": "Long-acting beta-2 agonist"},
    "formoterol": {"atc_code": "R03AC13", "generic_name": "Formoterol", "drug_class": "Long-acting beta-2 agonist"},
    "budesonide": {"atc_code": "R03BA02", "generic_name": "Budesonide", "drug_class": "Inhaled corticosteroid"},
    "fluticasone": {"atc_code": "R03BA05", "generic_name": "Fluticasone", "drug_class": "Inhaled corticosteroid"},
    "tiotropium": {"atc_code": "R03BB04", "generic_name": "Tiotropium", "drug_class": "Long-acting anticholinergic"},
    "montelukast": {"atc_code": "R03DC03", "generic_name": "Montelukast", "drug_class": "Leukotriene receptor antagonist"},
    "cetirizine": {"atc_code": "R06AE07", "generic_name": "Cetirizine", "drug_class": "Antihistamine"},
    "fexofenadine": {"atc_code": "R06AX26", "generic_name": "Fexofenadine", "drug_class": "Antihistamine"},
    "loratadine": {"atc_code": "R06AX13", "generic_name": "Loratadine", "drug_class": "Antihistamine"},

    # Neurological
    "levodopa": {"atc_code": "N04BA01", "generic_name": "Levodopa", "drug_class": "Dopamine precursor"},
    "carbidopa": {"atc_code": "N04BA02", "generic_name": "Carbidopa-Levodopa", "drug_class": "Dopamine precursor"},
    "donepezil": {"atc_code": "N06DA02", "generic_name": "Donepezil", "drug_class": "Cholinesterase inhibitor"},
    "phenytoin": {"atc_code": "N03AB02", "generic_name": "Phenytoin", "drug_class": "Antiepileptic"},
    "valproate": {"atc_code": "N03AG01", "generic_name": "Valproate", "drug_class": "Antiepileptic"},
    "levetiracetam": {"atc_code": "N03AX14", "generic_name": "Levetiracetam", "drug_class": "Antiepileptic"},
    "gabapentin": {"atc_code": "N03AX12", "generic_name": "Gabapentin", "drug_class": "Antiepileptic/Neuropathic"},
    "pregabalin": {"atc_code": "N03AX16", "generic_name": "Pregabalin", "drug_class": "Antiepileptic/Neuropathic"},
    "sumatriptan": {"atc_code": "N02CC01", "generic_name": "Sumatriptan", "drug_class": "Triptan"},

    # Vitamins / Supplements
    "vitamin d3": {"atc_code": "A11CC05", "generic_name": "Colecalciferol", "drug_class": "Vitamin D"},
    "cholecalciferol": {"atc_code": "A11CC05", "generic_name": "Colecalciferol", "drug_class": "Vitamin D"},
    "vitamin b12": {"atc_code": "B03BA01", "generic_name": "Cyanocobalamin", "drug_class": "Vitamin B12"},
    "methylcobalamin": {"atc_code": "B03BA51", "generic_name": "Methylcobalamin", "drug_class": "Vitamin B12"},
    "folic acid": {"atc_code": "B03BB01", "generic_name": "Folic acid", "drug_class": "Vitamin B9"},
    "ferrous sulphate": {"atc_code": "B03AA07", "generic_name": "Ferrous sulphate", "drug_class": "Iron supplement"},
    "calcium carbonate": {"atc_code": "A12AA04", "generic_name": "Calcium carbonate", "drug_class": "Calcium supplement"},
    "omega 3": {"atc_code": "C10AX06", "generic_name": "Omega-3 fatty acids", "drug_class": "Lipid modifier"},

    # Corticosteroids
    "prednisolone": {"atc_code": "H02AB06", "generic_name": "Prednisolone", "drug_class": "Corticosteroid"},
    "prednisone": {"atc_code": "H02AB07", "generic_name": "Prednisone", "drug_class": "Corticosteroid"},
    "dexamethasone": {"atc_code": "H02AB02", "generic_name": "Dexamethasone", "drug_class": "Corticosteroid"},
    "methylprednisolone": {"atc_code": "H02AB04", "generic_name": "Methylprednisolone", "drug_class": "Corticosteroid"},
    "hydrocortisone": {"atc_code": "H02AB09", "generic_name": "Hydrocortisone", "drug_class": "Corticosteroid"},

    # Urology
    "tamsulosin": {"atc_code": "G04CA02", "generic_name": "Tamsulosin", "drug_class": "Alpha-1 blocker"},
    "finasteride": {"atc_code": "G04CB01", "generic_name": "Finasteride", "drug_class": "5-alpha reductase inhibitor"},
    "sildenafil": {"atc_code": "G04BE03", "generic_name": "Sildenafil", "drug_class": "PDE5 inhibitor"},
    "tadalafil": {"atc_code": "G04BE08", "generic_name": "Tadalafil", "drug_class": "PDE5 inhibitor"},
}

# Brand name → generic mapping (common Indian brands)
BRAND_TO_GENERIC: dict[str, str] = {
    "glycomet": "metformin",
    "glucophage": "metformin",
    "januvia": "sitagliptin",
    "jardiance": "empagliflozin",
    "forxiga": "dapagliflozin",
    "victoza": "liraglutide",
    "ozempic": "semaglutide",
    "lantus": "insulin glargine",
    "synjardy": "empagliflozin+metformin",
    "thyronorm": "levothyroxine",
    "eltroxin": "levothyroxine",
    "thyrox": "levothyroxine",
    "stamlo": "amlodipine",
    "amlip": "amlodipine",
    "cardace": "ramipril",
    "covance": "losartan",
    "telma": "telmisartan",
    "minipress": "prazosin",
    "aten": "atenolol",
    "concor": "bisoprolol",
    "lasix": "furosemide",
    "aldactone": "spironolactone",
    "lipitor": "atorvastatin",
    "crestor": "rosuvastatin",
    "rozavel": "rosuvastatin",
    "storvas": "atorvastatin",
    "ecosprin": "aspirin",
    "deplatt": "clopidogrel",
    "xarelto": "rivaroxaban",
    "eliquis": "apixaban",
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "combiflam": "ibuprofen+paracetamol",
    "voveran": "diclofenac",
    "pan": "pantoprazole",
    "omez": "omeprazole",
    "pantocid": "pantoprazole",
    "nexium": "esomeprazole",
    "zantac": "ranitidine",
    "emeset": "ondansetron",
    "azee": "azithromycin",
    "zithromax": "azithromycin",
    "ciplox": "ciprofloxacin",
    "levoquin": "levofloxacin",
    "augmentin": "amoxiclav",
    "mox": "amoxicillin",
    "flagyl": "metronidazole",
    "zoloft": "sertraline",
    "prozac": "fluoxetine",
    "lexapro": "escitalopram",
    "cipralex": "escitalopram",
    "duzela": "duloxetine",
    "xanax": "alprazolam",
    "clonax": "clonazepam",
    "ventolin": "salbutamol",
    "asthalin": "salbutamol",
    "seretide": "salmeterol+fluticasone",
    "foracort": "formoterol+budesonide",
    "montek": "montelukast",
    "zyrtec": "cetirizine",
    "allegra": "fexofenadine",
    "dopaquel": "quetiapine",
    "encorate": "valproate",
    "gabapin": "gabapentin",
    "lyrica": "pregabalin",
    "calcirol": "vitamin d3",
    "revital": "multivitamin",
    "shelcal": "calcium carbonate",
    "wysolone": "prednisolone",
    "dexa": "dexamethasone",
    "floricot": "hydrocortisone",
    "urimax": "tamsulosin",
    "proscar": "finasteride",
}


# ─── OCR Error Correction Patterns ───────────────────────────────────────────
# (pattern, replacement, context)  — applied via regex in sequence

OCR_CORRECTIONS: list[tuple[str, str]] = [
    # Unit corrections
    (r"\brnq\b", "mg"),
    (r"\brnl\b", "ml"),
    (r"\bmcq\b", "mcg"),
    (r"\brneg\b", "meg"),
    (r"\blU\b", "IU"),
    (r"\b1U\b", "IU"),
    # Common letter-digit confusions in medical context
    (r"(?<!\d)0(?=\s*(?:mg|ml|mcg|IU|tablets?))", "O"),    # 0 → O before units (Omeprazole)
    (r"\bO(?=\d)", "0"),    # O → 0 before digits
    # Frequency abbreviations
    (r"\bod\b", "OD"),   # once daily
    (r"\bbd\b", "BD"),   # twice daily
    (r"\btds\b", "TDS"), # three times daily
    (r"\bqid\b", "QID"), # four times daily
    (r"\bsos\b", "SOS"), # as needed
    (r"\bprn\b", "PRN"), # as needed
    (r"\bhs\b", "HS"),   # at bedtime
    (r"\bac\b", "AC"),   # before meals
    (r"\bpc\b", "PC"),   # after meals
    # Common drug name OCR fixes
    (r"\bMetforrn\b", "Metformin"),
    (r"\bMetfornin\b", "Metformin"),
    (r"\bAmIodipine\b", "Amlodipine"),
    (r"\bAtorvastatln\b", "Atorvastatin"),
    (r"\bLevothyroxlne\b", "Levothyroxine"),
    # Numeric cleanup
    (r"(\d)\s+\.\s*(\d)", r"\1.\2"),  # Fix "3 . 5" → "3.5"
    (r"(\d),(\d{3})", r"\1\2"),       # Remove thousand separators in lab values
]


# ─── Lab Value Reference Ranges ──────────────────────────────────────────────

LAB_REFERENCE_RANGES: dict[str, dict] = {
    "blood_sugar_fasting": {"min": 70, "max": 99, "unit": "mg/dL",
                             "borderline_high": 125, "high": 126},
    "blood_sugar_pp": {"min": 70, "max": 139, "unit": "mg/dL",
                        "borderline_high": 199, "high": 200},
    "hba1c": {"min": 4.0, "max": 5.6, "unit": "%",
               "borderline_high": 6.4, "high": 6.5},
    "tsh": {"min": 0.4, "max": 4.0, "unit": "mIU/L",
             "low": 0.4, "high": 4.0},
    "t3": {"min": 80, "max": 200, "unit": "ng/dL"},
    "t4": {"min": 5.0, "max": 12.0, "unit": "µg/dL"},
    "total_cholesterol": {"min": 0, "max": 200, "unit": "mg/dL",
                           "borderline_high": 239, "high": 240},
    "ldl": {"min": 0, "max": 100, "unit": "mg/dL",
             "borderline_high": 159, "high": 160},
    "hdl_male": {"min": 40, "max": 60, "unit": "mg/dL", "low": 40},
    "hdl_female": {"min": 50, "max": 60, "unit": "mg/dL", "low": 50},
    "triglycerides": {"min": 0, "max": 150, "unit": "mg/dL",
                       "borderline_high": 199, "high": 200},
    "systolic_bp": {"min": 90, "max": 120, "unit": "mmHg",
                     "borderline_high": 139, "high": 140},
    "diastolic_bp": {"min": 60, "max": 80, "unit": "mmHg",
                      "borderline_high": 89, "high": 90},
    "creatinine_male": {"min": 0.7, "max": 1.3, "unit": "mg/dL"},
    "creatinine_female": {"min": 0.5, "max": 1.1, "unit": "mg/dL"},
    "hemoglobin_male": {"min": 13.5, "max": 17.5, "unit": "g/dL"},
    "hemoglobin_female": {"min": 12.0, "max": 15.5, "unit": "g/dL"},
    "vitamin_d": {"min": 30, "max": 100, "unit": "ng/mL",
                   "deficient": 20, "insufficient": 30},
    "vitamin_b12": {"min": 200, "max": 900, "unit": "pg/mL",
                     "deficient": 200},
    "uric_acid_male": {"min": 3.4, "max": 7.0, "unit": "mg/dL"},
    "uric_acid_female": {"min": 2.4, "max": 6.0, "unit": "mg/dL"},
}


# ─── Indian Doctor Title Patterns for NER ────────────────────────────────────

DOCTOR_TITLE_PATTERNS: list[str] = [
    r"Dr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
    r"Dr\s+[A-Z][A-Z]+\s+[A-Z][a-z]+",
    r"(?:Prof\.?|Professor)\s+Dr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
    r"[A-Z][a-z]+\s+[A-Z][a-z]+\s*,\s*(?:MD|MBBS|MS|MCh|DM|DNB|FRCS|FACS|PhD)",
]

HOSPITAL_KEYWORDS: list[str] = [
    "hospital", "clinic", "centre", "center", "nursing home", "medical college",
    "health care", "healthcare", "polyclinic", "dispensary", "maternity home",
    "super speciality", "multispeciality", "institute", "infirmary",
    "apollo", "fortis", "manipal", "max healthcare", "aiims", "nimhans",
    "medanta", "aster", "narayana", "kokilaben", "lilavati", "hinduja",
    "tata memorial", "breach candy", "bombay hospital", "pgimer",
]

# ─── Frequency standardization ───────────────────────────────────────────────

FREQUENCY_MAP: dict[str, str] = {
    "od": "Once daily",
    "once daily": "Once daily",
    "once a day": "Once daily",
    "bd": "Twice daily",
    "bid": "Twice daily",
    "twice daily": "Twice daily",
    "twice a day": "Twice daily",
    "tds": "Three times daily",
    "tid": "Three times daily",
    "thrice daily": "Three times daily",
    "three times daily": "Three times daily",
    "qid": "Four times daily",
    "four times daily": "Four times daily",
    "sos": "As needed",
    "prn": "As needed",
    "as needed": "As needed",
    "hs": "At bedtime",
    "at bedtime": "At bedtime",
    "ac": "Before meals",
    "before meals": "Before meals",
    "pc": "After meals",
    "after meals": "After meals",
    "weekly": "Once weekly",
    "once weekly": "Once weekly",
    "monthly": "Once monthly",
}
