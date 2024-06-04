from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument('--no-sandbox')  # Necessary for running as root
options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
options.add_argument('--headless')  # Optional, for headless operation

# Specify the path to the Chrome binary

# Initialize ChromeDriver using webdriver-manager to handle driver setup
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Example operation: open Google and print the title
driver.get("http://www.google.com")
print(driver.title)  # Prints the title of the webpage
driver.quit()
