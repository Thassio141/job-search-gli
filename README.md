# 🤖 WhatsApp Bot - Scraper de Vagas Gupy

Script em Python para fazer scraping de vagas de emprego no portal da Gupy com paginação automática.

## 🚀 Funcionalidades

- ✅ **Busca múltipla por keywords** - busca por várias palavras-chave de uma vez
- ✅ **Filtro para vagas remotas** - aplicado automaticamente
- ✅ **Navegação automática** por múltiplas páginas
- ✅ **Deduplicação inteligente** - remove vagas duplicadas automaticamente
- ✅ **Extração de dados completos**:
  - **Link** da vaga
  - **Nome** (título da vaga)
  - **Empresa**
  - **Remoto** (true/false)
  - **Tipo de Contrato** (Efetivo, Temporário, Estágio, PJ, etc.)
- ✅ **Salva resultados em JSON**
- ✅ **Estatísticas detalhadas** por keyword e gerais

## 📋 Pré-requisitos

1. **Python 3.7+**
2. **Google Chrome** instalado
3. **ChromeDriver** baixado e configurado

### ChromeDriver
O script está configurado para usar o ChromeDriver em:
```
C:\Users\thass\Downloads\chromedriver-win64\chromedriver.exe
```

Se o seu ChromeDriver estiver em outro local, edite a linha no `scrape_gupy.py`:
```python
def __init__(self, chromedriver_path: str = r'SEU_CAMINHO_AQUI\chromedriver.exe'):
```

## 🛠️ Instalação

1. **Clone ou baixe os arquivos do projeto**

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

## 🎯 Como usar

### 1. Configure suas keywords:
Edite o arquivo `keywords.json` com as palavras-chave que deseja buscar:

```json
[
  "java",
  "react", 
  "fullstack",
  "kotlin",
  "python",
  "backend"
]
```

### 2. Execute o script:
```bash
python scrape_gupy.py
```

### 3. Personalização:
Edite as configurações no início da função `main()` em `scrape_gupy.py`:

```python
def main():
    # Configurações
    remote_only = True      # True = apenas remotas, False = todas
    max_pages = 5           # Limite de páginas por keyword
    headless = True         # False para ver o browser funcionando
```

### Exemplos de keywords:
- `"java"` - vagas de Java
- `"react"` - vagas de React
- `"fullstack"` - vagas fullstack
- `"python"` - vagas de Python
- `"backend"` - vagas de backend
- `"estágio"` - vagas de estágio

## 📊 Resultado

O script gera um arquivo `vagas_gupy.json` com **todas as vagas únicas** encontradas para todas as keywords:

```json
[
  {
    "link": "https://portal.gupy.io/jobs/1234567",
    "nome": "Desenvolvedor Java Sênior",
    "empresa": "Tech Company",
    "remoto": true,
    "tipoContrato": "Efetivo"
  },
  {
    "link": "https://portal.gupy.io/jobs/7654321",
    "nome": "Desenvolvedor React Pleno",
    "empresa": "StartupXYZ",
    "remoto": true,
    "tipoContrato": "Efetivo"
  },
  {
    "link": "https://portal.gupy.io/jobs/9876543",
    "nome": "Desenvolvedor Fullstack",
    "empresa": "Corp ABC",
    "remoto": true,
    "tipoContrato": "PJ"
  }
]
```

### Exemplo de saída no terminal:
```
🔍 Iniciando scraping de vagas da Gupy...
Keywords encontradas: java, react, fullstack, kotlin
Apenas remotas: True
Máximo de páginas por keyword: 5
--------------------------------------------------

🔍 Buscando por 'java' (1/4)...
✅ Encontradas 15 vagas para 'java'

🔍 Buscando por 'react' (2/4)...
✅ Encontradas 12 vagas para 'react'

🔍 Buscando por 'fullstack' (3/4)...
✅ Encontradas 8 vagas para 'fullstack'

🔍 Buscando por 'kotlin' (4/4)...
✅ Encontradas 3 vagas para 'kotlin'

🔄 Removendo duplicatas...
✅ Removidas 2 vagas duplicadas

✅ Salvo 36 vagas únicas em vagas_gupy.json

📊 Estatísticas Finais:
   • Total de vagas únicas: 36
   • Empresas diferentes: 25
   • Vagas remotas: 36
   • Tipos de contrato encontrados: Efetivo, PJ, Temporário

📈 Vagas por keyword:
   • java: 15 vagas
   • react: 12 vagas
   • fullstack: 8 vagas
   • kotlin: 3 vagas
```

## ⚙️ Configurações Avançadas

### Executar sem modo headless (ver o browser):
```python
headless = False
```

### Aumentar limite de páginas:
```python
max_pages = 20  # Cuidado para não sobrecarregar o servidor
```

### Incluir vagas presenciais:
```python
remote_only = False
```

## 🔧 Troubleshooting

### Erro "chromedriver not found":
- Verifique se o caminho do ChromeDriver está correto
- Baixe a versão compatível com seu Chrome em: https://chromedriver.chromium.org/

### Timeout ou elementos não encontrados:
- A Gupy pode ter alterado a estrutura da página
- Tente executar com `headless = False` para debug visual
- Aumente os timeouts se a internet estiver lenta

### Muitas vagas duplicadas:
- A Gupy às vezes mostra a mesma vaga em páginas diferentes
- Considere implementar deduplicação por link

## 🤝 Contribuindo

Sinta-se à vontade para:
- Reportar bugs
- Sugerir melhorias
- Enviar pull requests

## ⚠️ Disclaimer

Este script é apenas para fins educacionais e de aprendizado. Use com responsabilidade e respeite os termos de uso da Gupy.
