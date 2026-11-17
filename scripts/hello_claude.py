from dotenv import load_dotenv
import anthropic

load_dotenv()                     # reads .env and makes ANTHROPIC_API_KEY available

client = anthropic.Anthropic()    # finds the key automatically

response = client.messages.create(
    model="claude-haiku-5-5",     # chooses which claude: the cheap, fast model, for development
    max_tokens=200,               # upper limit on the length of the answer
    messages=[
        {"role": "user", "content": "In one sentence: what does a customer support agent do?"}
    ],
)

print(response.content[0].text)
print("Tokens used:", response.usage.input_tokens, "in /", response.usage.output_tokens, "out")