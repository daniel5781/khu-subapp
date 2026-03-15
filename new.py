from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time, os, csv, requests

# 저장 폴더 준비
os.makedirs("images", exist_ok=True)

driver = webdriver.Chrome()
driver.get("https://www.musinsa.com/snap/profile/snap?profile_id=1234627203913810064&snap_id=1309334824887322837")
time.sleep(3)

data = {}
last_idx = -1

while True:
    # 실제로 쓰이는 컨테이너 선택자
    snap_divs = driver.find_elements(By.CSS_SELECTOR, "div.gtm-impression-content[data-content-type='CODISHOP_SNAP']")
    for snap_div in snap_divs:
        idx = int(snap_div.get_attribute("data-index"))
        if idx <= last_idx:
            continue
        last_idx = idx
        data[idx] = {}

        # — 브랜드·시간 추출 (생략) —

        # ◾️ 이미지 슬라이드 안의 모든 <img> 가져와서 저장
        imgs = snap_div.find_elements(By.TAG_NAME, "img")
        img_paths = []
        for i, img in enumerate(imgs, start=1):
            url = img.get_attribute("src")
            try:
                r = requests.get(url, timeout=10); r.raise_for_status()
                path = f"images/{idx}_{i}.jpg"
                with open(path, "wb") as f: f.write(r.content)
                img_paths.append(path)
                print(f"[{idx}] 이미지#{i} 저장 → {path}")
            except Exception as e:
                print(f"[{idx}] 이미지#{i} 다운로드 실패: {e}")

        data[idx]["images"] = img_paths

    # 종료 조건 (예: idx가 원하는 숫자 도달 시)
    if last_idx >= 100:
        break

    # 더 불러오기
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
    time.sleep(0.5)

# CSV로 정리
with open("output.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["index", "image_paths"])
    for idx, info in data.items():
        w.writerow([idx, ";".join(info["images"])])

driver.quit()
