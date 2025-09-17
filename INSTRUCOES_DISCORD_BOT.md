# 🤖 Bot de Vagas do Discord

Este bot integra o sistema de scraping de vagas com o Discord, enviando automaticamente novas vagas encontradas para um canal específico.

## 📋 Funcionalidades

- ✅ **Scraping automático**: Executa o scraping a cada hora (configurável)
- ✅ **Envio para Discord**: Envia vagas encontradas para canal específico
- ✅ **Controle de duplicatas**: Evita enviar a mesma vaga duas vezes
- ✅ **Persistência**: Mantém registro de vagas enviadas mesmo após reinicialização
- ✅ **Configuração flexível**: Arquivo de configuração JSON
- ✅ **Embeds bonitos**: Vagas formatadas com cores e informações organizadas

## 🚀 Como Configurar

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 2. Criar Bot no Discord

1. Acesse [Discord Developer Portal](https://discord.com/developers/applications)
2. Clique em "New Application"
3. Dê um nome para seu bot
4. Vá para a aba "Bot"
5. Clique em "Add Bot"
6. Copie o **Token** do bot
7. Em "Privileged Gateway Intents", ative:
   - Message Content Intent

### 3. Configurar Permissões do Bot

1. Vá para a aba "OAuth2" > "URL Generator"
2. Selecione:
   - **Scopes**: `bot`
   - **Bot Permissions**: 
     - Send Messages
     - Embed Links
     - Read Message History
     - Use Slash Commands
3. Copie a URL gerada e acesse no navegador
4. Selecione o servidor e autorize o bot

### 4. Obter ID do Canal

1. No Discord, ative o "Modo Desenvolvedor" (Configurações > Avançado > Modo Desenvolvedor)
2. Clique com botão direito no canal desejado
3. Selecione "Copiar ID"

### 5. Configurar o Bot

Edite o arquivo `config.json`:

```json
{
  "discord": {
    "token": "SEU_TOKEN_DO_DISCORD_AQUI",
    "channel_id": 123456789,
    "headless": true
  },
  "scraping": {
    "interval_hours": 1,
    "max_pages_gupy": 5,
    "max_pages_indeed": 5,
    "max_scrolls_linkedin": 50,
    "max_days_old": 3
  },
  "bot": {
    "prefix": "!",
    "send_notifications": true,
    "max_jobs_per_message": 1
  }
}
```

**Substitua:**
- `SEU_TOKEN_DO_DISCORD_AQUI` pelo token do seu bot
- `123456789` pelo ID do canal onde as vagas serão enviadas

## 🎯 Como Executar

### Opção 1: Script Simples
```bash
python start_bot.py
```

### Opção 2: Execução Direta
```bash
python discord_bot.py
```

## ⚙️ Configurações Avançadas

### Intervalo de Execução
Para alterar a frequência do scraping, modifique `interval_hours` no `config.json`:

```json
"scraping": {
  "interval_hours": 2  // Executa a cada 2 horas
}
```

### Parâmetros de Scraping
Ajuste os parâmetros de cada plataforma:

```json
"scraping": {
  "max_pages_gupy": 10,      // Máximo de páginas na Gupy
  "max_pages_indeed": 8,     // Máximo de páginas no Indeed
  "max_scrolls_linkedin": 100, // Máximo de scrolls no LinkedIn
  "max_days_old": 7          // Máximo de dias de idade das vagas
}
```

## 📁 Arquivos Gerados

- `vagas_consolidadas.json`: Todas as vagas encontradas
- `vagas_enviadas.json`: Controle de vagas já enviadas
- `relatorio_execucao.json`: Relatório de execução do scraping
- `vagas_gupy.json`, `vagas_indeed.json`, `vagas_linkedin.json`: Vagas por plataforma

## ⚡ Funcionamento Automático

O bot funciona de forma completamente automática:

- **Início imediato**: Executa scraping assim que conecta ao Discord
- **Agendamento**: Repete a cada hora automaticamente  
- **Silencioso**: Funciona em background sem necessidade de comandos

## 🐛 Solução de Problemas

### Bot não conecta
- Verifique se o token está correto
- Confirme se o bot tem as permissões necessárias
- Verifique sua conexão com a internet

### Vagas não são enviadas
- Confirme se o ID do canal está correto
- Verifique se o bot tem permissão para enviar mensagens no canal
- Verifique se o arquivo `vagas_consolidadas.json` existe

### Scraping não funciona
- Verifique se o arquivo `keywords.json` existe e tem keywords válidas
- Confirme se o Chrome/ChromeDriver está instalado
- Verifique os logs para erros específicos

## 📊 Monitoramento

O bot exibe logs detalhados no console:
- ✅ Sucessos
- ❌ Erros
- 📊 Estatísticas
- ⏰ Timestamps

## 🔄 Fluxo de Funcionamento

1. **Inicialização**: Bot conecta ao Discord
2. **Execução Imediata**: Executa scraping assim que conecta
3. **Envio Inicial**: Envia vagas encontradas para o canal
4. **Agendamento**: Configura execução a cada X horas
5. **Ciclo Automático**: 
   - Executa scraping nas plataformas
   - Filtra vagas novas (não enviadas)
   - Envia vagas para o canal do Discord
   - Salva vagas enviadas para evitar duplicatas
   - Aguarda próximo ciclo

## 🛡️ Segurança

- **Nunca compartilhe seu token do Discord**
- **Mantenha o arquivo config.json privado**
- **Use permissões mínimas necessárias para o bot**

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs do console
2. Confirme todas as configurações
3. Teste com configurações mínimas primeiro
4. Verifique se todas as dependências estão instaladas
