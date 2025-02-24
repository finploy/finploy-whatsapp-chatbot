from flask import Flask, request, render_template
from pprint import pprint
from reply import reply_to_msg
from model import handle_message
import json
import os

app = Flask(__name__)

PROMPT_FILE = 'custom_prompt.json'

def load_custom_prompt():
    """Load custom prompt from file if it exists"""
    try:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, 'r') as f:
                data = json.load(f)
                return data.get('prompt', '')
        return ''
    except Exception as e:
        print(f"Error loading prompt: {str(e)}")
        return ''

def save_custom_prompt(prompt):
    """Save custom prompt to file"""
    try:
        with open(PROMPT_FILE, 'w') as f:
            json.dump({'prompt': prompt}, f)
        return True
    except Exception as e:
        print(f"Error saving prompt: {str(e)}")
        return False

# Load custom prompt when starting the server
custom_prompt = load_custom_prompt()

@app.route('/', methods=['POST'])
def webhook():
    try:
        req = request.get_json(force=True)
        pprint(req)  # Log the request for debugging
        global custom_prompt
        
        # Extract necessary fields
        phone_number = req.get('contact', {}).get('phone_number')
        is_new_msg = req.get('message', {}).get('is_new_message')
        message_body = req.get('message', {}).get('body', '')
        resume_link = ""
        if req.get('message',{}).get('media','') and type(req.get('message',{}).get('media','')) != list:
            resume_link = req.get('message',{}).get('media','').get('link', '')
            print(resume_link)
            message_body = "process_my_form"
        
        if not all([phone_number, is_new_msg, message_body]):
            return ""  # Return empty if required fields are missing
        
        if is_new_msg:
            # Process message and get response using the current custom prompt
            openai_response = handle_message(user_question=message_body, resume_link= resume_link, phone_number= phone_number,custom_prompt= custom_prompt)
            
            # Send response back via WhatsApp
            reply_to_msg(phone_number, openai_response)
        
        return ""
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return ""

@app.route('/manage-prompt', methods=['GET', 'POST'])
def manage_prompt():
    global custom_prompt
    if request.method == 'POST':
        new_prompt = request.form.get('prompt', '')
        if save_custom_prompt(new_prompt):
            custom_prompt = new_prompt
            return {'status': 'success', 'message': 'Prompt updated successfully'}
        return {'status': 'error', 'message': 'Failed to update prompt'}, 500
    return render_template('manage_prompt.html', current_prompt=custom_prompt)

if __name__ == "__main__":
    app.run(debug=True, port=8000, host='0.0.0.0')
