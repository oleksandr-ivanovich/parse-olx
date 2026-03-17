import asyncio
import json
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="olx_premium_map_parser_v5")

# Офіційні короткі коди областей OLX
REGIONS = {
    "vin": "Вінницька область",
    "vol": "Волинська область",
    "dnp": "Дніпропетровська область",
    "don": "Донецька область",
    "zht": "Житомирська область",
    "zak": "Закарпатська область",
    "zap": "Запорізька область",
    "if": "Івано-Франківська область",
    "ko": "Київська область",
    "kr": "Кіровоградська область",
    "lug": "Луганська область",
    "lv": "Львівська область",
    "nik": "Миколаївська область",
    "od": "Одеська область",
    "pol": "Полтавська область",
    "rov": "Рівненська область",
    "sum": "Сумська область",
    "ter": "Тернопільська область",
    "khr": "Харківська область",
    "khe": "Херсонська область",
    "khm": "Хмельницька область",
    "chk": "Черкаська область",
    "chn": "Чернігівська область",
    "chv": "Чернівецька область"
}

# Кроки по ціні (від і до) з оновленим лімітом до 16 000
PRICE_RANGES = [
    (0, 5000),
    (5000, 7000),
    (7000, 9500),
    (9500, 11500),
    (11500, 16000)
]

def get_coords(address):
    try:
        location = geolocator.geocode(f"{address}, Україна", timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Помилка геокодування для {address}: {e}", flush=True)
        return None, None

async def parse_olx_premium():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        results = []
        coords_cache = {}
        seen_links = set()
        
        for region_slug, region_name in REGIONS.items():
            for price_min, price_max in PRICE_RANGES:
                current_page = 1
                
                print(f"\n=== Починаю: {region_name} | {price_min}$-{price_max}$ ===", flush=True)
                
                while True:
                    # Динамічний URL з областю, ціновим діапазоном та пагінацією
                    url = f"https://www.olx.ua/uk/nedvizhimost/doma/prodazha-domov/{region_slug}/?currency=USD&search%5Border%5D=created_at:desc&search%5Bfilter_float_price:from%5D={price_min}&search%5Bfilter_float_price:to%5D={price_max}&page={current_page}"
                    
                    print(f"-> Завантажую сторінку {current_page}", flush=True)
                    
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2) # Захист від блокування
                    except Exception as e:
                        print(f"Помилка завантаження сторінки: {e}. Пропускаю.", flush=True)
                        break

                    try:
                        empty_state = await page.query_selector('[data-testid="empty-state"]')
                        if empty_state:
                            print("Оголошень у цьому діапазоні немає.", flush=True)
                            break
                            
                        await page.wait_for_selector('div[data-cy="l-card"]', timeout=10000)
                    except Exception:
                        print("Картки не знайдено або таймаут. Перехід до наступного блоку.", flush=True)
                        break

                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    listings = soup.select('div[data-cy="l-card"]')

                    if not listings:
                        break

                    for item in listings:
                        link_el = item.select_one('a')
                        if not link_el: continue

                        link = link_el['href']
                        if link.startswith('/'): link = "https://www.olx.ua" + link

                        if link in seen_links: continue
                        seen_links.add(link)

                        title_el = item.select_one('h4') or item.select_one('h6') or item.select_one('div[data-cy="ad-title"]')
                        price_el = item.select_one('[data-testid="ad-price"]')
                        location_el = item.select_one('[data-testid="location-date"]')

                        title = title_el.get_text(strip=True) if title_el else "Без назви"
                        price = price_el.get_text(separator=" ", strip=True) if price_el else "Ціна не вказана"
                        location_full = location_el.get_text(strip=True) if location_el else "Невідомо"
                        
                        village = location_full.split(' - ')[0] if ' - ' in location_full else location_full
                        
                        full_address = f"{village}, {region_name}"

                        if full_address in coords_cache:
                            lat, lng = coords_cache[full_address]
                        else:
                            lat, lng = get_coords(full_address)
                            coords_cache[full_address] = (lat, lng)
                            time.sleep(1.1)

                        if lat and lng:
                            results.append({
                                "title": title,
                                "price": price,
                                "location": f"{village} ({region_name})",
                                "lat": lat,
                                "lng": lng,
                                "link": link
                            })

                    next_button = soup.select_one('[data-cy="pagination-forward"]')
                    if not next_button:
                        break

                    current_page += 1
                
                # Даємо більшу паузу перед зміною цінового діапазону
                await asyncio.sleep(5)

            # Проміжне збереження після проходження всіх цін в одній області
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"--- Проміжне збереження: зібрано {len(results)} карток ---", flush=True)

        print(f"Готово! Фінальний результат: {len(results)} унікальних карток.", flush=True)
        await browser.close()

asyncio.run(parse_olx_premium())
