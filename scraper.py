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
import concurrent.futures

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Added user agent and window size
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def extract_recipe_details(item_url):
    driver = init_driver()
    result = {
        "ingredients": "N/A",
        "publish_date": "N/A",
        "nutrition_facts": "N/A"
    }
    
    try:
        print(f"\nProcessing: {item_url}")
        driver.get(item_url)
        wait = WebDriverWait(driver, 20)
        
        # Extract ingredients
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.structured-ingredients__list")))
            ingredients_list = driver.find_elements(By.CSS_SELECTOR, "ul.structured-ingredients__list li")
            ingredients = [item.text.strip() for item in ingredients_list if item.text.strip()]
            result["ingredients"] = ", ".join(ingredients) if ingredients else "N/A"
        except Exception as e:
            print(f"Ingredients not found: {str(e)}")
        
        # Extract publish date
        try:
            publish_date = driver.find_element(By.CSS_SELECTOR, "div.mntl-attribution__item-date").text.strip()
            result["publish_date"] = publish_date
        except Exception as e:
            print(f"Publish date not found: {str(e)}")
        
        # Extract nutrition facts
        try:
            # Scroll to nutrition button
            nutrition_button = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.nutrition-modal-label-container"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", nutrition_button)
            time.sleep(1)
            
            # Click using JavaScript
            driver.execute_script("arguments[0].click();", nutrition_button)
            
            # Wait for modal
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.nutrition-label")))
            time.sleep(1)
            
            # Extract nutrition data
            nutrition_rows = driver.find_elements(By.CSS_SELECTOR, "div.nutrition-label tbody tr")
            nutrition_data = []
            
            for row in nutrition_rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    nutrient = cells[0].text.strip()
                    value = cells[1].text.strip()
                    if nutrient and value:
                        nutrition_data.append(f"{nutrient}: {value}")
            
            result["nutrition_facts"] = ", ".join(nutrition_data) if nutrition_data else "N/A"
            
            # Close modal
            try:
                close_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
                close_button.click()
            except:
                pass
                
        except Exception as e:
            print(f"Nutrition facts not available: {str(e)}")
            
    except Exception as e:
        print(f"Error processing recipe: {str(e)}")
    finally:
        driver.quit()
        return result

def main():
    driver = init_driver()
    try:
        print("Loading main recipes page...")
        driver.get("https://www.simplyrecipes.com/recipes-5090746")
        
        # Wait for recipes to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.mntl-card-list-items"))
        )
        
        print("Scrolling to load all recipes...")
        scroll_pause_time = 2
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        print("Extracting recipe links...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        recipe_cards = soup.find_all("a", class_="mntl-card-list-items", href=True)
        print(f"Found {len(recipe_cards)} recipe cards")
        
        if not recipe_cards:
            print("No recipe cards found - check if page structure changed")
            return
        
        data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            for card in recipe_cards:
                try:
                    item_url = card["href"]
                    if not item_url.startswith("http"):
                        continue
                        
                    # Extract basic info from card
                    title = card.find("span", class_="card__title-text")
                    title = title.text.strip() if title else "N/A"
                    
                    cooking_time = card.find("span", class_="meta-text__text")
                    cooking_time = cooking_time.text.strip() if cooking_time else "N/A"
                    
                    category = card.find("div", class_="card__content")
                    category = category.get("data-tag", "N/A") if category else "N/A"
                    
                    futures.append((
                        item_url,
                        title,
                        cooking_time,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        category,
                        executor.submit(extract_recipe_details, item_url)
                    ))
                except Exception as e:
                    print(f"Error processing card: {str(e)}")
            
            print("\nProcessing recipe details...")
            for i, (item_url, title, cooking_time, timestamp, category, future) in enumerate(futures, 1):
                try:
                    details = future.result()
                    row = [
                        item_url,
                        details.get("title", title),
                        cooking_time,
                        timestamp,
                        category,
                        details["ingredients"],
                        details["publish_date"],
                        details["nutrition_facts"]
                    ]
                    data.append(row)
                    print(f"{i}/{len(futures)}: {title}")
                except Exception as e:
                    print(f"Error getting results: {str(e)}")
        
        # Save to CSV
        csv_file = "recipes.csv"
        header = [
            "URL", "Title", "Cooking Time", "Timestamp",
            "Category", "Ingredients", "Publish Date", "Nutrition Facts"
        ]
        
        with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(data)
        
        print(f"\nSuccessfully saved {len(data)} recipes to {csv_file}")
    
    except Exception as e:
        print(f"Main function error: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()