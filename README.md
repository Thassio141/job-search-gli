# 🤖 WhatsApp Bot - Scraper de Vagas Gupy

Script em Python para fazer scraping de vagas de emprego no portal da Gupy com paginação automática.

## 🚀 Funcionalidades

- ✅ Busca vagas por termo específico
- ✅ Filtro para vagas remotas
- ✅ Navegação automática por múltiplas páginas
- ✅ Extração de dados completos:
  - **Link** da vaga
  - **Nome** (título da vaga)
  - **Empresa**
  - **Remoto** (true/false)
  - **Tipo de Contrato** (Efetivo, Temporário, Estágio, PJ, etc.)
- ✅ Salva resultados em JSON
- ✅ Estatísticas do scraping

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

### Uso básico:
```bash
python scrape_gupy.py
```

### Personalização:
Edite as configurações no início da função `main()` em `scrape_gupy.py`:

```python
def main():
    # Configurações
    term = 'desenvolvedor python'  # Termo de busca
    remote_only = True             # True = apenas remotas, False = todas
    max_pages = 5                  # Limite de páginas
    headless = True                # False para ver o browser funcionando
```

### Exemplos de termos de busca:
- `'vagas'` - busca geral
- `'desenvolvedor python'` - específico para Python
- `'backend'` - vagas de backend
- `'estágio'` - vagas de estágio
- `'pleno'` - nível pleno

## 📊 Resultado

O script gera um arquivo `vagas_gupy.json` com as vagas encontradas:

```json
[
  {
    "link": "https://portal.gupy.io/jobs/1234567",
    "nome": "Desenvolvedor Python Sênior",
    "empresa": "Tech Company",
    "remoto": true,
    "tipoContrato": "Efetivo"
  },
  {
    "link": "https://portal.gupy.io/jobs/7654321",
    "nome": "Estágio em Desenvolvimento",
    "empresa": "StartupXYZ",
    "remoto": false,
    "tipoContrato": "Estágio"
  }
]
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
