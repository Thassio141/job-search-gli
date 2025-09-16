#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de vagas do LinkedIn (apenas LinkedIn), com execução standalone.
Usa URL com filtros (Remoto + Últimas 24h) e tenta fechar modal de login.
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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class LinkedInScraper:
    BASE = "https://br.linkedin.com"
    SEARCH_PATH = "/jobs/search"

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

    @staticmethod
    def _ensure_quoted(keyword: str) -> str:
        kw = keyword.strip()
        if (kw.startswith('"') and kw.endswith('"')):
            return kw
        return f'"{kw}"'

    def _build_search_url(self, keyword: str, location: str = "Brasil", start: int = 0) -> str:
        quoted_kw = self._ensure_quoted(keyword)
        params = {
            "keywords": quoted_kw,
            "location": location,
            "geoId": "106057199",
            "f_TPR": "r86400",
            "f_WT": "2",
            "position": "1",
            "pageNum": start // 25
        }
        query = urlencode(params, quote_via=quote_plus)
        return f"{self.BASE}{self.SEARCH_PATH}?{query}"

    @staticmethod
    def _parse_relative_time(text: str) -> Optional[datetime]:
        if not text:
            return None
        t = text.lower().strip()
        m = re.search(r'(\d+)\s+minute', t)
        if m:
            return datetime.now() - timedelta(minutes=int(m.group(1)))
        m = re.search(r'(\d+)\s+hour', t)
        if m:
            return datetime.now() - timedelta(hours=int(m.group(1)))
        m = re.search(r'(\d+)\s+day', t)
        if m:
            return datetime.now() - timedelta(days=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+min', t)
        if m:
            return datetime.now() - timedelta(minutes=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+hora', t)
        if m:
            return datetime.now() - timedelta(hours=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+dia', t)
        if m:
            return datetime.now() - timedelta(days=int(m.group(1)))
        return None

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
    def _extract_job_info(card_html: str) -> Optional[Dict]:
        soup = BeautifulSoup(card_html, 'html.parser')
        job_id = soup.get('data-job-id') or None
        title_link = soup.select_one('a[href*="/jobs/view/"]') or soup.select_one('a[href*="/jobs/"]')
        if not title_link:
            return None
        href = title_link['href']
        link = href if href.startswith('http') else urljoin("https://br.linkedin.com", href)
        nome = title_link.get_text(strip=True)
        empresa_el = soup.select_one('h4') or soup.select_one('.job-card-container__company-name')
        empresa = empresa_el.get_text(strip=True) if empresa_el else None
        loc_el = soup.select_one('.job-card-container__metadata-item') or soup.select_one('span[title*="Brasil"]')
        localidade = loc_el.get_text(strip=True) if loc_el else None
        loc_low = (localidade or '').lower()
        remoto = any(k in loc_low for k in ['(remote)', 'remoto', 'home office']) or 'Brasil' in (localidade or '')
        insight = soup.select_one('.job-card-container__job-insight-text')
        insights = insight.get_text(strip=True) if insight else None
        footer_text = ' '.join([li.get_text(strip=True) for li in soup.select('li')])
        promovida = 'promoted' in footer_text.lower()
        easy_apply = 'easy apply' in footer_text.lower() or 'seja um dos primeiros' in footer_text.lower()
        data_str = None
        data_iso = None
        for el in soup.find_all(True):
            text = el.get_text(strip=True)
            if 'há' in text.lower() and ('hora' in text.lower() or 'minuto' in text.lower()):
                data_str = text
                rel = LinkedInScraper._parse_relative_time(text)
                if rel:
                    data_iso = rel.isoformat()
                break
        tipo = LinkedInScraper._normalize_contract(f"{nome} {localidade} {footer_text}") or None
        return {
            'jobId': job_id,
            'link': link,
            'nome': nome,
            'empresa': empresa,
            'localidade': localidade,
            'remoto': remoto,
            'tipoContrato': tipo,
            'promovida': promovida,
            'easyApply': easy_apply,
            'insights': insights,
            'dataPublicacao': data_iso,
            'dataPublicacaoStr': data_str
        }

    def scrape_jobs(self, term: str, location: str = "Brasil", max_pages: int = 5, max_days_old: int = 3) -> List[Dict]:
        self.driver = self._setup_driver()
        results: List[Dict] = []
        try:
            wait = WebDriverWait(self.driver, 20)
            cutoff_date = datetime.now() - timedelta(days=max_days_old)
            found_old = False
            for page in range(max_pages):
                start = page * 25
                url = self._build_search_url(term, location=location, start=start)
                print(f"🔎 Acessando: {url}")
                self.driver.get(url)
                # Tenta fechar eventual modal de login
                try:
                    time.sleep(2)
                    modal_close_selectors = [
                        'button[aria-label="Fechar"]','button[aria-label="Close"]','.modal-close-button','.close-button',
                        'button[data-testid="close-button"]','button[class*="close"]','button[class*="dismiss"]',
                        '[role="dialog"] button[aria-label*="Fechar"]','[role="dialog"] button[aria-label*="Close"]',
                        'div[role="dialog"] button:last-child'
                    ]
                    modal_closed = False
                    for selector in modal_close_selectors:
                        try:
                            close_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if close_button.is_displayed() and close_button.is_enabled():
                                self.driver.execute_script("arguments[0].click();", close_button)
                                print("✅ Modal de login fechado")
                                modal_closed = True
                                time.sleep(1)
                                break
                        except Exception:
                            continue
                    if not modal_closed:
                        try:
                            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                            print("✅ Tentativa de fechar modal com ESC")
                            time.sleep(1)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"⚠️ Erro ao tentar fechar modal: {e}")
                try:
                    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-job-id], .job-card-container, [data-job-id]')))
                except TimeoutException:
                    print("⏳ Timeout esperando resultados; pulando...")
                    continue
                time.sleep(1.0)
                cards = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-job-id]') or \
                        self.driver.find_elements(By.CSS_SELECTOR, '.job-card-container') or \
                        self.driver.find_elements(By.CSS_SELECTOR, '[data-job-id]')
                if not cards:
                    print("⚠️ Nenhum card encontrado nesta página.")
                    break
                page_jobs = []
                has_old_here = False
                for card in cards:
                    try:
                        info = self._extract_job_info(card.get_attribute('outerHTML'))
                        if not info:
                            continue
                        if info.get('dataPublicacao'):
                            try:
                                dt = datetime.fromisoformat(info['dataPublicacao'])
                            except ValueError:
                                dt = None
                            if dt and dt < cutoff_date:
                                has_old_here = True
                                print(f"⚠️ Vaga antiga: {info['nome'][:60]}... ({info.get('dataPublicacaoStr')}) > {max_days_old} dias - IGNORADA")
                                continue
                        page_jobs.append(info)
                    except Exception as e:
                        print(f"Erro ao processar card: {e}")
                        continue
                if has_old_here:
                    found_old = True
                results.extend(page_jobs)
                print(f"✅ Página {page+1}: coletadas {len(page_jobs)} vagas recentes.")
                if found_old:
                    print("🛑 Interrompendo paginação por encontrar vagas antigas.")
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
    print("🚀 LinkedIn: iniciando scraping...")
    all_jobs: List[Dict] = []
    scraper = LinkedInScraper()
    for i, kw in enumerate(keywords, 1):
        qkw = LinkedInScraper._ensure_quoted(kw)
        print(f"\n🔍 ({i}/{len(keywords)}) {qkw}...")
        jobs = scraper.scrape_jobs(term=kw, location='Brasil', max_pages=5, max_days_old=3)
        all_jobs.extend(jobs)
    unique_jobs = deduplicate_jobs(all_jobs)
    with open('vagas_linkedin.json', 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ LinkedIn: {len(unique_jobs)} vagas únicas salvas em vagas_linkedin.json")


if __name__ == '__main__':
    main()


