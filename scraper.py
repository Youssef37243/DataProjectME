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
        
        # Extract category
        category_element = product.find("div", class_="card__content")
        category = category_element.get("data-tag", "N/A") if category_element else "N/A"

        # Extract ingredients, nutrition facts, and publish dates from the item URL
        ingredients = ["N/A"]
        nutrition_facts = {"N/A": "N/A"}
        publish_dates = ["N/A"]
        cooking_time = "N/A"

        if item_url != "N/A":
            try:
                # Open the item URL in a new tab
                driver.execute_script(f"window.open('{item_url}', '_blank');")
                driver.switch_to.window(driver.window_handles[1])  # Switch to the new tab

                # Wait for the ingredients section to load
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "structured-ingredients__list")))

                # Extract Ingredients
                try:
                    ingredients = [
                        elem.text.strip()
                        for elem in driver.find_elements(By.CLASS_NAME, "structured-ingredients__list-item")
                    ]
                except:
                    ingredients = ["N/A"]

                # Extract nutrition facts
                try:
                    nutrition_facts = {}
                    # Wait for the nutrition section to load
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "nutritional-guidelines-block")))
                    nutrition_section = driver.find_element(By.CLASS_NAME, "nutritional-guidelines-block")
                    
                    # Extract summary nutrition table
                    summary_table = nutrition_section.find_element(By.CLASS_NAME, "nutrition-info__table--body")
                    if summary_table:
                        rows = summary_table.find_elements(By.CLASS_NAME, "nutrition-info__table--row")
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) == 2:
                                key = cells[1].text.strip()  # Nutrient name
                                value = cells[0].text.strip()  # Nutrient value
                                nutrition_facts[key] = value

                    # Extract detailed nutrition table
                    detailed_table = nutrition_section.find_element(By.CLASS_NAME, "nutrition-label")
                    if detailed_table:
                        rows = detailed_table.find_elements(By.TAG_NAME, "tr")
                        for row in rows:
                            nutrient_tag = row.find_element(By.TAG_NAME, "th")
                            if nutrient_tag:
                                nutrient_name = nutrient_tag.text.strip()
                                value = row.text.replace(nutrient_name, "").strip()  # Remove name to get value
                                nutrition_facts[nutrient_name] = value
                except:
                    nutrition_facts = {"N/A": "N/A"}

                # Extract publish dates
                try:
                    publish_dates = [
                        elem.text.strip()
                        for elem in driver.find_elements(By.CLASS_NAME, "mntl-attribution__item-date")
                    ]
                except:
                    publish_dates = ["N/A"]

                # Extract cooking time
                try:
                    cooking_time_element = driver.find_element(By.CSS_SELECTOR, "span.meta-text__text")
                    cooking_time = cooking_time_element.text.strip() if cooking_time_element else "N/A"
                except:
                    cooking_time = "N/A"

                # Close the tab and switch back to the main window
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            except Exception as e:
                print(f"Error extracting details from {item_url}: {e}")
                # Close the tab and switch back to the main window in case of an error
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

        # Append data
        data.append([item_url, title, ingredients, cooking_time, nutrition_facts, publish_dates, timestamp, category])
    except Exception as e:
        print(f"Error extracting product: {e}")

# Close the browser
driver.quit()

# Save data to CSV
csv_file = "all_recipes.csv"
header = ["item_url", "title", "ingredients", "cooking_time", "nutrition_facts", "publish_dates", "timestamp", "category"]

with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    if file.tell() == 0:
        writer.writerow(header)  # Write header only if file is empty
    writer.writerows(data)

print(f"Scraped {len(data)} products and saved to {csv_file}.")