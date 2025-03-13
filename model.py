import openai
import os
import mysql.connector
import ast
import json
from datetime import datetime
import logging
from prompt import system_prompt
from dotenv import load_dotenv

# Constants and Configuration
SUPPORT_PHONE = "8169449669"
DEFAULT_ERROR_MESSAGE = f"Please call me directly on {SUPPORT_PHONE}"

# Setup
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_db_connection():
    """Create and return a database connection"""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
    except mysql.connector.Error as e:
        logging.error(f"Database connection error: {e}")
        raise

def execute_query(query, values=None, fetch=False):
    """Execute a database query with error handling"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(buffered=True)
        
        if values:
            cursor.execute(query, values)
            print("data added.")
        else:
            cursor.execute(query)
            print("data added.")
            
        if fetch:
            result = cursor.fetchall()
            return result
        else:
            connection.commit()
            return cursor.lastrowid
            
    except Exception as e:
        if connection:
            connection.rollback()
        logging.error(f"Database query error: {e}")
        return DEFAULT_ERROR_MESSAGE
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.commit()
            connection.close()

def extract_json_data(response,):
    """Extract JSON data from response string"""
    start_index = response.index("{")
    end_index = response.index("}") + 1
    data_str = response[start_index:end_index]
    return ast.literal_eval(data_str)

# Functions for conversation history management
def load_conversation_data(phone_number, uid):
    """Load all conversation data including history and context variables"""
    try:
        query = """SELECT history, current_id, user_name FROM conversation_history 
                  WHERE contact_number = %s AND uid = %s"""
        values = (phone_number, uid)
        result = execute_query(query, values, fetch=True)
        
        if result and result[0][0]:
            # Extract all values
            history_json = result[0][0]
            current_id = result[0][1]
            user_name = result[0][2]
            
            # Convert the JSON string from database to a Python list
            conversation_history = json.loads(history_json) if history_json else []
            
            return {
                "conversation_history": conversation_history,
                "current_id": current_id,
                "user_name": user_name
            }
        else:
            return {
                "conversation_history": [],
                "current_id": None,
                "user_name": None
            }
            
    except Exception as e:
        logging.error(f"Error loading conversation data: {e}")
        return {
            "conversation_history": [],
            "current_id": None,
            "user_name": None
        }

def save_conversation_data(phone_number, uid, conversation_history, current_id=None, user_name=None):
    """Save all conversation data including history and context variables"""
    try:
        # Convert the conversation history list to a JSON string
        history_json = json.dumps(conversation_history)
        
        # Check if a record already exists for this phone number and uid
        query = """SELECT id FROM conversation_history WHERE contact_number = %s AND uid = %s"""
        values = (phone_number, uid)
        result = execute_query(query, values, fetch=True)
        
        if result:
            # Update existing record
            query = """UPDATE conversation_history 
                     SET history = %s, current_id = %s, user_name = %s, updated_at = %s 
                     WHERE contact_number = %s AND uid = %s"""
            values = (history_json, current_id, user_name, datetime.now(), phone_number, uid)
            execute_query(query, values)
        else:
            # Create new record
            query = """INSERT INTO conversation_history 
                     (contact_number, uid, history, current_id, user_name, created_at, updated_at) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            values = (phone_number, uid, history_json, current_id, user_name, 
                      datetime.now(), datetime.now())
            execute_query(query, values)
            
        return True
    except Exception as e:
        logging.error(f"Error saving conversation data: {e}")
        return False

# def clear_conversation_data(phone_number, uid):
#     """Clear conversation data after completion"""
#     try:
#         query = """UPDATE conversation_history 
#                  SET history = %s, current_id = NULL, user_name = NULL, updated_at = %s 
#                  WHERE contact_number = %s AND uid = %s"""
#         values = ("[]", datetime.now(), phone_number, uid)
#         execute_query(query, values)
#         return True
#     except Exception as e:
#         logging.error(f"Error clearing conversation data: {e}")
#         return False

def candidate_query(user_question, phone_number, uid):
    """Handle job inquiry requests"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        conversation_history = data["conversation_history"]
        
        db = get_db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(f"SELECT * FROM candidates WHERE associate_mobile = '{phone_number}' ;")
        results = cursor.fetchall()
        
        if not results:
            output = "You have not refer any candidate yet."
        else:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You get fetched response from database which is basically the refrrals information which refer by user. Fetched response contains the table fileds as - [user_id,username,mobile_number,current_location,associate_id,associate_name,associate_mobile,unique_link,status,jobrole,companyname,salary,created]. Associate is the person who refer the candidate(i.e. the user who ask for this candidates info now ). Rewrite that in natural language for user understanding."},
                    {"role": "user", "content": f"fetched response - {results}"},
                ],
                temperature = 0.4
            )
            output = response.choices[0].message['content']
            
        # Update conversation history
        conversation_history.append({"role": "assistant", "content": output})
        save_conversation_data(phone_number, uid, conversation_history, 
                              data["current_id"], data["user_name"])
        
        return output
        
    except Exception as e:  
        logging.error(f"Job inquiry error: {e}")
        return "Sorry, I couldn't process your request. Please try again."
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'db' in locals() and db:
            db.close()

def handle_milestone_2(response, phone_number, uid):
    """Handle milestone 2 data processing"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        current_id = data["current_id"]
        conversation_history = data["conversation_history"]
        
        if not current_id:
            return "Error: Application ID not found. Please restart the application process."
            
        print("ID get in milestone 2 : ", current_id)
        
        extracted_data = extract_json_data(response)

        query =  f"""UPDATE candidate_details SET employed = '{extracted_data['employed_or_not']}', gender = '{extracted_data['gender']}', sales_experience = '{extracted_data['bank_experience']}' WHERE id = {current_id} ; """
        execute_query(query)
        
        conversation_history.append({
            "role": "assistant",
            "content": "Milestone - 2 completed. Do you want to proceed next milestone?"
        })
        
        # Save updated conversation history
        save_conversation_data(phone_number, uid, conversation_history, current_id, data["user_name"])
        
        print("conversation_history in milestone 2",conversation_history)
        return "Your information saved successfully.\nPart 2 of 4 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 3."
    except Exception as e:
        logging.error(f"Milestone 2 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_milestone_3(response, phone_number, uid):
    """Handle milestone 3 data processing"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        current_id = data["current_id"]
        conversation_history = data["conversation_history"]
        
        if not current_id:
            return "Error: Application ID not found. Please restart the application process."
            
        print("current id in milestone 3 : ", current_id)
        
        extracted_data = extract_json_data(response)
        query =  f"""UPDATE candidate_details SET 
                    hl_lap = '{extracted_data['hl/lap']}', 
                    personal_loan = '{extracted_data['personal_loan']}', 
                    business_loan = '{extracted_data['business_loan']}', 
                    education_loan = '{extracted_data['education_loan']}', 
                    gold_loan = '{extracted_data['gold_loan']}', 
                    credit_cards = '{extracted_data['credit_cards']}', 
                    casa = '{extracted_data['casa']}', 
                    others = '{extracted_data['others']}', 
                    Sales = '{extracted_data['Sales']}', 
                    Credit_dept = '{extracted_data['Credit_dept']}', 
                    HR_Training = '{extracted_data['HR/Training']}', 
                    Legal_compliance_Risk = '{extracted_data['Legal/compliance/Risk']}', 
                    Operations = '{extracted_data['Operations']}', 
                    Others1 = '{extracted_data['Others1']}' 
                    WHERE id = {current_id} ; """
        
        execute_query(query)
        
        conversation_history.append({
            "role": "assistant",
            "content": "Milestone - 3 completed. application completed."
        })
        
        # Save updated conversation history
        save_conversation_data(phone_number, uid, conversation_history, current_id, data["user_name"])
        
        print("conversation_history in milestone 3",conversation_history)
        return "Your information saved successfully.\nPart 3 of 4 completed🎉.\nLastly please upload your resume to complete the apply process."
    except Exception as e:
        logging.error(f"Milestone 3 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_job_inquiry(user_question, query, phone_number, uid):
    """Handle job inquiry processing"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        conversation_history = data["conversation_history"]
        
        results = execute_query(query, fetch=True)
        
        if not results:
            return DEFAULT_ERROR_MESSAGE
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You get user question and the fetched response from database for that question. Rewrite that response in natural language for user understanding. The fetched response contains following fields - id (INT), jobrole (VARCHAR), companyname (VARCHAR), location (VARCHAR), salary (VARCHAR). give all fetched data in structure format to understand user. don't mention id in response."},
                {"role": "user", "content": f"question is - {user_question} and fetched response - {results}"},
            ],
            temperature=0.4
        )
        
        output = response.choices[0].message['content']
        
        # Update conversation history
        conversation_history.append({"role": "assistant", "content": output})
        save_conversation_data(phone_number, uid, conversation_history,
                             data["current_id"], data["user_name"])
        
        return output
    except Exception as e:
        logging.error(f"Job inquiry error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_referral(data_dict, phone_number, uid):
    """Handle referral processing"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        conversation_history = data["conversation_history"]
        
        # Check if associate exists
        query = """SELECT associate_id FROM associate WHERE mobile_number = %s"""
        associate_result = execute_query(query, (phone_number,), fetch=True)
        
        if associate_result:
            associate_id = associate_result[0][0]
        else:
            # Create new associate
            query = """INSERT INTO associate (username, mobile_number, unique_link, created) 
                VALUES (%s, %s, %s, %s)"""
            values = (data_dict["user_Name"], phone_number, "", datetime.now())
            associate_id = execute_query(query, values)

        # Check if candidate already exists
        query = f"SELECT * FROM candidates WHERE mobile_number = {data_dict['candidate_mobile_number']}"
        candidate_exists = execute_query(query, fetch=True)
        
        if candidate_exists:
            output = "This candidate is already referred."
        else:
            # Insert new candidate
            query = """INSERT INTO candidates (
                username, mobile_number, current_location, associate_id,
                associate_name, associate_mobile, unique_link, jobrole,
                companyname, location, salary, created
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            values = (
                data_dict["candidate_Full_Name"],
                data_dict["candidate_mobile_number"],
                data_dict["candidate_current_location"],
                associate_id,
                data_dict["user_Name"],
                phone_number,
                "", "", "", "", "",
                datetime.now()
            )
            
            execute_query(query, values)
            output = "Thank you for the referral! I've registered the candidate successfully. 🤝"
        
        # Update conversation history
        conversation_history.append({"role": "assistant", "content": output})
        save_conversation_data(phone_number, uid, conversation_history,
                             data["current_id"], data["user_name"])
        
        return output
        
    except Exception as e:
        logging.error(f"Referral error: {e}")
        return DEFAULT_ERROR_MESSAGE

def check_existing_application(phone_number):
    """Check if user already has an application with modifications"""
    try:
        query = """SELECT id FROM candidate_details 
                  WHERE mobile_number = %s 
                  AND modified IS NOT NULL"""
        result = execute_query(query, (phone_number,), fetch=True)
        print(result)
        return bool(result)
    except Exception as e:
        logging.error(f"Application check error: {e}")
        return False

def handle_milestone_1(response, phone_number, uid):
    """Handle milestone 1 data processing with application validation"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        conversation_history = data["conversation_history"]
        
        # Check if user already has an application
        if check_existing_application(phone_number):
            message = "You already have an existing application with this contact number in our system. Do you want to overwrite that application?\n(Please type 'YES' or 'NO')"
            
            conversation_history.append({
                "role": "assistant",
                "content": message
            })
            
            # Save updated conversation history
            save_conversation_data(phone_number, uid, conversation_history)
            
            print("conversation_history in milestone 1",conversation_history)
            return message
            
        else:
            extracted_data = extract_json_data(response)

            query = """INSERT INTO candidates(username, mobile_number, current_location, associate_id, associate_name, associate_mobile, unique_link, status, jobrole, companyname, location, salary, created)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            values = (
                extracted_data['username'], 
                phone_number,  # Add phone number to the initial save
                extracted_data['current_location'],
                1, "harsh", "8104748399", "", "PENDING", "", "", "", "", datetime.now()
            )
            id = execute_query(query, values)
            query1 = """INSERT INTO candidate_details 
                (user_id, username, mobile_number, current_location, work_experience, 
                current_salary, current_company, destination) 
                VALUES (%s,%s, %s, %s, %s, %s, %s, %s)"""
            values1 = (
                id,
                extracted_data['username'], 
                phone_number,  # Add phone number to the initial save
                extracted_data['current_location'],
                extracted_data['work_experience'], 
                extracted_data['current_salary'],
                extracted_data['company_name'], 
                extracted_data['designation']
            )
            
            current_id = execute_query(query1, values1)
            print("New application ID:", current_id)
            
            conversation_history.append({
                "role": "assistant",
                "content": "Milestone - 1 completed. Do you want to proceed next milestone?"
            })
            
            # Save updated conversation history with current_id
            save_conversation_data(phone_number, uid, conversation_history, current_id, data["user_name"])
            
            message = "Your information saved successfully.\nPart 1 of 4 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 2."
            return message
    except Exception as e:
        logging.error(f"Milestone 1 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_referral_milestone_1(response, phone_number, uid):
    """Handle referral milestone 1 data processing"""
    try:
        # Load current conversation data
        data = load_conversation_data(phone_number, uid)
        conversation_history = data["conversation_history"]
        
        extracted_data = extract_json_data(response)
        user_name = extracted_data["user_Name"]

        # Check if associate already exists
        query = """SELECT associate_id, username FROM associate WHERE mobile_number = %s"""
        existing_associate = execute_query(query, (phone_number,), fetch=True)
        
        if existing_associate:
            # If associate exists, just update the username if it's empty
            associate_id = existing_associate[0][0]
            existing_username = existing_associate[0][1]
            
            if not existing_username.strip():  # Update only if username is empty or just whitespace
                update_query = """UPDATE associate SET username = %s WHERE associate_id = %s"""
                execute_query(update_query, (user_name, associate_id))
        else:
            # Create new associate if phone number doesn't exist
            query = """INSERT INTO associate (username, mobile_number, unique_link, created) 
                VALUES (%s, %s, %s, %s)"""
            values = (user_name, phone_number, "", datetime.now())
            execute_query(query, values)

        conversation_history.append({
            "role": "assistant",
            "content": "Milestone - 1 completed. Do you want to proceed next milestone?"
        })
        
        # Save updated conversation history with user_name
        save_conversation_data(phone_number, uid, conversation_history, data["current_id"], user_name)
        
        return "Your information saved successfully.\nMilestone - 1 completed 🎉.\n\nWould like to proceed to MILESTONE 2 ?"
        
    except Exception as e:
        logging.error(f"Referral milestone 1 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_message(user_question, phone_number, resume_link, custom_prompt, uid):
    """Main function to handle all incoming messages"""
    try:
        # Normalize phone number
        phone_number = phone_number.removeprefix("91")
        
        # Load conversation data from database
        data = load_conversation_data(phone_number, uid)
        conversation_history = data["conversation_history"]
        current_id = data["current_id"]
        user_name = data["user_name"]
        
        # Add user's question to history
        conversation_history.append({"role": "user", "content": user_question})
        
        # Save conversation history immediately
        save_conversation_data(phone_number, uid, conversation_history, current_id, user_name)
        
        # Process the message with OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt + custom_prompt},
                *[msg for msg in conversation_history if msg.get("role") in ["user", "assistant"]],  # Only include user and assistant messages
            ],
            temperature=0.4
        )
        response_content = response.choices[0].message['content']
        print(conversation_history)
        print(response_content)
        
        # Handle resume upload
        if resume_link:
            if current_id:
                query = """UPDATE candidate_details SET 
                    resume = %s, modified = %s 
                    WHERE id = %s"""
                values = (resume_link, datetime.now(), current_id)
                execute_query(query, values)
                
                # # Clear conversation history after complete application
                # clear_conversation_data(phone_number, uid)
                return "Your application saved successfully.\nPart 4 of 4 completed🎉."
            else:
                return "Unable to save resume. Application ID not found."
            
        # Handle different response types
        if "```milestone_1" in response_content:
            return handle_milestone_1(response_content, phone_number, uid)
        elif "```milestone_2" in response_content:
            return handle_milestone_2(response_content, phone_number, uid)
        elif "```milestone_3" in response_content:
            return handle_milestone_3(response_content, phone_number, uid)
        elif "```job_inquiry_query" in response_content:
            start_index = response_content.index("{") + 1
            end_index = response_content.index("}")
            query = response_content[start_index:end_index]
            print(query)
            return handle_job_inquiry(user_question, query, phone_number, uid)
        elif "```referral_milestone_1" in response_content:
            return handle_referral_milestone_1(response_content, phone_number, uid)
        elif "```referral_milestone_2" in response_content:
            data = extract_json_data(response_content)
            if user_name:
                data["user_Name"] = user_name
            return handle_referral(data, phone_number, uid)
        elif "```candidate_query" in response_content:
            return candidate_query(user_question, phone_number, uid)
            
        # Handle regular response
        conversation_history.append({"role": "assistant", "content": response_content})
        save_conversation_data(phone_number, uid, conversation_history, current_id, user_name)
        return response_content
        
    except Exception as e:
        logging.error(f"Message handling error: {e}")
        return DEFAULT_ERROR_MESSAGE

# For testing:
if __name__ == "__main__":
    while True:
        user = input("Enter: ")
        if user == "exit":
            break
        else: 
            print(handle_message(user, "917304847881", "", "", "test_uid"))
