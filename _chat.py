from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

template = """

Conversation History: {context}

Question: {question}

Answer:
"""

model = OllamaLLM(model='llama3.2:3b')
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

def handle_conversation():
    context=''
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        result = chain.invoke({'context': context, 'question': user_input})
        print("Bot: ", result, "\n")
        context += f"\nUser: {user_input}\nAI: {result}"

if __name__ == "__main__":
    handle_conversation()
