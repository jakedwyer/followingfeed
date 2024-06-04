from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import pickle
import time

def init_driver():
    options = Options()
    # We remove the headless option to allow for manual interaction with the browser
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)  # Gives an implicit wait for 10 seconds
    return driver

def manual_login(driver, url):
    # Navigate to the login page
    driver.get(url)
    input("Please log in manually in the browser window and press Enter here once you're done...")

def save_cookies(driver, path):
    # Save the cookies to a pickle file
    cookies = driver.get_cookies()
    with open(path, "wb") as file:
        pickle.dump(cookies, file)
    print(f"Cookies have been saved to {path}.")

def main():
    # Initialize the WebDriver
    driver = init_driver()

    # URL to login page, adjust as needed
    login_url = "https://example.com/login"
    
    # Manual login process
    manual_login(driver, login_url)

    # Wait a little to ensure all cookies are loaded
    time.sleep(5)

    # Save cookies to a file
    save_cookies(driver, "cookies.pkl")

    # Close the browser
    driver.quit()

if __name__ == "__main__":
    main()
