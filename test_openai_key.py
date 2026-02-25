# test_openai_key.py
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Get the key from .env
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("ERROR: OPENAI_API_KEY not found in .env file!")
    exit(1)

print("API key found in .env — length:", len(api_key))

# Create a minimal LLM instance
llm = ChatOpenAI(
    model="gpt-4o-mini",           # cheap & fast model for testing
    temperature=0,
    api_key=api_key,               # explicitly pass it (optional, but clear)
)

# Very simple prompt → should always work if key is valid
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "Say exactly this and nothing else: API key test successful"),
])

chain = prompt | llm

print("\nSending test request to OpenAI...")

try:
    response = chain.invoke({})
    content = response.content.strip()
    print("\nOpenAI response:", content)
    
    if "API key test successful" in content:
        print("\nSUCCESS: Your OpenAI API key is WORKING correctly!")
    else:
        print("\nWARNING: Got response, but content looks strange.")
except Exception as e:
    print("\nERROR: OpenAI call failed")
    print("Exception:", str(e))
    if "401" in str(e) or "invalid api key" in str(e).lower():
        print("→ Most likely: INVALID or EXPIRED API key")
    elif "429" in str(e):
        print("→ Rate limit hit — wait a minute and retry")
    elif "insufficient funds" in str(e).lower():
        print("→ Your OpenAI account has no credits / payment method issue")