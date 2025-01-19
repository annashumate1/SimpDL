import time
from selenium.webdriver.common.by import By

def login_to_simpcity(driver, username, password):
    print("Logging in...")
    username_field = driver.find_element(By.NAME, "login")
    password_field = driver.find_element(By.NAME, "password")
    login_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'button--primary')]")
    username_field.send_keys(username)
    password_field.send_keys(password)
    login_button.click()
    time.sleep(3)
    print("Login successful.")
