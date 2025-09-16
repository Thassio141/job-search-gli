#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para fazer scraping de vagas no portal da Gupy com paginação.
Coleta: link, nome, empresa, remoto (true/false), tipoContrato
Salva os dados em vagas_gupy.json
"""

import json
import re
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote, urlencode, quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class GupyScraper:
    """Classe para fazer scraping de vagas da Gupy"""
    
    def __init__(self, chromedriver_path: str = r'C:\Users\thass\Downloads\chromedriver-win64\chromedriver.exe'):
        self.chromedriver_path = chromedriver_path
        self.driver = None
        self.base_url = 'https://portal.gupy.io'
    
    def _setup_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Configura e inicializa o Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--lang=pt-BR')
        chrome_options.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        
        if headless:
            chrome_options.add_argument('--headless')
        
        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        
        return driver

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
            
        # Padrões comuns de data na Gupy
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
                    if len(groups) == 3:  # DD/MM/YYYY ou DD de Mês de YYYY
                        if pattern == patterns[0]:  # DD/MM/YYYY
                            day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                        else:  # DD de Mês de YYYY
                            day, month, year = int(groups[0]), months_pt[groups[1]], int(groups[2])
                    elif len(groups) == 2:  # DD/MM ou DD de Mês
                        if pattern == patterns[2]:  # DD de Mês
                            day, month = int(groups[0]), months_pt[groups[1]]
                        else:  # DD/MM
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

        # Link da vaga
        link_element = soup.find('a', {'aria-label': lambda x: x and x.startswith('Ir para vaga')})
        if not link_element:
            return None

        href = link_element.get('href', '')
        if not href:
            return None

        link = href if href.startswith('http') else urljoin(base_url, href)

        # Título da vaga
        title_element = link_element.find('h3')
        nome = title_element.get_text(strip=True) if title_element else None

        # Empresa
        company_element = link_element.find('p')
        empresa = company_element.get_text(strip=True) if company_element else None

        # Detalhes (local/remoto/tipo de contrato)
        detail_spans = link_element.find_all('span')
        detail_texts = [span.get_text(strip=True) for span in detail_spans if span.get_text(strip=True)]

        # Verificar se é remoto
        detail_text_combined = ' '.join(detail_texts).lower()
        remoto = 'remoto' in detail_text_combined or 'home office' in detail_text_combined

        # Extrair tipo de contrato
        tipo_contrato = None
        contract_patterns = [
            r'efetivo',
            r'tempor[aá]rio',
            r'est[aá]gio',
            r'aprendiz',
            r'pj|p\.?j\.?'
        ]

        # Primeiro, tenta encontrar nos detalhes
        for detail in detail_texts:
            for pattern in contract_patterns:
                if re.search(pattern, detail.lower()):
                    tipo_contrato = detail
                    break
            if tipo_contrato:
                break

        # Se não encontrou, tenta no aria-label
        if not tipo_contrato:
            aria_label = link_element.get('aria-label', '')
            match = re.search(r'tipo\s+([^.]+)\.', aria_label, re.IGNORECASE)
            if match:
                tipo_contrato = match.group(1).strip()

        # Normalizar tipo de contrato
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

        # Extrair data de publicação
        data_publicacao = None
        data_str = None
        
        # Procura por data nos detalhes ou em elementos específicos
        for detail in detail_texts:
            # Procura por padrões de data
            if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}\s+de\s+\w+', detail):
                data_str = detail
                break
        
        # Se não encontrou nos detalhes, procura em outros elementos
        if not data_str:
            # Procura em elementos com classes comuns de data
            date_elements = link_element.find_all(['time', 'span'], class_=re.compile(r'date|time|published', re.I))
            for elem in date_elements:
                text = elem.get_text(strip=True)
                if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}\s+de\s+\w+', text):
                    data_str = text
                    break
        
        # Se ainda não encontrou, procura no aria-label
        if not data_str:
            aria_label = link_element.get('aria-label', '')
            date_match = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}\s+de\s+\w+)', aria_label)
            if date_match:
                data_str = date_match.group(1)
        
        # Converte string de data para datetime
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

    def scrape_jobs(self, term: str = 'vagas', remote_only: bool = True, max_pages: int = 10, headless: bool = True, max_days_old: int = 3) -> List[Dict]:
        """
        Faz scraping de vagas na Gupy com paginação e parada por data
        
        Args:
            term: termo de busca
            remote_only: se True, aplica filtro remoto
            max_pages: máximo de páginas para percorrer
            headless: se True, roda o browser em modo headless
            max_days_old: máximo de dias de idade da vaga (padrão: 3)
            
        Returns:
            Lista de dicionários com dados das vagas
        """
        self.driver = self._setup_driver(headless)
        
        try:
            # Monta URL de busca
            search_url = f'{self.base_url}/job-search/term={quote(term)}'
            if remote_only:
                search_url += '&workplaceTypes[]=remote'
            
            print(f"Acessando: {search_url}")
            self.driver.get(search_url)
            
            # Espera inicial - aguarda cards de vaga ou paginação aparecer
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
                
                # Aguarda um pouco para garantir que a página carregou
                time.sleep(1.2)
                
                # Busca todos os cards de vaga na página atual
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
                            # Verifica se a vaga é mais antiga que o limite
                            if job_info['dataPublicacao']:
                                job_date = datetime.fromisoformat(job_info['dataPublicacao'])
                                if job_date < cutoff_date:
                                    print(f"⚠️ Vaga antiga encontrada: {job_info['nome'][:50]}... - {job_info['dataPublicacaoStr']} (> {max_days_old} dias) - IGNORADA")
                                    has_old_job_on_page = True
                                    # NÃO adiciona a vaga antiga, mas continua processando as outras da página
                                    continue
                                else:
                                    # Vaga é recente, adiciona à lista
                                    print(f"✅ Vaga recente: {job_info['nome'][:50]}... - {job_info['dataPublicacaoStr']} - SALVA")
                                    page_jobs.append(job_info)
                            else:
                                # Se não tem data, adiciona mesmo assim (pode ser recente)
                                print(f"📅 Vaga sem data: {job_info['nome'][:50]}... - SALVA (assumindo recente)")
                                page_jobs.append(job_info)
                    except Exception as e:
                        print(f"Erro ao processar card de vaga: {e}")
                        continue
                
                # Se encontrou vaga antiga nesta página, marca para parar de avançar páginas
                if has_old_job_on_page:
                    print(f"🛑 Página {current_page} contém vagas antigas - não avançará para próxima página")
                    found_old_job = True
                
                all_jobs.extend(page_jobs)
                print(f"Coletadas {len(page_jobs)} vagas recentes da página {current_page}")
                
                # Se encontrou vaga antiga, para de avançar páginas
                if found_old_job:
                    break
                
                # Tenta ir para a próxima página
                try:
                    next_button = self.driver.find_element(
                        By.CSS_SELECTOR, 
                        'nav[aria-label="pagination navigation"] button[aria-label="Próxima página"]:not([disabled])'
                    )
                    
                    # Clica no botão de próxima página
                    self.driver.execute_script("arguments[0].click();", next_button)
                    
                    # Aguarda um pouco para a página carregar
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
            
        except Exception as e:
            print(f"Erro durante o scraping: {e}")
            return []
            
        finally:
            if self.driver:
                self.driver.quit()


def load_keywords(filename: str = 'keywords.json') -> List[str]:
    """Carrega lista de keywords do arquivo JSON"""
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


class IndeedScraper:
    """
    Scraper de vagas no Indeed Brasil.
    Usa seletores robustos baseados em data-testid e padrões estáveis.
    """

    BASE = "https://br.indeed.com"
    SEARCH_PATH = "/jobs"

    def __init__(self,
                 chromedriver_path: str = r'C:\Users\thass\Downloads\chromedriver-win64\chromedriver.exe',
                 profile_dir: Optional[str] = None):
        self.chromedriver_path = chromedriver_path
        self.profile_dir = profile_dir
        self.driver: Optional[webdriver.Chrome] = None

    def _setup_driver(self, headless: bool = False) -> webdriver.Chrome:
        opts = Options()
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--lang=pt-BR')
        opts.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        if self.profile_dir:
            opts.add_argument(f'--user-data-dir={self.profile_dir}')
        if headless:
            opts.add_argument('--headless=new')

        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=opts)
        driver.implicitly_wait(8)
        return driver

    def _build_search_url(self,
                          keyword: str,
                          location: str = "Brasil",
                          remote_only: bool = False,
                          start: int = 0) -> str:
        """Monta a URL de busca de Jobs no Indeed."""
        params = {
            "q": keyword,
            "l": location,
            "start": start
        }
        if remote_only:
            params["sc"] = "0kf%3Aattr%28DSQF7%29%3B"  # Remote filter
        
        query = urlencode(params, quote_via=quote_plus)
        return f"{self.BASE}{self.SEARCH_PATH}?{query}"

    @staticmethod
    def _parse_relative_time(text: str) -> Optional[datetime]:
        """Converte textos do tipo 'há 2 dias', 'há 1 hora', etc."""
        if not text:
            return None
        t = text.lower().strip()

        # Português
        m = re.search(r'há\s+(\d+)\s+dia', t)
        if m:
            return datetime.now() - timedelta(days=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+hora', t)
        if m:
            return datetime.now() - timedelta(hours=int(m.group(1)))
        m = re.search(r'há\s+(\d+)\s+minuto', t)
        if m:
            return datetime.now() - timedelta(minutes=int(m.group(1)))

        return None

    @staticmethod
    def _normalize_contract(title_or_meta: str) -> Optional[str]:
        """Heurística para identificar tipo de contrato nos textos."""
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
        """Detecta senioridade pelo título."""
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
        """Extrai dados do card de vaga do Indeed."""
        soup = BeautifulSoup(card_html, 'html.parser')
        
        # ID da vaga (jk)
        a = soup.select_one('h2 a.jcs-JobTitle')
        jk = None
        if a:
            jk = a.get('data-jk')
            if not jk:
                # Fallback pela classe job_<jk>
                for cls in soup.get('class', []):
                    if cls.startswith('job_'):
                        jk = cls.split('job_')[-1]
                        break

        # Título
        title = None
        if a:
            title_span = a.select_one('span')
            title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)

        # URL absoluta
        url = None
        if a and a.get('href'):
            url = urljoin("https://br.indeed.com", a['href'])

        # Empresa
        company_el = soup.select_one('span[data-testid="company-name"]')
        company = company_el.get_text(strip=True) if company_el else None

        # Localidade
        location_el = soup.select_one('div[data-testid="text-location"]')
        location = location_el.get_text(strip=True) if location_el else None

        # Detectar remoto pela localidade
        remoto = False
        if location:
            loc_low = location.lower()
            remoto = any(k in loc_low for k in ['remoto', 'remote', 'home office', 'trabalho remoto'])

        # Bullets/snippet
        bullets = []
        bullets_el = soup.select('div[data-testid="belowJobSnippet"] li')
        bullets = [li.get_text(strip=True) for li in bullets_el]

        # Easy Apply
        easy_apply = False
        ia_icon = soup.select_one('.iaIcon')
        if ia_icon:
            easy_apply = 'Candidate-se facilmente' in ia_icon.get_text()

        # Tempo de resposta
        response_text = None
        for el in soup.find_all(True):
            if 'Normalmente responde' in el.get_text():
                response_text = el.get_text(strip=True)
                break

        # Patrocinado?
        is_sponsored = False
        if soup.get('class'):
            is_sponsored = 'maybeSponsoredJob' in soup.get('class', [])
        if a:
            is_sponsored = is_sponsored or a.get('id', '').startswith('sj_')
            is_sponsored = is_sponsored or '/pagead/clk' in (a.get('href') or '')

        # Senioridade
        seniority = IndeedScraper._detect_seniority(title)

        # Tipo de contrato
        tipo_contrato = IndeedScraper._normalize_contract(f"{title} {location} {' '.join(bullets)}")

        # Data de publicação (Indeed não mostra data exata, usar None)
        data_publicacao = None
        data_publicacao_str = None

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
            'dataPublicacao': data_publicacao,
            'dataPublicacaoStr': data_publicacao_str
        }

    def scrape_jobs(self,
                    term: str,
                    location: str = "Brasil",
                    remote_only: bool = False,
                    max_pages: int = 5,
                    headless: bool = False,
                    max_days_old: int = 3) -> List[Dict]:
        """Coleta vagas do Indeed."""
        self.driver = self._setup_driver(headless=headless)
        results: List[Dict] = []

        try:
            wait = WebDriverWait(self.driver, 20)
            found_old = False

            for page in range(max_pages):
                start = page * 10  # Indeed usa 10 por página
                url = self._build_search_url(term, location=location, remote_only=remote_only, start=start)
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
                has_old_here = False

                for card in cards:
                    try:
                        info = self._extract_job_info(card.get_attribute('outerHTML'))
                        if not info:
                            continue

                        # Indeed não tem data exata, então não aplicamos filtro de data
                        # Mas mantemos a estrutura para consistência
                        page_jobs.append(info)

                    except Exception as e:
                        print(f"Erro ao processar card: {e}")
                        continue

                results.extend(page_jobs)
                print(f"✅ Página {page+1}: coletadas {len(page_jobs)} vagas.")

                # Verifica se há próxima página
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


class LinkedInScraper:
    """
    Scraper de vagas no LinkedIn Jobs.
    Observações:
    - LinkedIn costuma exigir login. Use 'profile_dir' para reaproveitar sessão.
    - 'remote_only' tenta usar f_WT=2 (Remote). Se o LinkedIn mudar este parâmetro, a coleta ainda
      detecta 'remoto' pela localidade (ex.: 'Brazil (Remote)').
    """

    BASE = "https://www.linkedin.com"
    SEARCH_PATH = "/jobs/search/"

    def __init__(self,
                 chromedriver_path: str = r'C:\Users\thass\Downloads\chromedriver-win64\chromedriver.exe',
                 profile_dir: Optional[str] = None):
        self.chromedriver_path = chromedriver_path
        self.profile_dir = profile_dir
        self.driver: Optional[webdriver.Chrome] = None

    def _setup_driver(self, headless: bool = False) -> webdriver.Chrome:
        opts = Options()
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--lang=pt-BR')
        opts.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
        if self.profile_dir:
            opts.add_argument(f'--user-data-dir={self.profile_dir}')
        if headless:
            opts.add_argument('--headless=new')

        service = Service(self.chromedriver_path)
        driver = webdriver.Chrome(service=service, options=opts)
        driver.implicitly_wait(8)
        return driver

    @staticmethod
    def _ensure_quoted(keyword: str) -> str:
        """Garante que a keyword esteja entre aspas para a pesquisa do LinkedIn."""
        kw = keyword.strip()
        if (kw.startswith('"') and kw.endswith('"')) or (kw.startswith('"') and kw.endswith('"')):
            return kw
        return f'"{kw}"'

    def _build_search_url(self,
                          keyword: str,
                          location: str = "Brazil",
                          remote_only: bool = False,
                          start: int = 0) -> str:
        """Monta a URL de busca de Jobs no LinkedIn."""
        quoted_kw = self._ensure_quoted(keyword)
        params = {
            "keywords": quoted_kw,
            "location": location,
            "start": start
        }
        if remote_only:
            params["f_WT"] = "2"
        query = urlencode(params, quote_via=quote_plus)
        return f"{self.BASE}{self.SEARCH_PATH}?{query}"

    @staticmethod
    def _parse_relative_time(text: str) -> Optional[datetime]:
        """Converte textos do tipo '14 minutes ago', '8 hours ago', '2 days ago', etc."""
        if not text:
            return None
        t = text.lower().strip()

        # Inglês
        m = re.search(r'(\d+)\s+minute', t)
        if m:
            return datetime.now() - timedelta(minutes=int(m.group(1)))

        m = re.search(r'(\d+)\s+hour', t)
        if m:
            return datetime.now() - timedelta(hours=int(m.group(1)))

        m = re.search(r'(\d+)\s+day', t)
        if m:
            return datetime.now() - timedelta(days=int(m.group(1)))

        # Português
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
        """Heurística para identificar tipo de contrato nos textos do título/metadados (BR)."""
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
    def _extract_job_info(li_html: str) -> Optional[Dict]:
        """Extrai dados do card de vaga a partir do HTML do <li data-occludable-job-id=...>."""
        soup = BeautifulSoup(li_html, 'html.parser')

        root_li = soup.find('li', attrs={'data-occludable-job-id': True}) or soup
        job_id = root_li.get('data-occludable-job-id') or None

        # Título + Link
        a = soup.select_one('a.job-card-container__link')
        if not a or not a.get('href'):
            return None

        href = a['href']
        link = href if href.startswith('http') else urljoin("https://www.linkedin.com", href)
        nome = a.get('aria-label') or a.get_text(strip=True)

        # Empresa
        empresa_el = soup.select_one('.artdeco-entity-lockup__subtitle span')
        empresa = empresa_el.get_text(strip=True) if empresa_el else None

        # Localidade + remoto
        loc_el = soup.select_one('.job-card-container__metadata-wrapper li span')
        localidade = loc_el.get_text(strip=True) if loc_el else None
        loc_low = (localidade or '').lower()
        remoto = any(k in loc_low for k in ['(remote)', 'remoto', 'home office'])

        # Insights (texto do card)
        insight = soup.select_one('.job-card-container__job-insight-text')
        insights = insight.get_text(strip=True) if insight else None

        # Promoted / Easy Apply
        footer_text = ' '.join([li.get_text(strip=True) for li in soup.select('.job-card-container__footer-wrapper li')])
        promovida = 'promoted' in footer_text.lower()
        easy_apply = 'easy apply' in footer_text.lower()

        # Data (time)
        time_el = soup.select_one('.job-card-container__footer-wrapper time')
        data_iso = None
        data_str = None
        if time_el:
            data_str = time_el.get_text(strip=True) or None
            dt_attr = time_el.get('datetime')
            if dt_attr:
                try:
                    data_iso = datetime.fromisoformat(dt_attr).isoformat()
                except ValueError:
                    pass
            if not data_iso and data_str:
                rel = LinkedInScraper._parse_relative_time(data_str)
                if rel:
                    data_iso = rel.isoformat()

        # Tipo de contrato (heurística no título + localidade/rodapé)
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

    def scrape_jobs(self,
                    term: str,
                    location: str = "Brazil",
                    remote_only: bool = False,
                    max_pages: int = 5,
                    headless: bool = False,
                    max_days_old: int = 3) -> List[Dict]:
        """Coleta vagas do LinkedIn para uma 'term' (keyword) — SEMPRE usando aspas no query."""
        self.driver = self._setup_driver(headless=headless)
        results: List[Dict] = []

        try:
            wait = WebDriverWait(self.driver, 20)
            cutoff_date = datetime.now() - timedelta(days=max_days_old)
            found_old = False

            for page in range(max_pages):
                start = page * 25
                url = self._build_search_url(term, location=location, remote_only=remote_only, start=start)
                print(f"🔎 Acessando: {url}")
                self.driver.get(url)

                try:
                    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li[data-occludable-job-id]')))
                except TimeoutException:
                    print("⏳ Timeout esperando resultados; seguindo...")
                    continue

                time.sleep(1.0)
                lis = self.driver.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
                if not lis:
                    print("⚠️ Nenhum card encontrado nesta página.")
                    break

                page_jobs = []
                has_old_here = False

                for li in lis:
                    try:
                        info = self._extract_job_info(li.get_attribute('outerHTML'))
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


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    """Remove vagas duplicadas baseado no link ou job_id"""
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


def scrape_from_source(source: str, keywords: List[str], **kwargs) -> List[Dict]:
    """Executa scraping de uma fonte específica"""
    print(f"🔧 Iniciando scraping da fonte: {source}")
    all_jobs = []
    
    if source == "gupy":
        scraper = GupyScraper()
        print(f"🔍 Iniciando scraping da Gupy...")
        
        for i, keyword in enumerate(keywords, 1):
            print(f"\n🔍 Buscando por '{keyword}' ({i}/{len(keywords)})...")
            
            try:
                jobs = scraper.scrape_jobs(
                    term=keyword, 
                    remote_only=kwargs.get('remote_only', True), 
                    max_pages=kwargs.get('max_pages', 10), 
                    headless=kwargs.get('headless', True),
                    max_days_old=kwargs.get('max_days_old', 3)
                )
                
                if jobs:
                    print(f"✅ Encontradas {len(jobs)} vagas para '{keyword}'")
                    all_jobs.extend(jobs)
                else:
                    print(f"⚠️ Nenhuma vaga encontrada para '{keyword}'")
                    
            except Exception as e:
                print(f"❌ Erro ao buscar '{keyword}': {e}")
                continue
                
    elif source == "linkedin":
        print(f"🔧 Criando scraper do LinkedIn...")
        scraper = LinkedInScraper(profile_dir=kwargs.get('linkedin_profile_dir'))
        print(f"🔍 Iniciando scraping do LinkedIn...")
        
        for i, keyword in enumerate(keywords, 1):
            quoted_keyword = LinkedInScraper._ensure_quoted(keyword)
            print(f"\n🔍 Buscando por {quoted_keyword} ({i}/{len(keywords)})...")
            
            try:
                jobs = scraper.scrape_jobs(
                    term=keyword,
                    location=kwargs.get('location', 'Brazil'),
                    remote_only=kwargs.get('remote_only', True),
                    max_pages=kwargs.get('max_pages', 5),
                    headless=kwargs.get('headless', False),
                    max_days_old=kwargs.get('max_days_old', 3)
                )
                
                if jobs:
                    print(f"✅ Encontradas {len(jobs)} vagas para {quoted_keyword}")
                    all_jobs.extend(jobs)
                else:
                    print(f"⚠️ Nenhuma vaga encontrada para {quoted_keyword}")
                    
            except Exception as e:
                print(f"❌ Erro ao buscar '{keyword}': {e}")
                continue
                
    elif source == "indeed":
        print(f"🔧 Criando scraper do Indeed...")
        scraper = IndeedScraper(profile_dir=kwargs.get('indeed_profile_dir'))
        print(f"🔍 Iniciando scraping do Indeed...")
        
        for i, keyword in enumerate(keywords, 1):
            print(f"\n🔍 Buscando por '{keyword}' ({i}/{len(keywords)})...")
            
            try:
                jobs = scraper.scrape_jobs(
                    term=keyword,
                    location=kwargs.get('location', 'Brasil'),
                    remote_only=kwargs.get('remote_only', True),
                    max_pages=kwargs.get('max_pages', 5),
                    headless=kwargs.get('headless', False),
                    max_days_old=kwargs.get('max_days_old', 3)
                )
                
                if jobs:
                    print(f"✅ Encontradas {len(jobs)} vagas para '{keyword}'")
                    all_jobs.extend(jobs)
                else:
                    print(f"⚠️ Nenhuma vaga encontrada para '{keyword}'")
                    
            except Exception as e:
                print(f"❌ Erro ao buscar '{keyword}': {e}")
                continue
    
    print(f"🔧 Scraping da fonte {source} concluído: {len(all_jobs)} vagas coletadas")
    return all_jobs


def main():
    """Função principal com suporte a múltiplas fontes"""
    parser = argparse.ArgumentParser(description='Scraper de vagas de emprego')
    parser.add_argument('--source', choices=['gupy', 'linkedin', 'indeed', 'ambos'], default='gupy',
                       help='Fonte das vagas: gupy, linkedin, indeed ou ambos')
    parser.add_argument('--keywords', default='keywords.json',
                       help='Arquivo com keywords (padrão: keywords.json)')
    parser.add_argument('--remote-only', action='store_true', default=True,
                       help='Buscar apenas vagas remotas')
    parser.add_argument('--max-pages', type=int, default=10,
                       help='Máximo de páginas por keyword')
    parser.add_argument('--max-days-old', type=int, default=3,
                       help='Máximo de dias de idade da vaga')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Executar em modo headless')
    parser.add_argument('--location', default='Brazil',
                       help='Localização para LinkedIn (padrão: Brazil)')
    parser.add_argument('--linkedin-profile', 
                       help='Pasta do perfil do LinkedIn para manter sessão')
    parser.add_argument('--indeed-profile', 
                       help='Pasta do perfil do Indeed para manter sessão')
    
    args = parser.parse_args()
    
    # Configurações
    config = {
        'remote_only': args.remote_only,
        'max_pages': args.max_pages,
        'headless': args.headless,
        'max_days_old': args.max_days_old,
        'location': args.location,
        'linkedin_profile_dir': args.linkedin_profile,
        'indeed_profile_dir': args.indeed_profile
    }
    
    # Carrega keywords do arquivo
    keywords = load_keywords(args.keywords)
    
    print("🚀 Iniciando scraping de vagas...")
    print(f"Fonte(s): {args.source}")
    print(f"Keywords encontradas: {', '.join(keywords)}")
    print(f"Apenas remotas: {config['remote_only']}")
    print(f"Máximo de páginas por keyword: {config['max_pages']}")
    print(f"Parar busca se vaga for mais antiga que: {config['max_days_old']} dias")
    if args.source in ['linkedin', 'indeed', 'ambos']:
        print(f"Localização: {config['location']}")
    print("-" * 60)
    
    all_jobs = []
    
    # Executa scraping baseado na fonte escolhida
    # SEMPRE executa Gupy primeiro, depois LinkedIn, depois Indeed
    if args.source == 'ambos':
        print("\n🚀 Executando busca em TODAS as fontes...")
        
        # Gupy primeiro
        print("\n" + "="*50)
        print("🔍 FASE 1: GUPY")
        print("="*50)
        gupy_jobs = scrape_from_source('gupy', keywords, **config)
        all_jobs.extend(gupy_jobs)
        print(f"✅ Gupy: {len(gupy_jobs)} vagas coletadas")
        
        # LinkedIn depois
        print("\n" + "="*50)
        print("🔍 FASE 2: LINKEDIN")
        print("="*50)
        try:
            linkedin_jobs = scrape_from_source('linkedin', keywords, **config)
            all_jobs.extend(linkedin_jobs)
            print(f"✅ LinkedIn: {len(linkedin_jobs)} vagas coletadas")
        except Exception as e:
            print(f"❌ Erro no LinkedIn: {e}")
            print("⚠️ Continuando com Indeed...")
            linkedin_jobs = []
        
        # Indeed por último
        print("\n" + "="*50)
        print("🔍 FASE 3: INDEED")
        print("="*50)
        try:
            indeed_jobs = scrape_from_source('indeed', keywords, **config)
            all_jobs.extend(indeed_jobs)
            print(f"✅ Indeed: {len(indeed_jobs)} vagas coletadas")
        except Exception as e:
            print(f"❌ Erro no Indeed: {e}")
            indeed_jobs = []
        
        print(f"\n🎯 TOTAL COLETADO: {len(all_jobs)} vagas de todas as fontes")
    elif args.source == 'gupy':
        all_jobs = scrape_from_source('gupy', keywords, **config)
    elif args.source == 'linkedin':
        all_jobs = scrape_from_source('linkedin', keywords, **config)
    elif args.source == 'indeed':
        all_jobs = scrape_from_source('indeed', keywords, **config)
    
    # Remove duplicatas
    print(f"\n🔄 Removendo duplicatas...")
    unique_jobs = deduplicate_jobs(all_jobs)
    duplicates_removed = len(all_jobs) - len(unique_jobs)
    
    if duplicates_removed > 0:
        print(f"✅ Removidas {duplicates_removed} vagas duplicadas")
    
    # Salva o resultado em JSON
    if args.source == 'ambos':
        output_file = 'vagas_combinadas.json'
    elif args.source == 'linkedin':
        output_file = 'vagas_linkedin.json'
    elif args.source == 'indeed':
        output_file = 'vagas_indeed.json'
    else:  # gupy
        output_file = 'vagas_gupy.json'
        
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Salvo {len(unique_jobs)} vagas únicas em {output_file}")
    
    # Mostra algumas estatísticas
    if unique_jobs:
        empresas = set(job['empresa'] for job in unique_jobs if job['empresa'])
        remotas = sum(1 for job in unique_jobs if job['remoto'])
        tipos_contrato = set(job['tipoContrato'] for job in unique_jobs if job['tipoContrato'])
        
        # Estatísticas de data
        vagas_com_data = [job for job in unique_jobs if job['dataPublicacao']]
        vagas_sem_data = len(unique_jobs) - len(vagas_com_data)
        
        print(f"\n📊 Estatísticas Finais:")
        print(f"   • Total de vagas únicas: {len(unique_jobs)}")
        print(f"   • Empresas diferentes: {len(empresas)}")
        print(f"   • Vagas remotas: {remotas}")
        print(f"   • Vagas com data: {len(vagas_com_data)}")
        print(f"   • Vagas sem data: {vagas_sem_data}")
        print(f"   • Tipos de contrato encontrados: {', '.join(sorted(tipos_contrato)) if tipos_contrato else 'Nenhum'}")
        
        # Estatísticas por keyword
        print(f"\n📈 Vagas por keyword:")
        for keyword in keywords:
            keyword_jobs = [job for job in unique_jobs if keyword.lower() in job['nome'].lower() or keyword.lower() in job.get('empresa', '').lower()]
            print(f"   • {keyword}: {len(keyword_jobs)} vagas")
        
        # Mostra algumas datas encontradas
        if vagas_com_data:
            print(f"\n📅 Exemplos de datas encontradas:")
            for job in vagas_com_data[:3]:  # Mostra apenas as 3 primeiras
                print(f"   • {job['nome'][:50]}... - {job['dataPublicacaoStr']}")


if __name__ == "__main__":
    main()
