import requests
from pprint import pprint 
from dotenv import load_dotenv
load_dotenv()
import os

vendor_id = os.getenv("VENDOR_ID")
access_token = os.getenv("ACCESS_TOKEN")

url = f"https://watifly.in/api/{vendor_id}/contact/send-message"


def reply_to_msg(phone_number:str, message:str):
    payload = {
        "phone_number": phone_number,
        "message_body": message
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.request("POST", url, json=payload, headers=headers)

    response_json=response.json()

    return response_json
