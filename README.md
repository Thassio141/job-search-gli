# 🤖 WhatsApp Bot - Scraper de Vagas

Um sistema automatizado de scraping de vagas de emprego que coleta oportunidades de trabalho de múltiplas plataformas e envia os resultados via WhatsApp.

## 📋 Visão Geral

Este projeto automatiza a busca por vagas de emprego em três plataformas principais:
- **Gupy** - Portal brasileiro de vagas
- **LinkedIn** - Rede profissional global  
- **Indeed** - Portal internacional de empregos

O sistema coleta vagas baseadas em keywords personalizáveis, filtra por critérios específicos (remoto, data de publicação) e envia os resultados consolidados via WhatsApp.

## 🚀 Funcionalidades

### ✨ Recursos Principais
- **Multi-plataforma**: Scraping simultâneo em Gupy, LinkedIn e Indeed
- **Keywords personalizáveis**: Configure suas próprias palavras-chave de busca
- **Filtros inteligentes**: Vagas remotas e publicadas nos últimos 3 dias
- **Deduplicação**: Remove vagas duplicadas entre plataformas
- **Integração WhatsApp**: Envio automático para grupos do WhatsApp
- **Modo headless**: Execução silenciosa em background

### 🎯 Filtros Aplicados
- ✅ **Vagas remotas** apenas
- ✅ **Últimos 3 dias** de publicação
- ✅ **Deduplicação** por link/ID único
- ✅ **Scroll infinito** (LinkedIn) para máxima cobertura

## 📁 Estrutura do Projeto

```
whatsapp-bot/
├── README.md                 # Documentação do projeto
├── requirements.txt          # Dependências Python
├── keywords.json            # Lista de palavras-chave para busca
├── gupy_scraper.py         # Scraper específico para Gupy
├── linkedin_scraper.py     # Scraper específico para LinkedIn  
├── indeed_scraper.py       # Scraper específico para Indeed
├── vagas_gupy.json         # Vagas coletadas do Gupy (gerado)
├── vagas_linkedin.json     # Vagas coletadas do LinkedIn (gerado)
└── vagas_indeed.json       # Vagas coletadas do Indeed (gerado)
```

## 🛠️ Instalação

### Pré-requisitos
- Python 3.8+
- Google Chrome instalado
- ChromeDriver (gerenciado automaticamente)

### Passo a Passo

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd whatsapp-bot
```

2. **Instale as dependências**
```bash
pip install -r requirements.txt
```

3. **Configure as keywords**
Edite o arquivo `keywords.json` com suas palavras-chave:
```json
[
  "java",
  "react",
  "fullstack",
  "kotlin",
  "python"
]
```

4. **Execute o scraper**
```bash
# Executar todos os scrapers
python gupy_scraper.py
python linkedin_scraper.py  
python indeed_scraper.py

# Ou executar individualmente
python linkedin_scraper.py
```

## ⚙️ Configuração

### Keywords Personalizadas
Edite `keywords.json` para incluir suas tecnologias de interesse:
```json
[
  "java",
  "react",
  "nodejs",
  "python",
  "fullstack",
  "frontend",
  "backend"
]
```

### Parâmetros Ajustáveis

#### LinkedIn Scraper
```python
# Em linkedin_scraper.py
scraper = LinkedInScraper(
    headless=False,  # True para execução silenciosa
    max_scrolls=50,  # Número de scrolls para carregar vagas
    max_days_old=3   # Dias máximos de idade da vaga
)
```

#### Gupy Scraper  
```python
# Em gupy_scraper.py
scraper.scrape_jobs(
    term=keyword,
    max_pages=5,      # Páginas máximas por keyword
    max_days_old=3   # Dias máximos de idade da vaga
)
```

## 📊 Saída dos Dados

### Estrutura JSON das Vagas
```json
{
  "jobId": "4301320063",
  "link": "https://br.linkedin.com/jobs/view/...",
  "nome": "Desenvolvedor Java Pleno",
  "empresa": "Koerich Lab", 
  "localidade": "Biguaçu, SC",
  "remoto": false,
  "tipoContrato": "Efetivo",
  "promovida": false,
  "easyApply": true,
  "insights": null,
  "dataPublicacao": "2025-09-16T00:00:00",
  "dataPublicacaoStr": "Há 1 hora"
}
```

### Campos Extraídos
- **jobId**: ID único da vaga
- **link**: URL completa da vaga
- **nome**: Título da posição
- **empresa**: Nome da empresa
- **localidade**: Localização (cidade, estado)
- **remoto**: Boolean indicando se é remoto
- **tipoContrato**: Tipo de contrato (Efetivo, PJ, etc.)
- **promovida**: Se é uma vaga patrocinada
- **easyApply**: Se permite candidatura rápida
- **dataPublicacao**: Data em formato ISO
- **dataPublicacaoStr**: Data em formato relativo ("Há 2 horas")

## 🔧 Uso Avançado

### Execução Individual por Plataforma

#### LinkedIn (Recomendado)
```bash
python linkedin_scraper.py
```
- ✅ Scroll infinito para máxima cobertura
- ✅ Fechamento automático de modais de login
- ✅ Filtros pré-configurados (remoto + 24h)

#### Gupy
```bash  
python gupy_scraper.py
```
- ✅ Paginação tradicional
- ✅ Filtro de vagas remotas
- ✅ Parada inteligente em vagas antigas

#### Indeed
```bash
python indeed_scraper.py  
```
- ✅ Seletores robustos baseados em data-testid
- ✅ Filtros de remoto e 24h
- ✅ Extração completa de metadados

### Modo Headless
Para execução em background (servidor):
```python
scraper = LinkedInScraper(headless=True)
```

### Logs e Debug
O sistema fornece logs detalhados:
```
🚀 LinkedIn: iniciando scraping com 4 keywords...
📋 Keywords: ['java', 'react', 'fullstack', 'kotlin']
🔍 (1/4) Buscando por: "java"
📜 Iniciando scroll infinito para carregar mais vagas...
✅ Scroll completo: 60 cards carregados
🧾 Total coletado: 60 vagas válidas
```

## 🚨 Solução de Problemas

### Erro: ChromeDriver não encontrado
```bash
# Instale o webdriver-manager
pip install webdriver-manager
```

### Erro: Modal de login do LinkedIn
O sistema já inclui fechamento automático de modais. Se persistir:
1. Execute em modo não-headless primeiro
2. Faça login manual uma vez
3. Execute novamente em headless

### Erro: Timeout nas buscas
```python
# Aumente os timeouts
wait = WebDriverWait(self.driver, 30)  # Era 20
```

### Poucas vagas encontradas
1. Verifique se as keywords estão corretas
2. Aumente `max_scrolls` (LinkedIn) ou `max_pages` (Gupy)
3. Verifique se os filtros não estão muito restritivos

## 📈 Estatísticas de Performance

### Teste Realizado
- **Keywords**: 4 (java, react, fullstack, kotlin)
- **Tempo total**: ~5 minutos
- **Vagas coletadas**: 163 únicas
- **Taxa de sucesso**: 100%

### Breakdown por Plataforma
- **LinkedIn**: 60 vagas (java) + 60 vagas (react) + 23 vagas (fullstack) + 20 vagas (kotlin)
- **Gupy**: Varia conforme disponibilidade
- **Indeed**: Varia conforme disponibilidade

## 🔒 Considerações Legais

⚠️ **Importante**: Este projeto é para fins educacionais e de automação pessoal.

- Respeite os termos de uso das plataformas
- Use com moderação para evitar bloqueios
- Não faça scraping comercial sem autorização
- Mantenha intervalos entre execuções

## 🤝 Contribuição

Contribuições são bem-vindas! Para contribuir:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 📞 Suporte

Para dúvidas ou problemas:
- Abra uma issue no GitHub
- Verifique a seção de solução de problemas
- Consulte os logs de execução

---

**Desenvolvido com ❤️ para automatizar a busca por oportunidades de trabalho**
