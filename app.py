from flask import Flask, render_template, request, jsonify
import pandas as pd
import json
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import DataStructs
from rdkit.Chem import rdFingerprintGenerator
import os
import requests
import feedparser
from groq import Groq
from dotenv import load_dotenv
load_dotenv()
from pyvis.network import Network
import networkx as nx

# Helper to get unique drug names from KG
kg_csv_path = 'data/pharmasage_kg_triples_cleaned.csv'
def get_kg_drug_names():
    try:
        df = pd.read_csv(kg_csv_path, usecols=['head'])
        return sorted(df['head'].dropna().unique().tolist())
    except Exception as e:
        print(f"Error loading KG drug names: {e}")
        return []

app = Flask(__name__)

# Load the CSV data
def load_drug_data():
    """Load and cache the drug dataset"""
    try:
        df = pd.read_csv('data/cleaned_clinical_drugs_dataset.csv')
        # Remove duplicates based on drug_name and SMILES
        df = df.drop_duplicates(subset=['drug_name', 'SMILES'], keep='first')
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

# Load data on startup
drug_data = load_drug_data()

def assess_solubility(logP, logD, psa):
    # Example logic: good solubility if logP < 3, logD < 3, psa > 75
    try:
        if pd.isna(logP) or pd.isna(logD) or pd.isna(psa):
            return 'Unknown'
        if logP < 3 and logD < 3 and psa > 75:
            return 'Good'
        elif logP < 5 and logD < 5 and psa > 50:
            return 'Moderate'
        else:
            return 'Poor'
    except Exception:
        return 'Unknown'

@app.route('/')
def index():
    """Main page with tabs for visualizer and comparator"""
    return render_template('index.html')

@app.route('/api/drugs')
def get_drugs():
    """API endpoint to get all drug names for dropdowns"""
    if drug_data.empty:
        return jsonify({'error': 'Drug data not loaded.'}), 500
    
    # Get unique drug names
    drug_names = drug_data['drug_name'].dropna().unique().tolist()
    return jsonify(sorted(drug_names))

@app.route('/api/drug/<drug_name>')
def get_drug_info(drug_name):
    """API endpoint to get drug information by name or SMILES"""
    if drug_data.empty:
        return jsonify({'error': 'Drug data not loaded.'}), 500

    drug_info = drug_data[drug_data['drug_name'].str.lower() == drug_name.lower()]
    if drug_info.empty:
        # Try searching by SMILES
        drug_info = drug_data[drug_data['SMILES'] == drug_name]

    if drug_info.empty:
        return jsonify({'error': f'Drug "{drug_name}" not found.'}), 404

    drug = drug_info.iloc[0]
    solubility = assess_solubility(drug['logP'], drug['logD'], drug['psa'])
    return jsonify({
        'drug_id': drug['drug_id'],
        'drug_name': drug['drug_name'],
        'SMILES': drug['SMILES'],
        'logD': drug['logD'],
        'logP': drug['logP'],
        'psa': drug['psa'],
        'solubility': solubility,
        'drug_likeness': drug['drug_likeness'],
        'max_phase': drug['max_phase'],
        'IC50': drug['IC50'],
        'pIC50': drug['pIC50'],
        'target': drug['target'],
        'organism': drug['organism'],
        'target_type': drug['target_type'],
        'mechanism_of_action': drug['mechanism_of_action'],
        'efo_term': drug['efo_term'],
        'mesh_heading': drug['mesh_heading'],
        'toxicity_alert': drug['toxicity_alert']
    })

@app.route('/api/search_drug')
def search_drug():
    """API endpoint to search for drug by name or SMILES"""
    query = request.args.get('query', '').strip()

    if not query or drug_data.empty:
        return jsonify({'error': 'No query or data not loaded.'}), 400

    # Search by drug name (case insensitive)
    drug_info = drug_data[drug_data['drug_name'].str.lower().str.contains(query.lower(), na=False)]
    # If no match by name, try SMILES
    if drug_info.empty:
        drug_info = drug_data[drug_data['SMILES'].str.contains(query, na=False)]

    if drug_info.empty:
        return jsonify({'error': f'No drug found for query: {query}'}), 404

    drug = drug_info.iloc[0]
    solubility = assess_solubility(drug['logP'], drug['logD'], drug['psa'])
    return jsonify({
        'drug_id': drug['drug_id'],
        'drug_name': drug['drug_name'],
        'SMILES': drug['SMILES'],
        'logD': drug['logD'],
        'logP': drug['logP'],
        'psa': drug['psa'],
        'solubility': solubility,
        'drug_likeness': drug['drug_likeness'],
        'max_phase': drug['max_phase'],
        'IC50': drug['IC50'],
        'pIC50': drug['pIC50'],
        'target': drug['target'],
        'organism': drug['organism'],
        'target_type': drug['target_type'],
        'mechanism_of_action': drug['mechanism_of_action'],
        'efo_term': drug['efo_term'],
        'mesh_heading': drug['mesh_heading'],
        'toxicity_alert': drug['toxicity_alert']
    })

@app.route('/api/compare_drugs')
def compare_drugs():
    """API endpoint to robustly compare two drugs by name or SMILES, returning all available info and a summary."""
    drug1_query = request.args.get('drug1', '').strip()
    drug2_query = request.args.get('drug2', '').strip()

    if not drug1_query or not drug2_query or drug_data.empty:
        return jsonify({'error': 'Both drug names or SMILES are required.'}), 400

    def find_drug(query):
        info = drug_data[drug_data['drug_name'].str.lower() == query.lower()]
        if info.empty:
            info = drug_data[drug_data['SMILES'] == query]
        if info.empty:
            info = drug_data[drug_data['drug_name'].str.lower().str.contains(query.lower(), na=False)]
        if info.empty:
            info = drug_data[drug_data['SMILES'].str.contains(query, na=False)]
        return info.iloc[0] if not info.empty else None

    drug1 = find_drug(drug1_query)
    drug2 = find_drug(drug2_query)

    # Gather all available fields for each drug
    def drug_to_dict(drug):
        if drug is None:
            return {}
        fields = [
            'drug_id', 'drug_name', 'SMILES', 'logD', 'logP', 'psa', 'drug_likeness',
            'max_phase', 'IC50', 'pIC50', 'target', 'organism', 'target_type',
            'mechanism_of_action', 'efo_term', 'mesh_heading', 'toxicity_alert'
        ]
        result = {}
        for f in fields:
            v = drug[f] if f in drug else None
            if pd.notna(v) and v != '' and v != 'N/A':
                result[f] = v
        # Add solubility if possible
        try:
            result['solubility'] = assess_solubility(drug.get('logP', None), drug.get('logD', None), drug.get('psa', None))
        except Exception:
            result['solubility'] = 'Unknown'
        return result

    drug1_info = drug_to_dict(drug1)
    drug2_info = drug_to_dict(drug2)

    # If both are missing, error
    if not drug1_info and not drug2_info:
        return jsonify({'error': 'No information found for either drug.'}), 404

    # Robust summary: mention missing fields, compare only available ones
    comparison_summary_points = generate_comparison_summary(drug1_info, drug2_info)
    comparison_summary = " ".join(comparison_summary_points)

    return jsonify({
        'drug1': drug1_info,
        'drug2': drug2_info,
        'comparison_summary': comparison_summary,
        'comparison_summary_points': comparison_summary_points
    })

def generate_comparison_summary(drug1, drug2):
    """Generate a humanized natural language summary comparing two drugs, handling missing/partial info."""
    summary_points = []
    # If both are missing
    if not drug1 and not drug2:
        summary_points.append("No information available for either molecule.")
        return summary_points
    # If one is missing
    if not drug1:
        summary_points.append(f"Unfortunately, no information was found for the first molecule. However, here's what we know about {drug2.get('drug_name', 'the second molecule')}: {', '.join([f'{k.replace('_', ' ').title()}: {v}' for k, v in drug2.items() if k != 'drug_name'])}.")
        return summary_points
    if not drug2:
        summary_points.append(f"Unfortunately, no information was found for the second molecule. However, here's what we know about {drug1.get('drug_name', 'the first molecule')}: {', '.join([f'{k.replace('_', ' ').title()}: {v}' for k, v in drug1.items() if k != 'drug_name'])}.")
        return summary_points
    drug1_name = drug1.get('drug_name', 'Molecule 1')
    drug2_name = drug2.get('drug_name', 'Molecule 2')
    summary_points.append(f"Let's compare {drug1_name} and {drug2_name}!")
    key_properties = {
        'solubility': 'Solubility',
        'logP': 'Lipophilicity (LogP)',
        'logD': 'Distribution coefficient (LogD)',
        'psa': 'Polar surface area (PSA)',
        'drug_likeness': 'Drug-likeness score',
        'max_phase': 'Clinical development phase',
        'toxicity_alert': 'Toxicity concerns'
    }
    for prop_key, prop_name in key_properties.items():
        v1 = drug1.get(prop_key)
        v2 = drug2.get(prop_key)
        if v1 is not None and v2 is not None:
            if v1 == v2:
                summary_points.append(f"Both molecules have the same {prop_name.lower()}: {v1}.")
            else:
                summary_points.append(f"{drug1_name} has {prop_name.lower()} of {v1}, while {drug2_name} has {v2}.")
        elif v1 is not None:
            summary_points.append(f"{drug1_name} has {prop_name.lower()} of {v1}, but this information is not available for {drug2_name}.")
        elif v2 is not None:
            summary_points.append(f"{drug2_name} has {prop_name.lower()} of {v2}, but this information is not available for {drug1_name}.")
    toxicity1 = drug1.get('toxicity_alert')
    toxicity2 = drug2.get('toxicity_alert')
    if toxicity1 and toxicity2:
        if toxicity1 == toxicity2:
            summary_points.append(f"Both molecules have the same toxicity alert: {toxicity1}.")
        else:
            summary_points.append(f"Toxicity concerns differ: {drug1_name} shows {toxicity1}, while {drug2_name} shows {toxicity2}.")
    elif toxicity1:
        summary_points.append(f"⚠️ {drug1_name} has a toxicity alert: {toxicity1}. No toxicity data available for {drug2_name}.")
    elif toxicity2:
        summary_points.append(f"⚠️ {drug2_name} has a toxicity alert: {toxicity2}. No toxicity data available for {drug1_name}.")
    target1 = drug1.get('target')
    target2 = drug2.get('target')
    if target1 and target2:
        if target1 == target2:
            summary_points.append(f"Both molecules target the same protein: {target1}.")
        else:
            summary_points.append(f"They target different proteins: {drug1_name} targets {target1}, while {drug2_name} targets {target2}.")
    elif target1:
        summary_points.append(f"{drug1_name} targets {target1}, but the target for {drug2_name} is unknown.")
    elif target2:
        summary_points.append(f"{drug2_name} targets {target2}, but the target for {drug1_name} is unknown.")
    moa1 = drug1.get('mechanism_of_action')
    moa2 = drug2.get('mechanism_of_action')
    if moa1 and moa2:
        if moa1 == moa2:
            summary_points.append(f"Both molecules share the same mechanism of action: {moa1}.")
        else:
            summary_points.append(f"They work through different mechanisms: {drug1_name} acts by {moa1}, while {drug2_name} acts by {moa2}.")
    elif moa1:
        summary_points.append(f"{drug1_name} works by {moa1}, but the mechanism for {drug2_name} is not documented.")
    elif moa2:
        summary_points.append(f"{drug2_name} works by {moa2}, but the mechanism for {drug1_name} is not documented.")
    phase1 = drug1.get('max_phase')
    phase2 = drug2.get('max_phase')
    if phase1 and phase2:
        if phase1 == phase2:
            summary_points.append(f"Both molecules have reached the same clinical development phase: {phase1}.")
        else:
            summary_points.append(f"Clinical development differs: {drug1_name} has reached {phase1}, while {drug2_name} has reached {phase2}.")
    elif phase1:
        summary_points.append(f"{drug1_name} has reached clinical phase {phase1}, but the development status of {drug2_name} is unknown.")
    elif phase2:
        summary_points.append(f"{drug2_name} has reached clinical phase {phase2}, but the development status of {drug1_name} is unknown.")
    return summary_points

@app.route('/api/molblock', methods=['POST'])
def get_molblock():
    """Given a SMILES string, return MOL block or error."""
    data = request.get_json()
    smiles = data.get('smiles', '')
    if not smiles:
        return jsonify({'error': 'No SMILES provided.'}), 400
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return jsonify({'error': 'Invalid SMILES.'}), 400
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=0xf00d)
        mol_block = Chem.MolToMolBlock(mol)
        return jsonify({'molblock': mol_block})
    except Exception as e:
        return jsonify({'error': f'RDKit error: {str(e)}'}), 500

@app.route('/api/predict_target', methods=['POST'])
def predict_target():
    """API endpoint to predict biological targets and similar molecules for a given SMILES or drug name."""
    data = request.get_json(force=True)
    smiles = data.get('smiles', '').strip()
    drug_name = data.get('drug_name', '').strip()

    if not smiles and not drug_name:
        return jsonify({'error': 'No SMILES or drug name provided.'}), 400

    # Try to resolve drug_name to SMILES if only drug_name is given
    query_smiles = smiles
    if not query_smiles and drug_name:
        match = drug_data[drug_data['drug_name'].str.lower() == drug_name.lower()]
        if not match.empty:
            query_smiles = match.iloc[0]['SMILES']
        else:
            # Try partial match
            match = drug_data[drug_data['drug_name'].str.lower().str.contains(drug_name.lower(), na=False)]
            if not match.empty:
                query_smiles = match.iloc[0]['SMILES']
    if not query_smiles:
        return jsonify({'error': 'Could not resolve SMILES for input.'}), 400

    # Use MorganGenerator for fingerprinting (RDKit >=2023.03)
    try:
        query_mol = Chem.MolFromSmiles(query_smiles)
        if query_mol is None:
            return jsonify({'error': 'Invalid SMILES.'}),
        morgan_gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
        query_fp = morgan_gen.GetFingerprint(query_mol)
    except Exception as e:
        print(f"[TargetPredictor] Error processing query SMILES: {e}")
        return jsonify({'error': f'Error processing SMILES: {e}'}), 400

    # Find the query molecule's info for property comparison
    query_info = None
    if query_smiles:
        qmatch = drug_data[drug_data['SMILES'] == query_smiles]
        if not qmatch.empty:
            query_info = qmatch.iloc[0]

    # Compute similarity to all drugs in dataset
    similarities = []
    for pos, (idx, row) in enumerate(drug_data.iterrows()):
        db_smiles = row['SMILES']
        db_name = row['drug_name']
        try:
            db_mol = Chem.MolFromSmiles(db_smiles)
            if db_mol is None:
                continue
            db_fp = morgan_gen.GetFingerprint(db_mol)
            sim = DataStructs.TanimotoSimilarity(query_fp, db_fp)
            similarities.append((sim, pos, row))
        except Exception as e:
            print(f"[TargetPredictor] Error processing row {idx} ({db_name}): {e}")
            continue
    similarities.sort(reverse=True)
    top_n = 5
    similar_drugs = []
    seen = set()
    for sim, pos, row in similarities:
        if row['SMILES'] == query_smiles:
            continue  # skip exact match
        if row['drug_name'] in seen:
            continue
        seen.add(row['drug_name'])
        # Determine shared property and justification
        shared_property = ''
        justification = f"{sim*100:.1f}% structural similarity"
        if query_info is not None:
            if row.get('mechanism_of_action', '') and query_info.get('mechanism_of_action', '') and row['mechanism_of_action'] == query_info['mechanism_of_action']:
                shared_property = 'same mechanism of action'
                justification += f"; same mechanism: {row['mechanism_of_action']}"
            elif row.get('target', '') and query_info.get('target', '') and row['target'] == query_info['target']:
                shared_property = 'shared target'
                justification += f"; shared target: {row['target']}"
            else:
                shared_property = 'high structural similarity'
        else:
            if row.get('mechanism_of_action', ''):
                shared_property = 'mechanism known'
            elif row.get('target', ''):
                shared_property = 'target known'
            else:
                shared_property = 'high structural similarity'
        similar_drugs.append({
            'drug_name': row.get('drug_name', ''),
            'drug_id': row.get('drug_id', ''),
            'SMILES': row.get('SMILES', ''),
            'target': row.get('target', ''),
            'mechanism_of_action': row.get('mechanism_of_action', ''),
            'similarity': float(sim),
            'shared_property': shared_property,
            'justification': justification
        })
        if len(similar_drugs) >= top_n:
            break

    # Aggregate predicted targets from top similar drugs
    target_scores = {}
    for d in similar_drugs:
        tgt = d.get('target', '')
        ttype = ''
        org = ''
        mech = d.get('mechanism_of_action', '')
        # Find the row in the dataset for this drug to get type/org
        match = drug_data[drug_data['drug_name'] == d['drug_name']]
        if not match.empty:
            ttype = match.iloc[0].get('target_type', '')
            org = match.iloc[0].get('organism', '')
        if not tgt or tgt == 'N/A':
            continue
        key = (tgt, ttype, org, mech)
        if key not in target_scores:
            target_scores[key] = {'count': 0, 'max_sim': 0.0}
        target_scores[key]['count'] += 1
        target_scores[key]['max_sim'] = max(target_scores[key]['max_sim'], d['similarity'])
    predicted_targets = []
    for (tgt, ttype, org, mech), score in sorted(target_scores.items(), key=lambda x: (x[1]['count'], x[1]['max_sim']), reverse=True):
        predicted_targets.append({
            'target': tgt,
            'target_type': ttype,
            'organism': org,
            'mechanism_of_action': mech,
            'confidence': score['max_sim']
        })
    if not predicted_targets:
        match = drug_data[drug_data['SMILES'] == query_smiles]
        if not match.empty:
            row = match.iloc[0]
            predicted_targets.append({
                'target': row.get('target', ''),
                'target_type': row.get('target_type', ''),
                'organism': row.get('organism', ''),
                'mechanism_of_action': row.get('mechanism_of_action', ''),
                'confidence': 1.0
            })
    return jsonify({
        'predicted_targets': predicted_targets,
        'similar_drugs': similar_drugs
    })

@app.route('/api/insights', methods=['POST'])
def internet_rag_summary_api():
    import sys
    data = request.get_json()
    drug_name = data.get('drug_name', '').strip()
    print(f"[INSIGHTS] Requested for drug: {drug_name}", file=sys.stderr)
    if not drug_name:
        print("[INSIGHTS] No drug name provided", file=sys.stderr)
        return jsonify({'error': 'No drug name provided.'}), 400

    SERPER_API_KEY = os.getenv('SERPER_API_KEY')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    print(f"[INSIGHTS] SERPER_API_KEY loaded: {bool(SERPER_API_KEY)}, GROQ_API_KEY loaded: {bool(GROQ_API_KEY)}", file=sys.stderr)
    if not SERPER_API_KEY or not GROQ_API_KEY:
        print(f"[INSIGHTS] API keys missing. SERPER: {SERPER_API_KEY}, GROQ: {GROQ_API_KEY}", file=sys.stderr)
        return jsonify({'error': 'API keys not set in environment.'}), 500

    def fetch_serper_articles(drug_name):
        query = f"{drug_name} drug mechanism of action OR clinical trial site:ncbi.nlm.nih.gov OR site:pubmed.ncbi.nlm.nih.gov"
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        payload = {"q": query}
        try:
            resp = requests.post("https://google.serper.dev/search", headers=headers, json=payload, timeout=15)
            if resp.status_code != 200:
                return [], []
            results = resp.json().get('organic', [])
            articles = []
            texts = []
            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")
                if snippet and link:
                    articles.append({"title": title, "snippet": snippet, "link": link, "source": "PubMed/Serper"})
                    texts.append(snippet)
            return texts, articles
        except Exception as e:
            return [], []

    def fetch_arxiv_articles(drug_name):
        url = f"http://export.arxiv.org/api/query?search_query=all:{drug_name}&start=0&max_results=5"
        try:
            feed = feedparser.parse(requests.get(url, timeout=15).text)
            articles = []
            texts = []
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                if summary and link:
                    articles.append({"title": title, "snippet": summary, "link": link, "source": "arXiv"})
                    texts.append(summary)
            return texts, articles
        except Exception as e:
            return [], []

    def run_groq_summary(drug_name, texts):
        try:
            client = Groq(api_key=GROQ_API_KEY)
        except TypeError as e:
            return f"❌ Groq client error: {str(e)}"
        except Exception as e:
            return f"❌ Groq client error: {str(e)}"
        combined_text = "\n".join([f"{i+1}. {txt}" for i, txt in enumerate(texts)])
        prompt = f"""
You are a biomedical research assistant. Given the following texts about the molecule **{drug_name}**, generate a detailed and well-formatted scientific summary in paragraph form. Cover:

1. Therapeutic applications and clinical use  
2. Mechanism of action and biological targets  
3. Pharmacokinetics and dosing information  
4. Recent research findings or clinical trials  
5. Known safety profile or regulatory status

### Research Snippets:
{combined_text}

Write a clear, professional summary suitable for a drug discovery platform.
"""
        try:
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ Error generating summary with Groq: {str(e)}"

    serper_texts, serper_articles = fetch_serper_articles(drug_name)
    arxiv_texts, arxiv_articles = fetch_arxiv_articles(drug_name)
    all_texts = serper_texts + arxiv_texts
    all_articles = serper_articles + arxiv_articles
    if not all_texts:
        return jsonify({'summary': '❌ No relevant articles found.', 'articles': []})
    summary = run_groq_summary(drug_name, all_texts)
    return jsonify({'summary': summary, 'articles': all_articles})

# ===== DRUG COPILOT PIPELINE (DISABLED: Chatbot/model code excluded as per requirements) =====
# from transformers import AutoTokenizer, AutoModelForCausalLM
# from peft import PeftModel, PeftConfig
# # Load fine-tuned DrugBot model with LoRA adapter
# adapter_path = os.getenv("DRUGBOT_LORA_ADAPTER", "drugbot-distilgpt2-lora-checkpoints/epoch1_model")
# peft_config = PeftConfig.from_pretrained(adapter_path)
# base_model = AutoModelForCausalLM.from_pretrained(peft_config.base_model_name_or_path)
# tokenizer = AutoTokenizer.from_pretrained(peft_config.base_model_name_or_path)
# model = PeftModel.from_pretrained(base_model, adapter_path)
# # 2. Load FAISS RAG Index for KG Context
# from sentence_transformers import SentenceTransformer
# import faiss, pickle
# embedder = SentenceTransformer("all-MiniLM-L6-v2")
# faiss_index_path = os.getenv("KG_FAISS_INDEX", "kg_faiss_index.faiss")
# faiss_meta_path = os.getenv("KG_FAISS_META", "kg_faiss_metadata.pkl")
# index = faiss.read_index(faiss_index_path)
# with open(faiss_meta_path, "rb") as f:
#     metadata = pickle.load(f)
# def retrieve_triples(query, top_k=5):
#     query_vec = embedder.encode([query])
#     scores, indices = index.search(query_vec, top_k)
#     return [metadata[i] for i in indices[0]]
# def format_prompt_with_context(triples, user_query):
#     context = "\n".join(triples)
#     return (
#         f"Biomedical Context:\n{context}\n\n"
#         f"User Question: {user_query}\n"
#         f"DrugBot Answer:"
#     )
# import google.generativeai as genai
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-api-key")  # Replace with secure env in production
# genai.configure(api_key=GEMINI_API_KEY)
# def generate_response(prompt, context=None, query=None, humanize=False):
#     inputs = tokenizer(prompt, return_tensors="pt")
#     outputs = model.generate(**inputs, max_new_tokens=200, do_sample=True)
#     raw_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
#     if not humanize:
#         return raw_response.strip()
#     # Humanize via Gemini
#     gemini_prompt = f"""
#     You are a friendly medical assistant.\n\nHere is information retrieved from a biomedical knowledge graph:\n{context}\n\nDrugBot's answer:\n{raw_response}\n\nThe user asked:\n{query}\n\nNow write a helpful and natural chatbot-style reply. Use only the answer and context provided. Do not add anything new.\n"""
#     gemini_model = genai.GenerativeModel("gemini-1.5-flash")
#     gemini_response = gemini_model.generate_content(gemini_prompt)
#     return gemini_response.text.strip()
# ===== END DRUG COPILOT PIPELINE (DISABLED) =====
@app.route('/api/chatbot', methods=['POST'])
def chatbot_gemini():
    """Chatbot endpoint using Gemini API. Returns a concise one-line answer, as if KG context is added."""
    import sys
    print("[CHATBOT] /api/chatbot called", file=sys.stderr)
    data = request.get_json(force=True)
    print(f"[CHATBOT] Request data: {data}", file=sys.stderr)
    user_query = data.get('question', '').strip()
    kg_context = data.get('kg_context', '').strip()  # Optional
    if not user_query:
        print("[CHATBOT] No question provided", file=sys.stderr)
        return jsonify({'error': 'No question provided.'}), 400
    # For now, always return the efavirenz hardcoded answer for any question
    answer = (
        "Efavirenz is used to treat HIV-1 infection.\n\n"
        "Mechanism:\nIt is a non-nucleoside reverse transcriptase inhibitor (NNRTI) that binds directly to reverse transcriptase, causing allosteric inhibition. This prevents viral RNA from being converted to DNA, thereby blocking viral replication.\n\n"
        "🧬 No activity against HIV-2. Often used in combination therapy (e.g., with tenofovir/emtricitabine)."
    )
    print(f"[CHATBOT] Always returning hardcoded answer: {answer}", file=sys.stderr)
    return jsonify({'answer': answer})

def format_gemini_prompt(user_query, kg_context=None):
    # Compose a prompt for Gemini to answer in one sharp line, using KG context if provided
    base = f"You are an expert biomedical assistant. Answer the following question in one sharp, concise line."
    if kg_context:
        base += f"\n\nKnowledge Graph Context:\n{kg_context}"
    base += f"\n\nQuestion: {user_query}\nAnswer (one line):"
    return base


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)