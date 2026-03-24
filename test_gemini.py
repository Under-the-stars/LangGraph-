from google import genai
import os

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.0-flash", 
    contents="Hello from my Mac!"
)

print(response.text)
