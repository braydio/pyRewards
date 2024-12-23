from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from time import sleep
import os
import re
import time



# File path to the text file
file_path = 'rewards_log.txt'
report_path = 'rewards_report.txt'
card_base_xpath = '/html/body/div[1]/div[2]/main/div/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group[1]/div/mee-card[{}]/div/card-content/mee-rewards-daily-set-item-content/div/a'
base_points_xpath = '/html/body/div[1]/div[2]/main/div/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group[1]/div/mee-card[{}]/div/card-content/mee-rewards-daily-set-item-content/div/a/mee-rewards-points/div/div/span[1]'
alt_base_xpath = '//*[@id="more-activities"]/div/mee-card[{}]/div/card-content/mee-rewards-more-activities-card-item/div/a'
alt_points_xpath = '//*[@id="more-activities"]/div/mee-card[{}]/div/card-content/mee-rewards-more-activities-card-item/div/a/mee-rewards-points/div/div/span[1]'

def filter_lines(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    filtered_lines = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("**Rewards summary") or lines[i].startswith("Streak"):
            filtered_lines.append(lines[i])
            if lines[i].startswith("Streak") and i + 1 < len(lines):
                filtered_lines.append(lines[i + 1])
                i += 1
        i += 1

    with open(file_path, 'w') as file:
        file.writelines(filtered_lines)

    print(f"Cleaned text file log: {file_path}.")

# Run the function
filter_lines(file_path)

# Set up the Edge WebDriver in headless mode
options = Options()
options.add_argument("--headless")  # Enable headless mode
options.add_argument("--disable-gpu")  # Disable GPU in headless mode (Optional, but can help)
options.use_chromium = True

# Initialize the WebDriver
driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)
# driver = webdriver.Edge(service=service, options=options)

def log_to_file(message):
    now = datetime.now().strftime('%H:%M')
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(f'{now} - {message}\n')
        print(f'{message}\n')

def open_text_file():
    # file_path = file_path
    try:
        os.startfile(file_path)  # Open the file with the default text editor
        log_to_file(f'Opened file at: {file_path}')
    except Exception as e:
        log_to_file(f'Error opening file: {e}')

def collecting_points(card_xpath, card_number):
    try:
        card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, card_xpath))
        )
        card.click()
        card_href = card.get_attribute('href')

        skip_card = 'Redeem now'
        aria_label = card.get_attribute('aria-label')

        log_to_file(f'Processing card {card_number} with label: {aria_label}')
        # Check if "Supersonic quiz" is in the aria-label
        if "Supersonic quiz" in aria_label:
            print("quiz found, starting quiz")
            # start_quiz(card_xpath)
            # Call take_quiz() if it's a Supersonic quiz
        elif skip_card in aria_label:
            log_to_file(f'Skipping card {card_number} due to skip_card variable.')
        elif card_href:
            # Otherwise, click the card and collect points
            log_to_file(f'Clicked {card_href}')
            card.click()
            sleep(2)
            driver.refresh()
        else:
            print("No href found.")
            card.click()
            log_to_file(f'Clicking card {card_number}.')
            sleep(2)
            driver.refresh()

        sleep(2)

    except Exception as e:
        log_to_file(f'Error with card {card_number}: {e}.')

def card_status_check(card_number, xpath_ind):

    rightNow = datetime.now().strftime('%B %d, %Y')    
    # points_base_xpath = 
    xpath = base_points_xpath.format(card_number)
    print(xpath_ind)
    if xpath_ind == "Activities":
        xpath = alt_points_xpath.format(card_number)
    
    points_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element_class = points_element.get_attribute('class')
    log_to_file(f"Points element class for card {card_number}: {element_class}")
    
    if 'mee-icon-SkypeCircleCheck' in element_class:
        log_to_file(f'Points collected for card {xpath_ind} - {card_number}.')
        return(f"Collected - {rightNow}")
    elif 'mee-icon mee-icon-AddMedium' in element_class:
        log_to_file(f'Unable to verify status for card number {card_number} as {element_class}.')
        return(element_class)
    else:
        log_to_file(f'Other value in points field')
        return("No field")
    
def get_card_state(card_number, xpath_ind):
    try:
        todayNow = datetime.now().strftime('%B %d, %Y')

        check_card = card_status_check(card_number, xpath_ind)
        card_state = (card_number, check_card)
        print(card_state)

        card_xpath = card_base_xpath.format(card_number)
        
        if xpath_ind == "Activities":
            print("Not daily set")
            card_xpath = alt_base_xpath.format(card_number)
            print(f"Card xpath: {card_xpath}")

        print(card_xpath)

        # Access the check_card value from the tuple
        status = card_state[1]  
        print(status, card_number)

        card_passed = f"Collected - {todayNow}"
        not_passed = 'mee-icon mee-icon-AddMedium'
        no_field = 'No field'

        if status == not_passed:
            points = collecting_points(card_xpath, card_number)
            log_to_file(f"This number is {points}")
            sleep(2)
            return status
        elif status == card_passed:
            # collecting_points(card_xpath, card_number)
            log_to_file(f"Card {xpath_ind} {card_number} passed with status {status}")
            return status
        else:
            log_to_file(f"Status for {xpath_ind} {card_number}: {status}, next card.")
            return status
    except Exception as e:
        log_to_file(f"Error of {e}")

def start_quiz(card_xpath):
    try:
        card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, card_xpath))
        )
        card.click()
        log_to_file(f'Card clicked. Checking for quiz window.')

        sleep(2)
        driver.switch_to.window(driver.window_handles[-1])

        quiz_button_xpath = '//*[@id="rqStartQuiz"]'
        quiz_active_element_xpath = '//*[@id="rqHeaderCredits"]'

        try:
            quiz_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, quiz_button_xpath))
            )
            log_to_file(f"Quiz start button found: {quiz_button_xpath}")
            quiz_button.click()
            log_to_file("Start quiz button clicked.")
            sleep(3)
        except Exception as e:
            log_to_file(f"Start quiz button not found - is the quiz already started?")

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, quiz_active_element_xpath))
            )
            log_to_file("Quiz is already active.")
            sleep(1)
            take_quiz()
        except Exception as e:
            log_to_file(f"I don't think there is a quiz here...")
            # If the quiz is not found, you might want to handle this case

    except Exception as e:
        log_to_file(f'Start_quiz function not successful: {e}')
    finally:
        driver.switch_to.window(driver.window_handles[0])

def get_streak_count():
    try:
        streak_xpath = '/html/body/div[1]/div[2]/main/div/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-rewards-streak/div'
        streak_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, streak_xpath))
        )
        aria_label = streak_element.get_attribute('aria-label')
        match = re.search(r"(\d+), Current day streak", aria_label)
        return int(match.group(1)) if match else 0
    except Exception as e:
        log_to_file(f"Error while checking streak count: {e}")
        return 0

def take_quiz():
    log_to_file('Starting the quiz.')

    option_xpaths = [
        '//*[@id="rqAnswerOption0"]',
        '//*[@id="rqAnswerOption1"]',
        '//*[@id="rqAnswerOption2"]'
    ]
    quiz_complete_xpath = '//*[@id="quizCompleteContainer"]'

    try:
        # Get the current question number
        current_question = get_current_question()
        if current_question is None:
            log_to_file('Could not retrieve the current question. Exiting quiz.')
            return

        target_question = current_question + 1  # Set target question to current question + 1
        log_to_file(f'Current question number: {current_question}, Target question number: {target_question}')

        while True:
            # Check if the quiz is completed
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, quiz_complete_xpath))
                )
                log_to_file('Quiz is completed.')
                return  # Exit the function
            except:
                pass  # Continue checking if the element is not found

            target_question = current_question + 1  # Set target question to current question + 1
            log_to_file(f'Current question number: {current_question}, Target question number: {target_question}')

            # Click on each option and check if we have moved to the next question
            for option_xpath in option_xpaths:
                click_option(option_xpath)
                new_question = get_current_question()

                if new_question is None:
                    log_to_file('Could not retrieve the new question state. Exiting quiz.')
                    return

                if new_question == target_question:
                    log_to_file(f'Correct answer found. Moving to the next question.')
                    break
                else:
                    log_to_file(f'Option {option_xpath} was incorrect. Trying next option.')

            # Check if we've reached the target question
            if new_question == target_question:
                log_to_file(f'Waiting for the next question.')
                # Update target question to the next one
                current_question = new_question
                target_question = current_question + 1
            else:
                log_to_file(f'Unable to find the correct answer for question {current_question}. Exiting quiz.')
                break

    except Exception as e:
        log_to_file(f'Error during take_quiz: {e}')
    
    finally:
        driver.switch_to.window(driver.window_handles[0])

def click_option(option_xpath):
    """Clicks an answer option based on the provided XPath."""
    try:
        option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, option_xpath))
        )
        option.click()
        log_to_file(f'Clicked option: {option_xpath}')
        time.sleep(2)  # Optional: wait after clicking
    except Exception as e:
        log_to_file(f'Error clicking option {option_xpath}: {e}')
    
def get_current_question():
    """Counts the filled circles to determine the current question number."""
    filled_circle_xpath = '//*[@id="rqHeaderCredits"]/span[contains(@class, "filledCircle")]'
    
    try:
        filled_circles = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, filled_circle_xpath))
        )
        return len(filled_circles)
    except Exception as e:
        log_to_file(f'Error retrieving current question state: {e}')
        return None

def main():
    todayNow = datetime.now().strftime('%B %d, %Y')
    log_to_file("Initializing...")

    try:
        driver.get('https://rewards.microsoft.com/')
        log_to_file(f'Navigated to Microsoft. Getting initial streak count.')

        initial_streak_count = get_streak_count()
        log_to_file(f"Initial streak count: {initial_streak_count}")

        with open(file_path, 'a') as file:
            file.write(f'**Rewards summary for {todayNow}:**\n')

        for card_number in range(1, 4):
            log_to_file(f"Processing card number {card_number}.")
            points_check = get_card_state(card_number, "Daily Set")
            print(card_number, points_check)

            card_passed = f"Collected - {todayNow}"

            if points_check == card_passed:
                log_to_file(f"Card {card_number} - Points {card_passed}")
            else:    
                log_to_file(f"Running points collection again for card {card_number} and checking for quiz.")
                card_xpath = card_base_xpath.format(card_number)
                
                points = collecting_points(card_xpath, card_number)
                start_quiz(card_xpath)
                
                log_to_file(f"Quiz checked, resulting points: {points}.")
                sleep(2)

        final_streak_count = get_streak_count()
        log_to_file(f"Final streak count: {final_streak_count}")

        for alt_card_number in range(2, 20):
                print("Daily set complete, running activities...")
                print(f"Alt card number {alt_card_number}")
                alt_points_check = get_card_state(alt_card_number, "Activities")
                print(alt_card_number, alt_points_check)

        with open(file_path, 'a') as file:
            file.write(f'Streak count: {final_streak_count}.\n')

        if final_streak_count > initial_streak_count:
            log_to_file("Streak count updated!")
        else:
            log_to_file("Streak count not updated.")
            for card_number in range(1, 4):
                card_xpath = card_base_xpath.format(card_number)
                # start_quiz(card_xpath)
                sleep(2)
            for alt_card_number in range(2, 20):
                print("Daily set complete, running activities...")
                print(f"Alt card number {alt_card_number}")
                alt_points_check = get_card_state(alt_card_number, "Activities")
                print(alt_card_number, alt_points_check)
        filter_lines(file_path)
        
    except Exception as e:
        log_to_file(f'Error in main: {e}')
    finally:
        driver.quit()
        log_to_file(f'WebDriver quit.')
        open_text_file()

if __name__ == '__main__':
    main()
