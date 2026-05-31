# 🏦 Cofre — Controle Financeiro Pessoal

Aplicativo web em Python (Flask) inspirado no YNAB. Você controla 100% dos seus
dados (ficam num arquivo `cofre.db` na sua máquina) e acessa pelo **PC e pelo celular**.

## ✨ O que já vem pronto

- **Login com senha** 🔐 — no primeiro acesso você cria uma senha; depois o app fica
  protegido. Essencial antes de hospedar online.
- **Cartões de crédito com fatura** 💳 — cadastre o cartão com dia de fechamento e
  vencimento. As compras entram por ciclo de fatura, e você vê total, vencimento e
  status (paga/em aberto). Pagar a fatura é uma transferência da conta para o cartão.
- **Contas** (corrente, poupança, cartão, dinheiro, investimento) com saldo automático.
- **Lançamentos** de entrada/saída com data, categoria, descrição e observação.
- **Compras parceladas**: ao lançar um gasto, escolha em quantas vezes (ex.: 12x).
  O app cria todas as parcelas de uma vez, cada uma no mês certo, marcadas como "3/12".
  A previsão e as faturas futuras já enxergam os valores, e quando acaba, some sozinho.
- **Orçamento mensal estilo YNAB**: você atribui dinheiro a cada categoria, vê o
  "Pronto para Atribuir" e o saldo disponível **rola para o mês seguinte**. Com o
  botão **Repetir**, copia o orçamento de outro mês — em modo "só preencher vazias"
  (mantém o que você já ajustou) ou "substituir tudo".
- **Categorias agrupadas** (ex.: Contas Fixas › Aluguel), totalmente editáveis.
- **Recorrentes & previstos**: salário, aluguel, assinaturas — com botão "lançar agora".
- **Patrimônio líquido** ◈ — acompanhe tudo que você tem menos tudo que deve, mês a
  mês, com gráfico de evolução. As contas (corrente, investimento, cartão) entram
  automaticamente pelo saldo; some a elas itens manuais como imóvel, carro ou
  financiamento e atualize o valor de cada mês.
- **Previsão de orçamento**: projeta o saldo dos próximos 3/6/12 meses combinando
  os recorrentes com a média de gastos por categoria.
- **Importação semiautomática**: suba o **CSV ou OFX** do seu banco, revise,
  categorize e importe (detecta duplicatas automaticamente).
- **Painel** com saldo total, entradas/saídas do mês e gráfico de 6 meses.
- **Instalável no celular** (PWA): "Adicionar à tela inicial".

## 🔐 Senha

No primeiro `python app.py`, abra o navegador e você verá a tela para **criar a senha**.
Guarde-a bem: não há recuperação (é um app pessoal, sem e-mail). Para trocar a senha,
você pode apagar a linha `password_hash` da tabela `settings` no `cofre.db` e recriar.

## 💳 Como funciona o cartão de crédito

1. Em **Contas**, crie uma conta do tipo "Cartão de crédito" com os dias de
   **fechamento** e **vencimento** (ex.: fecha 28, vence 8).
2. Lance as compras normalmente no cartão, com categoria — elas já contam no seu
   orçamento na data da compra (filosofia YNAB: orce quando gasta, não quando paga).
3. Em **Cartões**, veja a fatura de cada ciclo, o quanto deve e quando vence.
4. Clique em **Pagar fatura** e escolha de qual conta sai o dinheiro. O app cria a
   transferência — isso reduz o saldo da conta e abate a dívida do cartão, sem contar
   como um gasto novo no orçamento.

## ▶️ Como rodar

```bash
pip install -r requirements.txt
python app.py
```

Abra **http://localhost:5000** no navegador do PC.
Na primeira vez ele cria o banco e já vem com contas e categorias de exemplo.

## 📱 Acessar pelo celular

Com o PC e o celular na **mesma rede Wi-Fi**:

1. Descubra o IP local do PC:
   - Windows: `ipconfig` (procure "Endereço IPv4", algo como `192.168.0.12`)
   - Mac/Linux: `ifconfig` ou `ip addr`
2. No celular, abra `http://SEU_IP:5000` (ex.: `http://192.168.0.12:5000`).
3. Toque em "Adicionar à tela inicial" para usar como app.

> Para acessar **fora de casa**, hospede num servidor (Railway, Render, Fly.io,
> um Raspberry Pi ou uma VPS). É um app Flask comum — qualquer host de Python serve.
> Nesse caso, coloque uma senha/login antes de expor à internet.

## 💾 Seus dados

Tudo fica no arquivo **`cofre.db`** (SQLite) na pasta do projeto.
Faça backup desse arquivo de vez em quando — é todo o seu histórico.

## 📂 Estrutura

```
app.py        → servidor Flask + proteção de login + dados iniciais
auth.py       → senha, login, logout
api.py        → API JSON (contas, lançamentos, orçamento, previsão, cartões, importação)
models.py     → tabelas do banco (valores guardados em centavos)
budget.py     → lógica do orçamento YNAB (Pronto para Atribuir, rollover)
forecast.py   → módulo de previsão
networth.py   → patrimônio líquido (ativos − passivos + evolução mensal)
cards.py      → ciclo de fatura do cartão de crédito
importer.py   → leitura de CSV e OFX
templates/    → HTML (app, login, setup)
static/       → CSS, JS e ícones
```

## 🔎 Formato de CSV aceito

O importador detecta as colunas sozinho. Funciona com cabeçalhos como
`Data; Histórico; Valor` e também com colunas separadas de entrada/saída.
Aceita números no formato brasileiro (`1.234,56`) e datas `dd/mm/aaaa`.
Arquivos `.ofx` (extrato padrão dos bancos) também funcionam direto.
