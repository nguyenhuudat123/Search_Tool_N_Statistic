import time
import random
import threading
from subprocess import CREATE_NO_WINDOW
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class NaverScraper:
    def __init__(self):
        self.driver = None

    def run_automation(self, items_data, target, is_paused_event, stop_check_func, update_ui_callback, finish_callback):
        """
        Hàm thực thi tiến trình quét độc lập.
        update_ui_callback: Hàm để đẩy dữ liệu ngược về giao diện an toàn.
        """
        if not self.driver:
            opts = Options()
            opts.add_experimental_option("detach", True)
            opts.add_argument('--disable-blink-features=AutomationControlled')
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option('useAutomationExtension', False)
            
            # Cấu hình chặn cửa sổ cmd đen khi gọi ChromeDriver
            service = Service(ChromeDriverManager().install())
            service.creation_flags = CREATE_NO_WINDOW
            
            self.driver = webdriver.Chrome(service=service, options=opts)
            self.driver.get("about:blank")
        
        try:
            for kw, item_id in items_data:
                if stop_check_func(): 
                    break
                
                is_paused_event.wait()
                update_ui_callback(item_id, 'rank', "Đang quét...", None)
                
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.execute_script("window.open('about:blank', '_blank');")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                
                time.sleep(random.uniform(3, 5))
                self.driver.get(f"https://search.naver.com/search.naver?query={kw}")
                try: 
                    WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                except: 
                    pass
                
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(0.5)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)

                script_highlight = f"""
                var target = "{target}";
                var found = false;
                var firstFoundElement = null;
                var titleSelectors = [
                    'a.api_txt_lines.total_tit', 'a.total_tit', 'a.title_link', '.total_wrap a[href*="blog"]',
                    '.total_wrap a[href*="post"]', 'a.sh_cafe_title', 'a.api_txt_lines[href*="cafe"]',
                    '.total_wrap a[href*="cafe"]', 'a.news_tit', 'a.news_area', 'a[class*="news"]',
                    'a.product_title', 'a.goods_name', '.product_info_area a', 'a.video_title', 'a.video_tit',
                    'a.question_text', 'a.title_link[href*="kin.naver"]', 'a.link_tit', 'a.lnk_tit', 'a.ad_tit',
                    'a[class*="ad_"]', '.api_subject_bx a', '.total_area a', '.card_area a', '.group_list a'
                ];
                var allSelectors = titleSelectors.join(', ');
                var titleElements = document.querySelectorAll(allSelectors);
                var validTitles = Array.from(titleElements).filter(function(el) {{
                    var text = el.textContent.trim(); return text.length > 5 && text.length < 200;
                }});
                validTitles.forEach(function(el) {{
                    var fullText = el.textContent.trim();
                    if (fullText.includes(target)) {{
                        found = true;
                        if (!firstFoundElement) {{ firstFoundElement = el; }}
                        el.style.backgroundColor = 'yellow'; el.style.color = 'black';
                        el.style.fontWeight = 'bold'; el.style.padding = '3px 6px';
                        el.style.borderRadius = '3px'; el.style.display = 'inline-block';
                    }}
                }});
                if (firstFoundElement) {{
                    var elementPosition = firstFoundElement.getBoundingClientRect().top + window.pageYOffset;
                    window.scrollTo({{ top: elementPosition - 150, behavior: 'smooth' }});
                    firstFoundElement.style.border = '3px solid red';
                }}
                return found;
                """
                
                try:
                    is_target_found = self.driver.execute_script(script_highlight)
                    if is_target_found:
                        update_ui_callback(item_id, 'rank', "✓ TÌM THẤY", None)
                    else:
                        update_ui_callback(item_id, 'rank', "순위밖", "")
                        time.sleep(0.3)
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                except Exception:
                    update_ui_callback(item_id, 'rank', "Lỗi", None)

        finally:
            finish_callback(len(items_data))

    def quit_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass