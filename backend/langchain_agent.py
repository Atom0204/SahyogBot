import os
from dotenv import load_dotenv
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain.vectorstores import Chroma
import requests

load_dotenv()
IBM_WATSON_API_KEY = os.getenv("IBM_WATSON_API_KEY")

DOCS_PATH = "docs"
VECTOR_STORE_PATH = "vector_store"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

IBM_WATSON_URL = "https://eu-de.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"
IBM_PROJECT_ID = "9a0b1866-eecb-4b29-b7f1-7ba2345b5ea1"
IBM_MODEL_ID = "meta-llama/llama-3-3-70b-instruct"
IBM_IAM_URL = "https://iam.cloud.ibm.com/identity/token"

def get_ibm_iam_token(api_key):
    data = {
        "apikey": api_key,
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(IBM_IAM_URL, data=data, headers=headers)
    response.raise_for_status()
    return response.json()["access_token"]

# Singleton for vector store
_vector_store = None

def load_or_create_vector_store():
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    if not os.path.exists(VECTOR_STORE_PATH):
        os.makedirs(VECTOR_STORE_PATH)
    loaders = []
    for filename in os.listdir(DOCS_PATH):
        if filename.lower().endswith(".pdf"):
            loaders.append(PyPDFLoader(os.path.join(DOCS_PATH, filename)))
    documents = []
    for loader in loaders:
        documents.extend(loader.load())
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    docs = splitter.split_documents(documents)
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_store = Chroma.from_documents(docs, embeddings, persist_directory=VECTOR_STORE_PATH)
    vector_store.persist()
    _vector_store = vector_store
    return vector_store

def call_ibm_watson_api(prompt: str) -> str:
    bearer_token = get_ibm_iam_token(IBM_WATSON_API_KEY)
    body = {
        "messages": [
            {
                "role": "system",
"content": (
    "You are SahyogBot, a helpful and polite AI assistant designed to guide Indian citizens—especially students, women, and rural families—through government schemes, scholarships, and financial aid.\n\n"
    "🧠 Use the provided 'Context' to answer any scheme-related question.\n"
    "🔁 If the context does not contain relevant information, respond with: 'No matching information found in database. I will now search the internet.' and stop.\n"
    "The user’s query will be followed by: \nContext: [retrieved content]\n\nQuestion: [user question]\n\nAnswer:\n"
    "If context is present, answer like this:\n\n"
    "🎯 Relevant Government Schemes:\n"
    "• [Scheme Name] - [Brief Description]\n"
    "• ...\n\n"
    "📋 Next Steps:\n"
    "1. [Check eligibility / Gather documents / Apply]\n\n"
    "🔗 Official Links (if any):\n"
    "- [MyGov.in / India.gov.in / State Portal]\n"
    "- [Helpline if relevant]\n\n"
    "💡 Format strictly using GitHub Markdown (bold, bullet points, etc.)\n"
    "NEVER make up schemes. Be factual. Never hallucinate or suggest fake links.\n"
    "Use clean language and never use disclaimers like 'As an AI model…'"
)

            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "project_id": IBM_PROJECT_ID,
        "model_id": IBM_MODEL_ID,
        "frequency_penalty": 0,
        "max_tokens": 2000,
        "presence_penalty": 0,
        "temperature": 0,
        "top_p": 1
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}"
    }
    response = requests.post(IBM_WATSON_URL, headers=headers, json=body)
    if response.status_code != 200:
        raise Exception(f"IBM Watson API error: {response.text}")
    data = response.json()
    # Extract the answer from the response structure
    try:
        return data["results"][0]["generated_text"]
    except Exception:
        return str(data)

def get_scheme_recommendation(query: str) -> str:
    vector_store = load_or_create_vector_store()
    retriever = vector_store.as_retriever()
    # Retrieve top 4 relevant chunks as context
    docs = retriever.get_relevant_documents(query)
    context = "\n\n".join([doc.page_content for doc in docs])
    prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    return call_ibm_watson_api(prompt)
