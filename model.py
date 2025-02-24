from dotenv import load_dotenv
import openai
import os
import mysql.connector
import ast
from datetime import datetime, timedelta
import logging
import requests
from prompt import system_prompt

# Session management class
class Session:
    def __init__(self):
        self.conversational_history = []
        self.current_id = None
        self.user_name = None
        self.last_active = datetime.now()

class SessionManager:
    def __init__(self, session_timeout=60):  # timeout in minutes
        self.sessions = {}
        self.session_timeout = timedelta(minutes=session_timeout)

    def get_session(self, phone_number):
        """Get or create a session for a phone number"""
        self.cleanup_expired_sessions()
        
        if phone_number not in self.sessions:
            self.sessions[phone_number] = Session()
        else:
            self.sessions[phone_number].last_active = datetime.now()
            
        return self.sessions[phone_number]

    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = datetime.now()
        expired_numbers = [
            number for number, session in self.sessions.items()
            if current_time - session.last_active > self.session_timeout
        ]
        for number in expired_numbers:
            del self.sessions[number]

    def clear_session(self, phone_number):
        """Clear a specific session"""
        if phone_number in self.sessions:
            del self.sessions[phone_number]

# Constants and Configuration
SUPPORT_PHONE = "8169449669"
DEFAULT_ERROR_MESSAGE = f"Please call me directly on {SUPPORT_PHONE}"

# Setup
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Create global session manager
session_manager = SessionManager()

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
        else:
            cursor.execute(query)
            
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

def extract_json_data(response):
    """Extract JSON data from response string"""
    start_index = response.index("{")
    end_index = response.index("}") + 1
    data_str = response[start_index:end_index]
    return ast.literal_eval(data_str)

def candidate_query(user_question, phone_number):
    """Handle job inquiry requests"""
    try:
        query = """SELECT * FROM candidates WHERE associate_mobile = %s"""
        results = execute_query(query, (phone_number,), fetch=True)
        
        if not results:
            return "You have not referred any candidate yet."
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You get fetched response from database which is basically the referrals information which refer by user. Fetched response contains the table fields as - [user_id,username,mobile_number,current_location,associate_id,associate_name,associate_mobile,unique_link,status,jobrole,companyname,salary,created]. Associate is the person who refer the candidate(i.e. the user who ask for this candidates info now). Rewrite that in natural language for user understanding."},
                {"role": "user", "content": f"fetched response - {results}"},
            ],
            temperature=0.4
        )
        return response.choices[0].message['content']
        
    except Exception as e:  
        logging.error(f"Job inquiry error: {e}")
        return "Sorry, I couldn't process your request. Please try again."

def handle_milestone_2(response, session):
    """Handle milestone 2 data processing"""
    try:
        data = extract_json_data(response)
        query = f"""UPDATE candidate_details SET employed = '{data['employed_or_not']}', gender = '{data['gender']}', sales_experience = '{data['bank_experience']}' WHERE id = {session.current_id} ; """

        # query = """UPDATE candidate_details SET 
        #     employed = %s, gender = %s, sales_experience = %s 
        #     WHERE id = %s"""
        # values = (
        #     data['employed_or_not'],
        #     data['gender'],
        #     data['bank_experience'],
        #     session.current_id
        # )
        
        execute_query(query)
        
        session.conversational_history.append({
            "role": "assistant",
            "content": "Milestone - 2 completed."
        })
        return "Your information saved successfully.\nPart 2 of 4 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 3."
    except Exception as e:
        logging.error(f"Milestone 2 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_milestone_3(response, session):
    """Handle milestone 3 data processing"""
    try:
        data = extract_json_data(response)
        # query = """UPDATE candidate_details SET 
        #     hl_lap = %s, personal_loan = %s, business_loan = %s,
        #     education_loan = %s, gold_loan = %s, credit_cards = %s,
        #     casa = %s, others = %s, Sales = %s, Credit_dept = %s,
        #     HR_Training = %s, Legal_compliance_Risk = %s,
        #     Operations = %s, Others1 = %s 
        #     WHERE id = %s"""
        # values = (
        #     data['hl/lap'], data['personal_loan'], data['business_loan'],
        #     data['education_loan'], data['gold_loan'], data['credit_cards'],
        #     data['casa'], data['others'], data['Sales'], data['Credit_dept'],
        #     data['HR/Training'], data['Legal/compliance/Risk'],
        #     data['Operations'], data['Others1'], session.current_id
        # )
        query = f"""UPDATE candidate_details SET 
                    hl_lap = '{data['hl/lap']}', 
                    personal_loan = '{data['personal_loan']}', 
                    business_loan = '{data['business_loan']}', 
                    education_loan = '{data['education_loan']}', 
                    gold_loan = '{data['gold_loan']}', 
                    credit_cards = '{data['credit_cards']}', 
                    casa = '{data['casa']}', 
                    others = '{data['others']}', 
                    Sales = '{data['Sales']}', 
                    Credit_dept = '{data['Credit_dept']}', 
                    HR_Training = '{data['HR/Training']}', 
                    Legal_compliance_Risk = '{data['Legal/compliance/Risk']}', 
                    Operations = '{data['Operations']}', 
                    Others1 = '{data['Others1']}' 
                    WHERE id = {session.current_id} ; """
        
        execute_query(query)
        
        session.conversational_history.append({
            "role": "assistant",
            "content": "Milestone - 3 completed"
        })
        return "Your information saved successfully.\nPart 3 of 4 completed🎉.\nLastly please upload your resume to complete the apply process."
    except Exception as e:
        logging.error(f"Milestone 3 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_job_inquiry(user_question, query):
    """Handle job inquiry processing"""
    try:
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
        return response.choices[0].message['content']
    except Exception as e:
        logging.error(f"Job inquiry error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_referral(data_dict, phone_number):
    """Handle referral processing"""
    try:
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
        query = """SELECT * FROM candidates WHERE mobile_number = %s"""
        candidate_exists = execute_query(query, (data_dict['candidate_mobile_number'],), fetch=True)
        
        if candidate_exists:
            return "This candidate is already referred."
            
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
        return "Thank you for the referral! I've registered the candidate successfully. 🤝"
        
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
        return bool(result)
    except Exception as e:
        logging.error(f"Application check error: {e}")
        return False

def handle_milestone_1(response, phone_number, session):
    """Handle milestone 1 data processing with application validation"""
    try:
        if check_existing_application(phone_number):
            session.conversational_history.append({
                "role": "assistant",
                "content": "Existing application found."
            })
            return "You already have an existing application in our system. Each user can only create one application."
        
        data = extract_json_data(response)
        query = """INSERT INTO candidate_details 
            (username, mobile_number, current_location, work_experience, 
            current_salary, current_company, destination) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        values = (
            data['username'], 
            phone_number,
            data['current_location'],
            data['work_experience'], 
            data['current_salary'],
            data['company_name'], 
            data['designation']
        )
        
        session.current_id = execute_query(query, values)
        
        session.conversational_history.append({
            "role": "assistant",
            "content": "Milestone - 1 completed."
        })
        return "Your information saved successfully.\nPart 1 of 4 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 2."
    except Exception as e:
        logging.error(f"Milestone 1 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_referral_milestone_1(response, phone_number, session):
    """Handle referral milestone 1 data processing"""
    try:
        data = extract_json_data(response)
        session.user_name = data["user_Name"]

        # Check if associate already exists
        query = """SELECT associate_id, username FROM associate WHERE mobile_number = %s"""
        existing_associate = execute_query(query, (phone_number,), fetch=True)
        
        if existing_associate:
            # If associate exists, just update the username if it's empty
            associate_id = existing_associate[0][0]
            existing_username = existing_associate[0][1]
            
            if not existing_username.strip():
                update_query = """UPDATE associate SET username = %s WHERE associate_id = %s"""
                execute_query(update_query, (session.user_name, associate_id))
        else:
            # Create new associate if phone number doesn't exist
            query = """INSERT INTO associate (username, mobile_number, unique_link, created) 
                VALUES (%s, %s, %s, %s)"""
            values = (session.user_name, phone_number, "", datetime.now())
            execute_query(query, values)

        session.conversational_history.append({
            "role": "assistant",
            "content": "Milestone - 1 completed."
        })
        return "Your information saved successfully.\nPart 1 of 2 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 2."
        
    except Exception as e:
        logging.error(f"Referral milestone 1 error: {e}")
        return DEFAULT_ERROR_MESSAGE

def handle_message(user_question, phone_number, resume_link, custom_prompt):
    """Main function to handle all incoming messages"""
    try:
        phone_number = phone_number.removeprefix("91")
        
        # Get session for this user
        session = session_manager.get_session(phone_number)
        
        # Add message to this user's conversation history
        session.conversational_history.append({"role": "user", "content": user_question})
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt + custom_prompt},
                *session.conversational_history,
            ],
            temperature=0.4
        )
        response_content = response.choices[0].message['content']
        
        # Handle resume upload
        if resume_link:
            query = """UPDATE candidate_details SET 
                resume = %s, modified = %s 
                WHERE id = %s"""
            values = (resume_link, datetime.now(), session.current_id)
            execute_query(query, values)
            session_manager.clear_session(phone_number)  # Clear session after completion
            return "Your application saved successfully.\nPart 4 of 4 completed🎉."
            
        # Handle different response types
        if "```milestone_1" in response_content:
            return handle_milestone_1(response_content, phone_number, session)
        elif "```milestone_2" in response_content:
            return handle_milestone_2(response_content, session)
        elif "```milestone_3" in response_content:
            return handle_milestone_3(response_content, session)
        elif "```job_inquiry_query" in response_content:
            start_index = response_content.index("{") + 1
            end_index = response_content.index("}")
            query = response_content[start_index:end_index]
            return handle_job_inquiry(user_question, query)
        elif "```referral_milestone_1" in response_content:
            return handle_referral_milestone_1(response_content, phone_number, session)
        elif "```referral_milestone_2" in response_content:
            data = extract_json_data(response_content)
            data["user_Name"] = session.user_name
            return handle_referral(data, phone_number)
        elif "```candidate_query" in response_content:
            output = candidate_query(user_question, phone_number)
            session.conversational_history.append({"role": "assistant", "content": output})
            return output
            
        session.conversational_history.append({"role": "assistant", "content": response_content})
        return response_content
        
    except Exception as e:
        logging.error(f"Message handling error: {e}")
        return DEFAULT_ERROR_MESSAGE
