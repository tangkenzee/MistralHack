import base64
import requests
from dotenv import load_dotenv
import os
from mistralai import Mistral

load_dotenv()

api_key = os.environ["MISTRAL_API_KEY"]
model = "pixtral-large-latest"

client = Mistral(api_key=api_key)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

image_path = "./images/vscode.png" # path to your image
base64_image = encode_image(image_path)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                # "text": "Based on the given image, provide these information. 1. The size and resolution of the image 2. Based on the ascpect ratio of the image divide it into a 10 column 5 row grid. Tell me where is the Setting Button at? Note that you only give me the answer not filler text. "
                "text": "tell me where generally the settings button is"
            },
            {
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{base64_image}"
            }
        ]
    }
]

chat_response = client.chat.complete(
    model=model,
    messages=messages
)

print(chat_response)