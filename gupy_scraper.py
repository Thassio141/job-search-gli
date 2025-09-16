#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de vagas da Gupy (apenas Gupy), com execução standalone.
Coleta: link, nome, empresa, remoto, tipoContrato, datas.
"""

import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


class GupyScraper:
    """Classe para fazer scraping de vagas da Gupy"""
    
    def __init__(self, chromedriver_path: str = r'C:\Users\thass\Downloads\chromedriver-win64\chromedriver.exe'):
        self.chromedriver_path = chromedriver_path
        self.driver = None
        self.base_url = 'https://portal.gupy.io'
    
    def _setup_driver(self) -> webdriver.Chrome:
        """Configura e inicializa o Chrome WebDriver (sem headless)."""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--lang=pt-BR')
        chrome_options.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        
        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        
        return driver

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
            
        patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY
            r'(\d{1,2}) de (\w+) de (\d{4})',  # DD de Mês de YYYY
            r'(\d{1,2}) de (\w+)',  # DD de Mês (ano atual)
            r'(\d{1,2})/(\d{1,2})',  # DD/MM (ano atual)
        ]
        
        current_year = datetime.now().year
        months_pt = {
            'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
            'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
            'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
        }
        
        for pattern in patterns:
            match = re.search(pattern, date_str.lower())
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        if pattern == patterns[0]:
                            day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                        else:
                            day, month, year = int(groups[0]), months_pt[groups[1]], int(groups[2])
                    elif len(groups) == 2:
                        if pattern == patterns[2]:
                            day, month = int(groups[0]), months_pt[groups[1]]
                        else:
                            day, month = int(groups[0]), int(groups[1])
                        year = current_year
                    return datetime(year, month, day)
                except (ValueError, KeyError):
                    continue
        return None

    @staticmethod
    def _extract_job_info(job_card_html: str, base_url: str) -> Optional[Dict]:
        """Extrai informações de uma vaga a partir do HTML do card"""
        soup = BeautifulSoup(job_card_html, 'html.parser')

        link_element = soup.find('a', {'aria-label': lambda x: x and x.startswith('Ir para vaga')})
        if not link_element:
            return None

        href = link_element.get('href', '')
        if not href:
            return None

        link = href if href.startswith('http') else urljoin(base_url, href)

        title_element = link_element.find('h3')
        nome = title_element.get_text(strip=True) if title_element else None

        company_element = link_element.find('p')
        empresa = company_element.get_text(strip=True) if company_element else None

        detail_spans = link_element.find_all('span')
        detail_texts = [span.get_text(strip=True) for span in detail_spans if span.get_text(strip=True)]

        detail_text_combined = ' '.join(detail_texts).lower()
        remoto = 'remoto' in detail_text_combined or 'home office' in detail_text_combined

        tipo_contrato = None
        contract_patterns = [
            r'efetivo', r'tempor[aá]rio', r'est[aá]gio', r'aprendiz', r'pj|p\.?j\.?' 
        ]
        for detail in detail_texts:
            for pattern in contract_patterns:
                if re.search(pattern, detail.lower()):
                    tipo_contrato = detail
                    break
            if tipo_contrato:
                break

        if not tipo_contrato:
            aria_label = link_element.get('aria-label', '')
            match = re.search(r'tipo\s+([^.]+)\.', aria_label, re.IGNORECASE)
            if match:
                tipo_contrato = match.group(1).strip()

        if tipo_contrato:
            tipo_lower = tipo_contrato.lower()
            if 'efetivo' in tipo_lower:
                tipo_contrato = 'Efetivo'
            elif 'tempor' in tipo_lower:
                tipo_contrato = 'Temporário'
            elif 'estág' in tipo_lower or 'estag' in tipo_lower:
                tipo_contrato = 'Estágio'
            elif 'aprendiz' in tipo_lower:
                tipo_contrato = 'Aprendiz'
            elif 'pj' in tipo_lower:
                tipo_contrato = 'PJ'
            else:
                tipo_contrato = tipo_contrato.strip()

        data_publicacao = None
        data_str = None
        for detail in detail_texts:
            if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}\s+de\s+\w+', detail):
                data_str = detail
                break
        if not data_str:
            date_elements = link_element.find_all(['time', 'span'], class_=re.compile(r'date|time|published', re.I))
            for elem in date_elements:
                text = elem.get_text(strip=True)
                if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}\s+de\s+\w+', text):
                    data_str = text
                    break
        if not data_str:
            aria_label = link_element.get('aria-label', '')
            date_match = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}\s+de\s+\w+)', aria_label)
            if date_match:
                data_str = date_match.group(1)
        if data_str:
            data_publicacao = GupyScraper._parse_date(data_str)

        return {
            'link': link,
            'nome': nome,
            'empresa': empresa,
            'remoto': remoto,
            'tipoContrato': tipo_contrato,
            'dataPublicacao': data_publicacao.isoformat() if data_publicacao else None,
            'dataPublicacaoStr': data_str
        }

    def scrape_jobs(self, term: str = 'vagas', remote_only: bool = True, max_pages: int = 10, max_days_old: int = 3) -> List[Dict]:
        """
        Faz scraping de vagas na Gupy com paginação e parada por data.
        """
        self.driver = self._setup_driver()
        try:
            search_url = f'{self.base_url}/job-search/term={quote(term)}'
            if remote_only:
                search_url += '&workplaceTypes[]=remote'
            print(f"Acessando: {search_url}")
            self.driver.get(search_url)
            wait = WebDriverWait(self.driver, 10)
            try:
                wait.until(
                    lambda driver: driver.find_elements(By.CSS_SELECTOR, 'a[aria-label^="Ir para vaga"]') or
                                  driver.find_elements(By.CSS_SELECTOR, 'nav[aria-label="pagination navigation"]')
                )
            except TimeoutException:
                print("Timeout aguardando elementos da página")
                return []
            all_jobs = []
            current_page = 1
            cutoff_date = datetime.now() - timedelta(days=max_days_old)
            found_old_job = False
            while current_page <= max_pages and not found_old_job:
                print(f"Processando página {current_page}...")
                time.sleep(1.2)
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 'a[aria-label^="Ir para vaga"]')
                if not job_cards:
                    print("Nenhuma vaga encontrada nesta página")
                    break
                page_jobs = []
                has_old_job_on_page = False
                for card in job_cards:
                    try:
                        job_info = self._extract_job_info(card.get_attribute('outerHTML'), self.base_url)
                        if job_info and job_info['link']:
                            # Filtro: excluir vagas Senior/SR
                            nome = (job_info.get('nome') or '').lower()
                            if 'senior' in nome or 'sr' in nome:
                                print(f"🚫 Vaga Senior/SR filtrada: {job_info.get('nome', 'N/A')}")
                                continue
                            
                            if job_info['dataPublicacao']:
                                job_date = datetime.fromisoformat(job_info['dataPublicacao'])
                                if job_date < cutoff_date:
                                    print(f"⚠️ Vaga antiga encontrada: {job_info['nome'][:50]}... - {job_info['dataPublicacaoStr']} (> {max_days_old} dias) - IGNORADA")
                                    has_old_job_on_page = True
                                    continue
                                else:
                                    print(f"✅ Vaga recente: {job_info['nome'][:50]}... - {job_info['dataPublicacaoStr']} - SALVA")
                                    page_jobs.append(job_info)
                            else:
                                print(f"📅 Vaga sem data: {job_info['nome'][:50]}... - SALVA (assumindo recente)")
                                page_jobs.append(job_info)
                    except Exception as e:
                        print(f"Erro ao processar card de vaga: {e}")
                        continue
                if has_old_job_on_page:
                    print(f"🛑 Página {current_page} contém vagas antigas - não avançará para próxima página")
                    found_old_job = True
                all_jobs.extend(page_jobs)
                print(f"Coletadas {len(page_jobs)} vagas recentes da página {current_page}")
                if found_old_job:
                    break
                try:
                    next_button = self.driver.find_element(
                        By.CSS_SELECTOR, 'nav[aria-label="pagination navigation"] button[aria-label="Próxima página"]:not([disabled])'
                    )
                    self.driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(1)
                    current_page += 1
                except NoSuchElementException:
                    print("Botão 'Próxima página' não encontrado ou desabilitado")
                    break
                except Exception as e:
                    print(f"Erro ao navegar para próxima página: {e}")
                    break
            if found_old_job:
                print(f"🛑 Busca interrompida para '{term}' - vaga mais antiga que {max_days_old} dias encontrada")
            else:
                print(f"✅ Busca finalizada para '{term}' - {len(all_jobs)} vagas coletadas")
            return all_jobs
        finally:
            if self.driver:
                self.driver.quit()


def load_keywords(filename: str = 'keywords.json') -> List[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            keywords = json.load(f)
        return keywords if isinstance(keywords, list) else []
    except FileNotFoundError:
        print(f"⚠️ Arquivo {filename} não encontrado. Usando keyword padrão 'vagas'")
        return ['vagas']
    except json.JSONDecodeError as e:
        print(f"⚠️ Erro ao ler {filename}: {e}. Usando keyword padrão 'vagas'")
        return ['vagas']


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = job.get('link') or job.get('jobId')
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    return unique_jobs


def main():
    keywords = load_keywords('keywords.json')
    print("🚀 Gupy: iniciando scraping...")
    all_jobs: List[Dict] = []
    scraper = GupyScraper()
    for i, kw in enumerate(keywords, 1):
        print(f"\n🔍 ({i}/{len(keywords)}) '{kw}'...")
        jobs = scraper.scrape_jobs(term=kw, remote_only=True, max_pages=10, max_days_old=3)
        all_jobs.extend(jobs)
    unique_jobs = deduplicate_jobs(all_jobs)
    with open('vagas_gupy.json', 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Gupy: {len(unique_jobs)} vagas únicas salvas em vagas_gupy.json")


if __name__ == '__main__':
    main()



