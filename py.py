import time
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Set up Selenium WebDriver with headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open the recipes page
driver.get("https://www.simplyrecipes.com/recipes-5090746")
wait = WebDriverWait(driver, 10)
wait.until(EC.presence_of_element_located((By.ID, "taxonomysc_1-0")))

# Scroll to the bottom of the page to trigger lazy loading
last_height = driver.execute_script("return document.body.scrollHeight")
while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)  # Allow time for content to load
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

# Get the page source after all content is loaded
page_source = driver.page_source

# Close the browser
driver.quit()

# Parse the page source with BeautifulSoup
soup = BeautifulSoup(page_source, "html.parser")

# Find all product elements
product_elements = soup.find_all("a", class_="mntl-card-list-items")

# Extract product details
data = []
for product in product_elements:
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract item_url
        item_url = product.get("href", "N/A")  # Get the href attribute
        
        # Extract title
        title_element = product.find("span", class_="card__title-text")
        title = title_element.text.strip() if title_element else "N/A"
        
        data.append([item_url, title, timestamp])
    except Exception as e:
        print(f"Error extracting product: {e}")

# Save data to CSV
csv_file = "all_recipes.csv"
header = ["item_url", "title", "timestamp"]

with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    if file.tell() == 0:
        writer.writerow(header)  # Write header only if file is empty
    writer.writerows(data)

print(f"Scraped {len(data)} products and saved to {csv_file}.")