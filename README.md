# 🦋 Loja Butterfly — Sistema de Gestão

Sistema de gerenciamento para papelaria/bazar com PDV, controle de estoque, fechamento de caixa e relatórios.

## Instalação

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Execute o sistema
python app.py
```

Acesse em: **http://localhost:5000**

## Módulos

| Módulo | Rota | Descrição |
|--------|------|-----------|
| Dashboard | `/` | Resumo do dia, gráficos, alertas |
| PDV | `/pdv` | Frente de caixa com carrinho |
| Fechamento | `/caixa` | Abrir/fechar caixa, sangria, suprimento |
| Produtos | `/produtos` | Cadastro e estoque |
| Vendas | `/vendas` | Histórico de vendas |
| Relatórios | `/relatorios` | Análises por período |

## Fluxo de uso diário

1. Acesse **Fechamento** → Abrir Caixa com saldo inicial
2. Use o **PDV** para registrar vendas
3. Ao fim do dia, acesse **Fechamento** → Fechar Caixa
4. Consulte **Relatórios** para análise

## Banco de dados

SQLite local — arquivo `butterfly.db` criado automaticamente na primeira execução com produtos de exemplo.
