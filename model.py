from dotenv import load_dotenv
import openai
import os
import mysql.connector
import ast
from datetime import datetime
import logging
import requests
from prompt import system_prompt

# Load environment variables and setup
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def db_connection():
    """Create database connection"""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
    except mysql.connector.Error as e:
        logging.error(f"Database error: {e}")
        raise


def job_inquiry_query(user_question,query):
    """Handle job inquiry requests"""
    try:
        db = db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(query)
        results = cursor.fetchall()
        print(results)
        if not results:
            return "I couldn't find any matching response at the moment. 😕"
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You get user question and the fetched response from database for that question. Rewrite that response in natural language for user understanding. The fetched response contains following fileds - id (INT) ,jobrole (VARCHAR) ,companyname (VARCHAR) ,location (VARCHAR) ,salary (VARCHAR). give all fetched data in structure format to undersatnd user. don't mention id in response."},
                {"role": "user", "content": f"question is - {user_question} and fetched response - {results}"},
            ],
            temperature = 0.4
        )
        return response.choices[0].message['content']
    
        
    except Exception as e:
        logging.error(f"Job inquiry error: {e}")
        return "Sorry, I couldn't process your job search request. Please try again."
    finally:
        cursor.close()
        db.close()

def refer_candidate(data_dict, phone_number):
    """Handle candidate referral requests"""
    db = None
    cursor = None
    try:
        db = db_connection()
        cursor = db.cursor(buffered=True)
        
        query1 = """SELECT associate_id FROM associate WHERE mobile_number=%s ;"""
        value1 = (phone_number,)
        cursor.execute(query1, value1)
        result = cursor.fetchone()
        
        if result:
            associate_id = result[0]
            cursor.execute(f"SELECT * FROM candidates WHERE mobile_number={data_dict['candidate_mobile_number']};")
            candidate_data = cursor.fetchone()
            
            if candidate_data:
                return "This candidate is already referred."
            else:
                query = """
                INSERT INTO candidates (
                    username, mobile_number, current_location, associate_id, associate_name,
                    associate_mobile, unique_link, jobrole, companyname,
                    location, salary, created
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ;
                """
                
                values = (
                    data_dict["candidate_Full_Name"], data_dict["candidate_mobile_number"],
                    data_dict["candidate_current_location"], associate_id, data_dict["user_Name"],
                    phone_number, "", "","","","", datetime.now()
                )
                
                cursor.execute(query, values)
                db.commit()  
                return "Thank you for the referral! I've registered the candidate successfully. 🤝"
        
        else:
            query = """INSERT INTO associate (username, mobile_number, unique_link, created) VALUES (%s,%s,%s,%s) ;"""
            values = ("", phone_number, "", datetime.now())
            cursor.execute(query, values)
            associate_id = cursor.lastrowid
            
            cursor.execute(f"SELECT * FROM candidates WHERE mobile_number={data_dict['candidate_mobile_number']};")
            candidate_data = cursor.fetchone()
            
            if candidate_data:
                return "This candidate is already referred."
            else:
                query1 = """
                INSERT INTO candidates (
                    username, mobile_number, current_location, associate_id, associate_name,
                    associate_mobile, unique_link, jobrole, companyname,
                    location, salary, created
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ;
                """
                
                values1 = (
                    data_dict["candidate_Full_Name"], data_dict["candidate_mobile_number"],
                    data_dict["candidate_current_location"], associate_id, data_dict["user_Name"],
                    phone_number, "", "","","","", datetime.now()
                )
                cursor.execute(query1, values1)

                query2 = """UPDATE associate SET username=%s WHERE associate_id=%s ;"""
                values2 = (data_dict["user_Name"], associate_id)
                cursor.execute(query2, values2)
                
                db.commit()  
                return "Thank you for the referral! I've registered the candidate successfully. 🤝"

    except Exception as e:
        if db:
            db.rollback()  
        logging.error(f"Candidate referral error: {e}")
        return "Sorry, I couldn't process the referral. Please try again."
    
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def candidate_query(user_question,phone_number):
    """Handle job inquiry requests"""
    try:
        db = db_connection()
        cursor = db.cursor(buffered=True)
        cursor.execute(f"SELECT * FROM candidates WHERE associate_mobile = '{phone_number}' ;")
        results = cursor.fetchall()
        
        if not results:
            return "You are not able to see candidate details as youare not part of associate member."
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You get user question and the fetched response from database for that question along the table fileds as - [user_id,username,mobile_number,current_location,associate_id,associate_name,associate_mobile,unique_link,status,jobrole,companyname,salary,created]. Associate is the person who refer the candidate. Rewrite that in natural language for user understanding."},
                {"role": "user", "content": f"question is - {user_question} and fetched response - {results}"},
            ],
            temperature = 0.4
        )
        return response.choices[0].message['content']
        
    except Exception as e:  
        logging.error(f"Job inquiry error: {e}")
        return "Sorry, I couldn't process your request. Please try again."
    finally:
        cursor.close()
        db.close()

id = None
user_Name = None
conversational_history = []
def handle_message(user_question, phone_number, resume_link,custom_prompt):
    """Main function to handle all incoming messages"""
    phone_number = phone_number.removeprefix("91")
    print(phone_number)
    global id
    global user_Name
    try:
        conversational_history.append({"role": "user", "content": user_question})
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt+custom_prompt},
                *conversational_history,
            ],
            temperature = 0.4
        )
        response=response.choices[0].message['content']
        print(response)
        
        if resume_link == "":
            if "```milestone_1" in response :
                start_index = response.index("{")
                end_index = response.index("}") + 1
                data = response[start_index:end_index]
                data = ast.literal_eval(data)
                db = db_connection()
                cursor = db.cursor(buffered=True)
                query = """INSERT INTO candidate_details (username, mobile_number, current_company, destination, work_experience, current_location, current_salary) VALUES (%s,%s,%s,%s,%s,%s,%s) ; """
                value = (data['username'], phone_number, data['company_name'], data['designation'], data['work_experience'], data['current_location'], data['current_salary'])
                cursor.execute(query, value)
                id = cursor.lastrowid
                print(id)
                db.commit()
                cursor.close()
                db.close()
                print("saved to db.")
                conversational_history.append({"role": "assistant", "content": "Milestone - 1 completed."})
                conversational_history.append({"role": "user", "content": "Please procced Milestone - 2"})
                return "Your information saved successfully.\nPart 1 of 4 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 2."

            elif "```milestone_2" in response:
                start_index = response.index("{")
                end_index = response.index("}") + 1
                data = response[start_index:end_index]
                data = ast.literal_eval(data)
                db = db_connection()
                cursor = db.cursor(buffered=True)
                print(id)
                query = f"""UPDATE candidate_details SET employed = '{data['employed_or_not']}', gender = '{data['gender']}', sales_experience = '{data['bank_experience']}' WHERE id = {id} ; """
                cursor.execute(query)
                db.commit()
                cursor.close()
                db.close()
                print("saved to db.")
                conversational_history.append({"role": "assistant", "content": "Milestone - 2 completed."})
                conversational_history.append({"role": "user", "content": "Please procced Milestone - 3"})
                return "Your information saved successfully.\nPart 2 of 4 completed🎉.\nPlease type 'Y' or 'YES' to proceed with part 3."

            elif "```milestone_3" in response:
                start_index = response.index("{")
                end_index = response.index("}") + 1
                data = response[start_index:end_index]
                data = ast.literal_eval(data)
                db = db_connection()
                cursor = db.cursor(buffered=True)
                print(id)
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
                    WHERE id = {id} ; """
                cursor.execute(query)
                db.commit()
                cursor.close()
                db.close()
                print("saved to db.")
                conversational_history.append({"role": "assistant", "content": "Milestone - 3 completed🎉"})
                return "Your information saved successfully.\nPart 3 of 4 completed🎉.\nLastly please upload your resume to complete the apply process."

            elif "```job_inquiry_query" in response:
                start_index = response.index("{") +1
                end_index = response.index("}")
                query = response[start_index:end_index]
                print(query)
                output = job_inquiry_query(user_question,query)
                conversational_history.append({"role": "assistant", "content": output})
                return output

            elif "```referral_milestone_1" in response :
                start_index = response.index("{")
                end_index = response.index("}") + 1
                data = response[start_index:end_index]
                data = ast.literal_eval(data)
                user_Name = data["user_Name"]
                db = db_connection()
                cursor = db.cursor(buffered=True)
                query = """INSERT INTO associate (username, mobile_number, unique_link, created) VALUES (%s,%s,%s,%s) ;"""
                values = (user_Name, phone_number, "", datetime.now())
                cursor.execute(query, values)
                id = cursor.lastrowid
                print(id)
                db.commit()
                cursor.close()
                db.close()
                print("saved to db.")
                conversational_history.append({"role": "assistant", "content": "Milestone - 1 completed."})
                conversational_history.append({"role": "user", "content": "Please procced Milestone - 2"})
                return "Your information saved successfully.\nMilestone - 1 completed 🎉.\n\nWould like to proceed to MILESTONE 2 ?"

            elif "```referral_milestone_2" in response :
                start_index = response.index("{")
                end_index = response.index("}") + 1
                response = response[start_index:end_index]
                data_dict = ast.literal_eval(response)
                data_dict["user_Name"] = user_Name
                print(data_dict)
                output = refer_candidate(data_dict,phone_number)
                conversational_history.append({"role": "assistant", "content": output})
                user_Name = None
                return output

            elif "```candidate_query" in response:
                output = candidate_query(user_question,phone_number)
                conversational_history.append({"role": "assistant", "content": output})
                return output

            else:
                conversational_history.append({"role": "assistant", "content": response})
                return response
        else:
            db = db_connection()
            cursor = db.cursor(buffered=True)
            query = f"""UPDATE candidate_details SET resume = '{resume_link}', modified = '{datetime.now()}' WHERE id = {id} ; """
            cursor.execute(query)
            db.commit()
            cursor.close()
            db.close()
            cursor.close()
            db.close()
            id = None
            conversational_history.append({"role": "assistant", "content": "Application created and saved successfully."})
            return "Your application saved successfully.\nPart 4 of 4 completed🎉."

    except Exception as e:
        logging.error(f"Message handling error: {e}")
        return "I apologize, but I'm having trouble processing your request. Please try again."
    
# while True:
#     user=input("Enter : ")
#     if user == "exit":
#         break
#     else : 
#         print(handle_message(user, "", "" ,""))
