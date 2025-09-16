#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de vagas do Indeed (apenas Indeed), com execução standalone.
Selectors robustos e filtros: Home-Office + Últimas 24 horas.
"""

import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlencode, quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class IndeedScraper:
    BASE = "https://br.indeed.com"
    SEARCH_PATH = "/jobs"

    def __init__(self, chromedriver_path: str = r'C:\\Users\\thass\\Downloads\\chromedriver-win64\\chromedriver.exe'):
        self.chromedriver_path = chromedriver_path
        self.driver: Optional[webdriver.Chrome] = None

    def _setup_driver(self) -> webdriver.Chrome:
        opts = Options()
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--lang=pt-BR')
        opts.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=opts)
        driver.implicitly_wait(8)
        return driver

    def _build_search_url(self, keyword: str, start: int = 0) -> str:
        params = {
            "q": keyword,
            "l": "Home-Office",
            "fromage": "1",
            "sc": "0kf%3Aattr%28DSQF7%29%3B",
            "from": "searchOnDesktopSerp",
            "start": start
        }
        query = urlencode(params, quote_via=quote_plus)
        return f"{self.BASE}{self.SEARCH_PATH}?{query}"

    @staticmethod
    def _normalize_contract(title_or_meta: str) -> Optional[str]:
        if not title_or_meta:
            return None
        s = title_or_meta.lower()
        if 'efetivo' in s or 'clt' in s:
            return 'Efetivo'
        if 'tempor' in s:
            return 'Temporário'
        if 'estág' in s or 'estag' in s:
            return 'Estágio'
        if 'aprendiz' in s:
            return 'Aprendiz'
        if re.search(r'\bpj\b|p\.?j\.?', s):
            return 'PJ'
        return None

    @staticmethod
    def _detect_seniority(title: str) -> Optional[str]:
        if not title:
            return None
        t = title.lower()
        if re.search(r'\b(sênior|senior|sr)\b', t):
            return 'Sênior'
        if re.search(r'\b(pleno|pl)\b', t):
            return 'Pleno'
        if re.search(r'\b(júnior|junior|jr)\b', t):
            return 'Júnior'
        return None

    @staticmethod
    def _extract_job_info(card_html: str) -> Optional[Dict]:
        soup = BeautifulSoup(card_html, 'html.parser')
        a = soup.select_one('h2 a.jcs-JobTitle')
        jk = None
        if a:
            jk = a.get('data-jk')
            if not jk:
                for cls in soup.get('class', []) or []:
                    if cls.startswith('job_'):
                        jk = cls.split('job_')[-1]
                        break
        title = None
        if a:
            title_span = a.select_one('span')
            title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)
        url = None
        if a and a.get('href'):
            url = urljoin("https://br.indeed.com", a['href'])
        company_el = soup.select_one('span[data-testid="company-name"]')
        company = company_el.get_text(strip=True) if company_el else None
        location_el = soup.select_one('div[data-testid="text-location"]')
        location = location_el.get_text(strip=True) if location_el else None
        remoto = False
        if location:
            loc_low = location.lower()
            remoto = any(k in loc_low for k in ['remoto', 'remote', 'home office', 'trabalho remoto'])
        bullets = [li.get_text(strip=True) for li in soup.select('div[data-testid="belowJobSnippet"] li')]
        easy_apply = False
        ia_icon = soup.select_one('.iaIcon')
        if ia_icon:
            easy_apply = 'Candidate-se facilmente' in ia_icon.get_text()
        response_text = None
        for el in soup.find_all(True):
            if 'Normalmente responde' in el.get_text():
                response_text = el.get_text(strip=True)
                break
        is_sponsored = False
        if soup.get('class'):
            is_sponsored = 'maybeSponsoredJob' in soup.get('class', [])
        if a:
            is_sponsored = is_sponsored or a.get('id', '').startswith('sj_') or '/pagead/clk' in (a.get('href') or '')
        seniority = IndeedScraper._detect_seniority(title)
        tipo_contrato = IndeedScraper._normalize_contract(f"{title} {location} {' '.join(bullets)}")
        return {
            'jobId': jk,
            'link': url,
            'nome': title,
            'empresa': company,
            'localidade': location,
            'remoto': remoto,
            'tipoContrato': tipo_contrato,
            'seniority': seniority,
            'bullets': bullets,
            'easyApply': easy_apply,
            'responseText': response_text,
            'isSponsored': is_sponsored,
            'dataPublicacao': None,
            'dataPublicacaoStr': None
        }

    def scrape_jobs(self, term: str, max_pages: int = 5) -> List[Dict]:
        self.driver = self._setup_driver()
        results: List[Dict] = []
        try:
            wait = WebDriverWait(self.driver, 20)
            for page in range(max_pages):
                start = page * 10
                url = self._build_search_url(term, start=start)
                print(f"🔎 Acessando: {url}")
                self.driver.get(url)
                try:
                    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#mosaic-provider-jobcards .cardOutline.tapItem.result')))
                except TimeoutException:
                    print("⏳ Timeout esperando resultados; seguindo...")
                    continue
                time.sleep(1.0)
                cards = self.driver.find_elements(By.CSS_SELECTOR, '#mosaic-provider-jobcards .cardOutline.tapItem.result')
                if not cards:
                    print("⚠️ Nenhum card encontrado nesta página.")
                    break
                page_jobs = []
                for card in cards:
                    try:
                        info = self._extract_job_info(card.get_attribute('outerHTML'))
                        if info:
                            page_jobs.append(info)
                    except Exception as e:
                        print(f"Erro ao processar card: {e}")
                        continue
                results.extend(page_jobs)
                print(f"✅ Página {page+1}: coletadas {len(page_jobs)} vagas.")
                # próxima página disponível?
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, 'nav[aria-label="pagination"] a[data-testid="pagination-page-next"][href]')
                    if not next_button.is_enabled():
                        print("🛑 Não há mais páginas disponíveis.")
                        break
                except NoSuchElementException:
                    print("🛑 Não há mais páginas disponíveis.")
                    break
            return results
        finally:
            if self.driver:
                self.driver.quit()


def load_keywords(filename: str = 'keywords.json') -> List[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return ['vagas']


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for job in jobs:
        key = job.get('link') or job.get('jobId')
        if key and key not in seen:
            seen.add(key)
            out.append(job)
    return out


def main():
    keywords = load_keywords('keywords.json')
    print("🚀 Indeed: iniciando scraping...")
    all_jobs: List[Dict] = []
    scraper = IndeedScraper()
    for i, kw in enumerate(keywords, 1):
        print(f"\n🔍 ({i}/{len(keywords)}) '{kw}'...")
        jobs = scraper.scrape_jobs(term=kw, max_pages=5)
        all_jobs.extend(jobs)
    unique_jobs = deduplicate_jobs(all_jobs)
    with open('vagas_indeed.json', 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Indeed: {len(unique_jobs)} vagas únicas salvas em vagas_indeed.json")


if __name__ == '__main__':
    main()



