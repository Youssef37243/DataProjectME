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
import pandas as pd

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def extract_recipe_details(item_url):
    driver = init_driver()
    result = {
        "ingredients": "Ingredients not found",
        "publish_date": "Unknown publish date",
        "nutrition_facts": "Nutrition Facts not found"
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
            result["ingredients"] = ", ".join(ingredients) if ingredients else "Ingredients not found"
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
            nutrition_button = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.nutrition-modal-label-container"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", nutrition_button)
            time.sleep(1)
            
            driver.execute_script("arguments[0].click();", nutrition_button)
            
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.nutrition-label")))
            time.sleep(1)
            
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

def get_category_links(driver):
    print("Extracting category links...")
    try:
        # Wait for the categories container to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.mntl-taxonomysc-child-block__links"))
        )
        
        category_links = []
        category_elements = driver.find_elements(By.CSS_SELECTOR, "div.mntl-taxonomysc-child-block__links a")[:5]
        
        for element in category_elements:
            href = element.get_attribute("href")
            text = element.text.strip()
            if href and href.startswith("https://www.simplyrecipes.com/"):
                category_links.append((text, href))
                print(f"Found valid category: {text} -> {href}")
        
        print(f"Total categories to process: {len(category_links)}")
        return category_links
    
    except Exception as e:
        print(f"Error extracting categories: {str(e)}")
        return []

def extract_recipes_from_category(driver, category_name, category_url):
    """Extract ALL recipes from a single category page"""
    print(f"\nProcessing category: {category_name} ({category_url})")
    try:
        driver.get(category_url)
        time.sleep(2)  # Additional wait for category page to load
        
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
        print(f"Found {len(recipe_cards)} recipes in {category_name}")
        
        recipes_data = []
        if not recipe_cards:
            print(f"No recipes found in category {category_name}")
            return recipes_data
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            for card in recipe_cards:
                try:
                    item_url = card["href"]
                    if not item_url.startswith("https://www.simplyrecipes.com/"):
                        continue
                        
                    title = card.find("span", class_="card__title-text")
                    title = title.text.strip() if title else "Title not found"
                    
                    cooking_time = card.find("span", class_="meta-text__text")
                    cooking_time = cooking_time.text.strip() if cooking_time else "Unknown cooking time"
                    
                    futures.append((
                        item_url,
                        title,
                        cooking_time,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        category_name,
                        executor.submit(extract_recipe_details, item_url)
                    ))
                except Exception as e:
                    print(f"Error processing card: {str(e)}")
            
            print(f"\nProcessing recipe details for {category_name}...")
            for i, (item_url, title, cooking_time, timestamp, category, future) in enumerate(futures, 1):
                try:
                    details = future.result()
                    row = [
                        item_url,
                        title,
                        details["ingredients"],
                        cooking_time,
                        details["nutrition_facts"],
                        details["publish_date"],
                        timestamp,
                        category,
                    ]
                    recipes_data.append(row)
                    print(f"{i}/{len(futures)}: {title}")
                except Exception as e:
                    print(f"Error getting results: {str(e)}")
        
        return recipes_data
    
    except Exception as e:
        print(f"Error processing category {category_name}: {str(e)}")
        return []

def remove_duplicates(df):
    """
    Remove duplicate recipes based on title (case-insensitive comparison).
    Keeps the first occurrence of each unique recipe.
    
    Args:
        df: Pandas DataFrame containing recipe data
        
    Returns:
        DataFrame with duplicates removed
    """
    # Create lowercase version of titles for case-insensitive comparison
    df['title_lower'] = df['Title'].str.lower()
    
    # Identify duplicates (keeping first occurrence)
    duplicates_mask = df.duplicated(subset=['title_lower'], keep='first')
    
    # Count duplicates found
    duplicate_count = duplicates_mask.sum()
    if duplicate_count > 0:
        print(f"Removed {duplicate_count} duplicate recipes")
    
    # Filter out duplicates and clean up
    deduped_df = df[~duplicates_mask].copy()
    deduped_df.drop(columns=['title_lower'], inplace=True)
    
    return deduped_df

def main():
    driver = init_driver()
    all_data = []
    
    try:
        print("Loading main recipes page...")
        driver.get("https://www.simplyrecipes.com/recipes-5090746")
        time.sleep(3)  # Additional wait for page to stabilize
        
        # Get first 4 category links
        category_links = get_category_links(driver)
        if not category_links:
            print("No valid categories found - exiting")
            return
        
        # Process only the first 4 categories
        for category_name, category_url in category_links[:5]:  # Explicit slice for safety
            try:
                print(f"\n{'='*50}")
                print(f"Starting category: {category_name}")
                print(f"URL: {category_url}")
                print(f"{'='*50}")
                
                category_data = extract_recipes_from_category(driver, category_name, category_url)
                all_data.extend(category_data)
                
                print(f"\nCompleted category: {category_name}")
                print(f"Total recipes collected so far: {len(all_data)}")
            except Exception as e:
                print(f"\nFailed to process category {category_name}: {str(e)}")
                continue
        
        # Convert to DataFrame and remove duplicates
        header = [
            "URL", "Title", "Ingredients", "Cooking Time", "Nutrition Facts", 
            "Publish Date", "Timestamp", "Category"
        ]
        df = pd.DataFrame(all_data, columns=header)
        df = remove_duplicates(df)
        
        # Save cleaned data to CSV
        csv_file = "recipes_cleaned.csv"
        df.to_csv(csv_file, index=False)
        
        print(f"\n{'='*50}")
        print(f"Scraping complete!")
        print(f"Categories processed: 5")
        print(f"Unique recipes collected: {len(df)}")
        print(f"Saved to: {csv_file}")
        print(f"{'='*50}")
    
    except Exception as e:
        print(f"Main function error: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()