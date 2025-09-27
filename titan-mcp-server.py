# app.py
# The complete, production-ready Gradio MCP Server for the Titan-Reasoner.
# By: surfiniaburger
# Final Version with corrected class definitions.

import os
import gc
import json
import torch
import gradio as gr
import pymongo
from unsloth import FastLanguageModel, FastVisionModel
from transformers import AutoTokenizer, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer
from titans_pytorch.neural_memory import NeuralMemory
from torch.amp import custom_fwd
import math
import torch.nn as nn
from google.cloud import bigquery
from google.cloud import storage
from google.oauth2 import service_account
from huggingface_hub import hf_hub_download, snapshot_download
from PIL import Image
import io
import re

# ===============================================================
# 1. SETUP AND CONFIGURATION
# ===============================================================

print("--- Initializing Configuration ---")

# --- Load Secrets and Config ---
MONGO_URI = os.environ.get("MONGO_URI")
HF_TOKEN = os.environ.get("HUGGINGFACE_API_KEY")
GCP_SECRET_JSON = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")

TITAN_REASONER_REPO = "surfiniaburger/Purified-Reasoner-gpt-oss-20b-v1"
EMBEDDING_MODEL_NAME = "unsloth/embeddinggemma-300m"
# Use a powerful, memory-efficient open-source vision model
VISION_MODEL_REPO = "unsloth/llava-v1.6-mistral-7b-hf-bnb-4bit"
DB_NAME = "dipg_rag_db"
COLLECTION_NAME = "dipg_vectors"
MAX_SEQ_LENGTH = 1024

# --- GCP and MongoDB Clients ---
try:
    gcp_credentials_dict = json.loads(GCP_SECRET_JSON)
    credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
    GCP_PROJECT_ID = credentials.project_id
    bq_client = bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)
    BQ_DATASET_ID = "dipg_knowledge_base"
    BQ_TABLE_ID = "research_chunks"
    print("✅ Successfully authenticated with Google Cloud.")
except Exception as e:
    print(f"❌ GCP Authentication Failed: {e}"); bq_client = None

try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_client.admin.command('ping')
    db = mongo_client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("✅ MongoDB Connection Successful.")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}"); collection = None

# ===============================================================
# 2. PRE-CACHE MODELS AT STARTUP
# ===============================================================
print("\n--- Pre-caching all required models. This may take a while... ---")
snapshot_download(repo_id=EMBEDDING_MODEL_NAME, token=HF_TOKEN)
print("✅ Embedding model files cached.")
snapshot_download(repo_id=TITAN_REASONER_REPO, token=HF_TOKEN)
print("✅ Vision model files cached.")
snapshot_download(repo_id=TITAN_REASONER_REPO, token=HF_TOKEN)
print("✅ Titan-Reasoner model files cached.")
print("\n--- Model pre-caching complete. Application is ready. ---")

# --- Load Embedding Model (Now loads from cache instantly) ---
print("Loading Embedding Model into memory...")
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
print("✅ Embedding Model Loaded.")

# ===============================================================
# 3. TITAN-REASONER ARCHITECTURE (Corrected, Multi-line Definitions)
# ===============================================================

class ManualLayerNorm(nn.Module):
    def __init__(self, dim, eps=1e-5):
        super().__init__()
        self.eps = eps
        self.gamma = nn.Parameter(torch.ones(dim))
        self.beta = nn.Parameter(torch.zeros(dim))

    def forward(self, x):
        mean = x.mean(-1, keepdim=True)
        std = x.std(-1, keepdim=True)
        return self.gamma * (x - mean) / (std + self.eps) + self.beta

class BatchedLinear(nn.Module):
    def __init__(self, in_features, out_features, bias=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.weight = nn.Parameter(torch.empty(out_features, in_features))
        if bias:
            self.bias = nn.Parameter(torch.empty(out_features))
        else:
            self.register_parameter('bias', None)
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        if self.bias is not None:
            fan_in, _ = nn.init._calculate_fan_in_and_fan_out(self.weight)
            bound = 1 / math.sqrt(fan_in) if fan_in > 0 else 0
            nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x):
        weight, bias = self.weight, self.bias
        if weight.ndim > 2:
            x = torch.einsum('...ni,...oi->...no', x, weight)
        else:
            x = torch.einsum('...i,oi->...o', x, weight)
        if bias is not None:
            if bias.ndim == x.ndim - 1:
                bias = bias.unsqueeze(-2)
            x = x + bias
        return x

class EagerMemoryMLP(nn.Module):
    def __init__(self, dim, mult=4, depth=1):
        super().__init__()
        layers = []
        for _ in range(depth):
            layers.append(nn.Sequential(BatchedLinear(dim, dim * mult), nn.GELU(), BatchedLinear(dim * mult, dim)))
        self.model = nn.Sequential(*layers)
        self.norm = ManualLayerNorm(dim)

    def forward(self, x):
        return self.norm(self.model(x))

class PatchedNeuralMemory(NeuralMemory):
    def __init__(self, *args, **kwargs):
        dim = kwargs.get('dim')
        dim_head = kwargs.get('dim_head', dim)
        mlp_depth = kwargs.get('mem_mlp_depth', 1)
        eager_model = EagerMemoryMLP(dim=dim_head, depth=mlp_depth)
        kwargs['model'] = eager_model
        kwargs['mem_model_norm_add_residual'] = False
        kwargs['per_head_learned_parameters'] = False
        super().__init__(*args, **kwargs)
        self.store_norm = nn.LayerNorm(dim)
        self.retrieve_norm = nn.LayerNorm(dim)

class PatchedNeuralMemoryFP32(PatchedNeuralMemory):
    @custom_fwd(device_type='cuda', cast_inputs=torch.float32)
    def forward(self, *args, **kwargs):
        return super().forward(*args, **kwargs)

class TitanReasoner(nn.Module):
    def __init__(self, base_model):
        super().__init__()
        self.base_model = base_model
        model_dim = self.base_model.config.hidden_size
        self.memory = PatchedNeuralMemoryFP32(dim=model_dim, chunk_size=128, heads=4, dim_head=model_dim // 8)

    def forward(self, input_ids, **kwargs):
        input_embeds = self.base_model.get_input_embeddings()(input_ids)
        retrieved_memory, _ = self.memory(input_embeds)
        augmented_embeds = input_embeds + retrieved_memory.to(input_embeds.dtype)
        return self.base_model(inputs_embeds=augmented_embeds, **kwargs)


# ===============================================================
# 3. HELPER FUNCTIONS FOR MULTI-MODAL RAG
# ===============================================================

def extract_image_paths_from_texts(texts: list[str]) -> list[str]:
    """Finds all unique GCS image paths in a list of text chunks."""
    image_paths = set()
    for text in texts:
        matches = re.findall(r'\(gs://(.*?)\)', text)
        for match in matches:
            image_paths.add(f"gs://{match}")
    return list(image_paths)

def summarize_images_with_open_source_vision(image_paths: list[str]) -> dict[str, str]:
    """
    Takes a list of GCS image paths, generates summaries using an open-source
    vision model, and returns a mapping from path to summary.
    """
    if not image_paths:
        return {}

    print("Step 3.5a: Loading Open-Source Vision Model...")
    vision_model, processor = FastVisionModel.from_pretrained(
        VISION_MODEL_REPO,
        load_in_4bit=True,
        dtype=None,
        token=HF_TOKEN,
    )
    FastVisionModel.for_inference(vision_model)
    print("Vision model loaded.")

    summaries = {}
    for path in image_paths:
        try:
            print(f"Summarizing image: {path}")
            # Download image from GCS into a PIL Image object
            bucket_name = path.split('/')[2]
            blob_name = '/'.join(path.split('/')[3:])
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            image_bytes = blob.download_as_bytes()
            image = Image.open(io.BytesIO(image_bytes))

            instruction = "You are a medical expert. Describe this image from a research paper in detail. Be specific about graphs, charts, and tables. Explain what the data shows and what its implications might be in the context of brain tumor research."
            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": instruction}]}]
            
            input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = processor(image, input_text, return_tensors="pt").to("cuda")

            with torch.no_grad():
                outputs = vision_model.generate(**inputs, max_new_tokens=300, use_cache=True)
            
            summary = processor.decode(outputs[0], skip_special_tokens=True).split("ASSISTANT:")[-1].strip()
            summaries[path] = f"[AI-Generated Summary of Image: {summary}]"

        except Exception as e:
            print(f"❌ Failed to summarize image {path}: {e}")
            summaries[path] = f"[Image at {path.split('/')[-1]} could not be processed.]"
            
    # CRITICAL: Unload the vision model to free up VRAM for the Titan-Reasoner
    del vision_model, processor
    gc.collect()
    torch.cuda.empty_cache()
    print("Step 3.5b: Vision model unloaded from GPU memory.")
    return summaries



# ===============================================================
# 5. THE CORE RAG PIPELINE FUNCTION
# ===============================================================

def query_dipg_reasoner(user_query: str) -> str:
    """Answers questions about DIPG by retrieving, re-ranking, and generating a response."""
    if collection is None: return "Error: MongoDB connection is not available."
    if bq_client is None: return "Error: BigQuery connection is not available."

    # --- 1. RETRIEVE & 2. HYDRATE ---
    print(f"\nReceived query: '{user_query}'")
    print("Step 1 & 2: Retrieving from Mongo and Hydrating from BigQuery...")
    query_embedding = embedding_model.encode(user_query)
    pipeline = [{"$vectorSearch": {"index": "vector_index", "queryVector": query_embedding.tolist(), "path": "embedding", "numCandidates": 100, "limit": 10}}, {"$project": {"_id": 0, "chunk_id": 1}}]
    retrieved_ids = list(collection.aggregate(pipeline))
    if not retrieved_ids: return "I could not find any relevant information."
    
    chunk_ids = [doc['chunk_id'] for doc in retrieved_ids]
    formatted_ids = ', '.join(f"'{cid}'" for cid in chunk_ids)
    query = f"SELECT chunk_id, chunk_text FROM `{GCP_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}` WHERE chunk_id IN ({formatted_ids})"
    hydrated_docs = bq_client.query(query).to_dataframe().to_dict('records')
    print(f"Retrieved and hydrated {len(hydrated_docs)} documents.")
    print(hydrated_docs)

    # --- 3. RE-RANK WITH QWEN RERANKER ---
    print("Step 3: Re-ranking documents with Qwen-Reranker...")
    
    # Load reranker model
    reranker_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Reranker-4B", padding_side='left')
    reranker_model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-Reranker-4B", torch_dtype=torch.float16).to("cuda")
    reranker_model.eval()

    # Define reranking task and prepare pairs
    task = 'Given a medical research query about DIPG, find the most relevant text chunk from a research paper.'
    pairs = [f"<Instruct>: {task}\n<Query>: {user_query}\n<Document>: {doc['chunk_text']}" for doc in hydrated_docs]

    # Prepare tokens for Qwen Reranker
    prefix_tokens = reranker_tokenizer.encode("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n", add_special_tokens=False)
    suffix_tokens = reranker_tokenizer.encode("<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n", add_special_tokens=False)
    token_false_id = reranker_tokenizer.convert_tokens_to_ids("no")
    token_true_id = reranker_tokenizer.convert_tokens_to_ids("yes")

    scores = []
    with torch.no_grad():
        for pair in pairs:
            # Tokenize without padding for a single pair
            inputs = reranker_tokenizer(
                [pair], padding=False, truncation=True,
                max_length=8192 - len(prefix_tokens) - len(suffix_tokens)
            )
            
            # Manually add prefix and suffix
            inputs['input_ids'][0] = prefix_tokens + inputs['input_ids'][0] + suffix_tokens
            
            # Pad and create tensor
            inputs = reranker_tokenizer.pad(inputs, padding=True, return_tensors="pt").to("cuda")

            # Get scores
            batch_scores = reranker_model(**inputs).logits[:, -1, :]
            true_vector = batch_scores[:, token_true_id]
            false_vector = batch_scores[:, token_false_id]
            batch_scores = torch.stack([false_vector, true_vector], dim=1)
            score = torch.nn.functional.log_softmax(batch_scores, dim=1)[:, 1].exp().tolist()
            scores.extend(score)

    for doc, score in zip(hydrated_docs, scores):
        doc['rerank_score'] = score
    
    top_docs = sorted(hydrated_docs, key=lambda x: x['rerank_score'], reverse=True)[:3]
    
    # Cleanup reranker model from memory
    del reranker_model, reranker_tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    
    print("Re-ranking complete.")

    # --- NEW STEP 3.5: EXTRACT & SUMMARIZE IMAGES ---
    print("Step 3.5: Extracting and summarizing images from top documents...")
    all_texts_for_images = [doc['chunk_text'] for doc in top_docs]
    image_paths_to_summarize = extract_image_paths_from_texts(all_texts_for_images)
    
    image_summaries_map = {}
    if image_paths_to_summarize:
        image_summaries_map = summarize_images_with_open_source_vision(image_paths_to_summarize)
    else:
        print("No images found in the retrieved documents.")

    # --- 4. AUGMENT & GENERATE (LOAD -> USE -> UNLOAD) ---
    print("Step 4: Loading and running Titan-Reasoner...")
    base_model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=TITAN_REASONER_REPO, max_seq_length=512, dtype=None, load_in_4bit=True, token=HF_TOKEN,
    )
    titan_reasoner_model = TitanReasoner(base_model).to("cuda")
    memory_weights_path = hf_hub_download(repo_id=TITAN_REASONER_REPO, filename="titan_reasoner_memory.pt", token=HF_TOKEN)
    titan_reasoner_model.memory.load_state_dict(torch.load(memory_weights_path, map_location="cuda") )
    titan_reasoner_model.eval()

    # --- CORRECTED CONTEXT AUGMENTATION ---
    context_for_prompt = ""
    for i, doc in enumerate(top_docs):
        doc_text = doc['chunk_text']
        # Find all image placeholders in this chunk
        image_placeholders_in_doc = re.findall(r'\(gs://(.*?)\)', doc_text)
        
        for placeholder in image_placeholders_in_doc:
            gcs_path = f"gs://{placeholder}"
            if gcs_path in image_summaries_map:
                # Replace the placeholder with the rich summary
                doc_text = doc_text.replace(f"({gcs_path})", f"\\n{image_summaries_map[gcs_path]}\n")

        context_for_prompt += f"--- CONTEXT SOURCE {i+1} (Score: {doc['rerank_score']:.4f}) ---\n{doc_text}\n\n"


    system_prompt = f"""You are a specialized AI assistant, the Titan-Reasoner, designed to answer questions about Diffuse Intrinsic Pontine Glioma (DIPG). Your knowledge is strictly limited to the context provided below.

**CRITICAL DIRECTIVES:**
1.  Base your entire answer ONLY on the information contained within the "CONTEXT SOURCE" sections.
2.  Do NOT use any of your internal, pre-trained knowledge about DIPG or any other topic.
3.  If the provided context does not contain enough information to answer the question, you MUST state that and explain what information is missing. Do not attempt to guess or infer.
4.  When you use information from a source, cite it at the end of the sentence like this: [Source 1], [Source 2], etc.

**CONTEXT PROVIDED:**
{context_for_prompt}

**USER'S QUESTION:**
{user_query}

**CRITICAL FINAL INSTRUCTION:**
First, think step-by-step in an 'analysis' channel to determine the answer from the context.
Then, you MUST conclude your response with a 'final' channel that contains ONLY the direct and concise answer to the user's question.

**YOUR RESPONSE:**
"""
    messages = [{"role": "user", "content": system_prompt}]
    prompt_string = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, reasoning_effort="high")
    inputs = tokenizer(prompt_string, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = titan_reasoner_model.base_model.generate(
            **inputs, max_new_tokens=256, temperature=0.1, repetition_penalty=1.1, pad_token_id=tokenizer.eos_token_id
        )
    
    response_text = tokenizer.decode(outputs[0, inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    
    del base_model, tokenizer, titan_reasoner_model; gc.collect(); torch.cuda.empty_cache()
    print("Generation complete. Titan-Reasoner unloaded from GPU memory.")
    
    return response_text

# ===============================================================
# 5. CREATE THE GRADIO INTERFACE
# ===============================================================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # Titan-Reasoner: A Specialized RAG System for DIPG Research
        This application uses a fine-tuned `gpt-oss-20b` model (the Titan-Reasoner) to answer questions about the pediatric brain tumor DIPG. 
        It retrieves information from a knowledge base of research papers and generates answers based *only* on that context, 
        leveraging the model's specialized training to avoid hallucination.
        """
    )
    with gr.Row():
        query_input = gr.Textbox(label="Ask a question about DIPG", placeholder="What are the latest experimental treatments for H3K27M-mutant DIPG?")
        submit_button = gr.Button("Submit", variant="primary")
    output_answer = gr.Markdown(label="Generated Answer")
    submit_button.click(fn=query_dipg_reasoner, inputs=query_input, outputs=output_answer)

# CORRECTED: The __name__ check needs double underscores on both sides
if __name__ == "__main__":
    demo.launch(mcp_server=True)
