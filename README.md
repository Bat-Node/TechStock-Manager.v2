# TechStock Manager

Demanda #2026-INV05 — Módulo de Vendas, Checkout Transacional e Controle de Acesso

Projeto desenvolvido para a TechStore Informática & Serviços Corporativos, com o objetivo de organizar o estoque de equipamentos, periféricos e licenças de software.

O sistema permite consultar os produtos, cadastrar novos itens, registrar entradas e saídas de estoque e vender pelo balcão, com login, controle de acesso e recibo de faturamento.

## Funcionalidades

- Dashboard com produtos, categorias e fornecedores.
- Cadastro de produtos com seleção de categoria e fornecedor.
- Controle de entradas e saídas com histórico de movimentações.
- Bloqueio de saídas com quantidade superior ao estoque disponível.
- Alerta quando o saldo está igual ou abaixo do estoque mínimo.
- Validação de SKU duplicado, preço inválido e estoque negativo.
- Exclusão de produtos, categorias e fornecedores com proteção dos vínculos existentes.
- Login com sessão persistente e dois perfis de acesso (Operador e Gerente).
- Frente de caixa com carrinho de vários itens e cálculo automático do total.
- Checkout transacional (ACID). A venda, os itens, a baixa de estoque e as movimentações são gravados juntos. Em caso de falha, a operação inteira é desfeita.
- Recibo de faturamento com opção de impressão e identificação de componentes físicos e licenças digitais.
- Cancelamento de vendas pelo Gerente, com devolução dos itens ao estoque.

## Tecnologias utilizadas

- Python 3.14.7
- Flask 3.1.3
- pyodbc 5.3.0
- Microsoft SQL Server
- ODBC Driver 17 for SQL Server
- HTML, CSS e Jinja2

## Pré-requisitos

Para executar o projeto no Windows, instale o Python com pip, o SQL Server, o SQL Server Management Studio (SSMS) e o ODBC Driver 17 for SQL Server. O SQL Server deve estar em execução.

## Preparação do ambiente

Use a pasta do projeto completo, com os arquivos da etapa de inventário e os da etapa de vendas. O ZIP da etapa de vendas contém apenas parte do projeto. Mantenha o `database.sql`, o `requirements.txt` e os templates da etapa anterior. Se os arquivos do ZIP vierem soltos, coloque os arquivos `.html` em `templates/` e o `style.css` em `static/`, substituindo as versões anteriores.

Baixe e extraia o projeto ou clone o repositório pelo GitHub. Abra o terminal na pasta que contém o `app.py` e crie um ambiente virtual.

```bash
python -m venv .venv
```

Para ativar o ambiente no Prompt de Comando (CMD), execute o comando abaixo.

```bat
.venv\Scripts\activate.bat
```

No PowerShell, use este comando.

```powershell
.\.venv\Scripts\Activate.ps1
```

Caso o PowerShell bloqueie a ativação, use o Prompt de Comando. Com o ambiente ativo, instale as dependências.

```bash
python -m pip install -r requirements.txt
```

## Criação do banco de dados

1. Abra o SQL Server Management Studio e conecte-se à instância do SQL Server.
2. Abra o arquivo `database.sql` e execute o script completo pressionando **F5**.
3. Na mesma instância, abra o script do módulo de vendas e execute-o com **F5**.

O `database.sql` cria o banco `TechStock` e as tabelas `Categorias`, `Fornecedores`, `Produtos` e `Movimentacoes`. Ele também carrega 4 categorias, 3 fornecedores e 6 produtos de teste, entre hardware e licenças de software.

Execute cada script uma vez. Se o banco já tiver as tabelas de inventário da primeira etapa, execute apenas a migração de vendas.

### Módulo de vendas

No ZIP desta etapa, a migração se chama `database_vendas.sql`. Se o arquivo for renomeado para `migration_v2.sql` na entrega, execute-o com esse nome.

A migração adiciona três tabelas ao banco `TechStock`.

- **`Usuarios`** guarda os operadores e gerentes, com e-mail único, senha em hash, perfil de acesso e status.
- **`Vendas`** registra o número do pedido, a data e hora, o cliente, o documento, a forma de pagamento, o valor total, a situação e o operador responsável.
- **`Itens_Venda`** relaciona cada venda aos seus produtos. Guarda a quantidade e o preço praticado no momento da venda. O banco calcula o subtotal e exige quantidade e preço maiores que zero.

O script cria as seguintes contas de teste.

| Perfil | E-mail | Senha |
|---|---|---|
| Gerente | gerente@techstore.com | gerente123 |
| Operador | operador@techstore.com | operador123 |

Na versão atual do script, a lista de vendas começa vazia em um banco recém-criado. Use o roteiro de avaliação para registrar vendas pela interface. A carga inicial de vendas simuladas solicitada no enunciado ainda precisa ser incluída no SQL pela equipe.

## Configuração da conexão

A função `conectar()` do `app.py` usa estes parâmetros.

| Parâmetro | Valor |
|---|---|
| Driver | `ODBC Driver 17 for SQL Server` |
| Servidor | `localhost\SQLEXPRESS` |
| Banco | `TechStock` |
| Autenticação | `Trusted_Connection=yes` |

Caso a instância tenha outro nome, altere o valor de `SERVER` no `app.py` para o nome usado na conexão do SSMS. A opção `Trusted_Connection=yes` usa a autenticação do Windows. O usuário que executa a aplicação precisa ter acesso ao banco `TechStock`.

## Execução da aplicação

Com o banco criado, a conexão configurada e as dependências instaladas, execute o comando abaixo na pasta do projeto.

```bash
python app.py
```

Acesse [http://127.0.0.1:5000](http://127.0.0.1:5000) no navegador. O comando inicia o Flask em modo de desenvolvimento, com depuração ativada. Para encerrar, pressione **Ctrl + C** no terminal.

## Como utilizar

Entre com um dos usuários de teste. A sessão permanece ativa por até 8 horas, mesmo se o navegador for fechado.

### Perfis de acesso

| Ação | Operador | Gerente |
|---|---|---|
| Consultar o estoque no dashboard | Sim | Sim |
| Abrir a Frente de Caixa e registrar vendas | Sim | Sim |
| Consultar vendas e emitir recibos | Apenas das próprias vendas | De todas as vendas |
| Cadastrar produtos e fornecedores e definir o preço no cadastro | Não | Sim |
| Excluir produtos, categorias e fornecedores | Não | Sim |
| Registrar entradas e saídas manuais de estoque | Não | Sim |
| Ver o faturamento e cancelar vendas | Não | Sim |

### Fluxo de uma venda

1. Abra a **Frente de Caixa**, escolha o produto e a quantidade e clique em adicionar. Repita para os demais itens. O total é recalculado a cada inclusão.
2. Informe o nome e o CPF ou CNPJ do cliente, selecione a forma de pagamento e finalize a venda.
3. Confira o recibo e use o botão **Imprimir recibo** para abrir a prévia de impressão.
4. Se algum produto estiver com saldo insuficiente, o sistema exibe qual item causou o erro e desfaz toda a operação.

### Estoque e cadastros (Gerente)

Use o formulário de cadastro para adicionar produtos. Na área de movimentação, selecione o produto, o tipo de operação e a quantidade. Uma entrada aumenta o saldo e uma saída reduz o saldo. Os alertas de reposição ficam no dashboard.

O sistema bloqueia a exclusão de produtos com movimentações ou vendas registradas e de categorias ou fornecedores que ainda tenham produtos vinculados.

### Como a transação funciona

A função `transacao()` do `app.py` inicia o checkout com `BEGIN TRANSACTION`. A aplicação cria o registro em `Vendas`. Para cada produto, grava a linha em `Itens_Venda`, baixa o estoque e registra a saída em `Movimentacoes`.

A baixa usa `UPDATE ... WHERE estoque >= quantidade`, de modo que a verificação de saldo acontece junto com a atualização. Se todos os itens forem processados, o sistema executa `COMMIT`. Se um item tiver saldo insuficiente, o sistema executa `ROLLBACK` e desfaz todas as alterações da venda.

O cancelamento também acontece em uma transação. A aplicação marca a venda como `CANCELADA`, devolve os itens ao estoque e registra as entradas em `Movimentacoes`.

## Roteiro de teste para avaliação

Use um banco de teste e escolha dois produtos com pelo menos duas unidades em estoque, de preferência um item físico e uma licença digital. Anote os saldos antes de cada teste.

### 1. Conferir os perfis de acesso

1. Entre como **Operador** usando a conta da tabela acima. Confira se consegue abrir o dashboard, a Frente de Caixa e a lista de vendas.
2. Ainda como Operador, abra `http://127.0.0.1:5000/produtos/novo` pelo navegador. O sistema deve bloquear o acesso ao cadastro.
3. Saia e repita o acesso com a conta de **Gerente**. O formulário deve abrir. Depois, volte a entrar como Operador para o próximo teste.

### 2. Concluir uma venda com dois produtos

1. Na **Frente de Caixa**, adicione uma unidade de cada produto. Confira os subtotais e se a soma corresponde ao total do carrinho.
2. Informe um cliente fictício e um CPF de teste, como `12345678909`. Selecione **PIX** e clique em **Finalizar venda**.
3. No recibo, confira os dados da TechStore, o número do pedido, a data e hora, o operador, o cliente, a forma de pagamento, os itens e o valor total. Confira a identificação de item físico e licença digital. Clique em **Imprimir recibo** para abrir a prévia.
4. Em **Vendas**, confirme que o pedido aparece como concluído. No dashboard, confira se o saldo diminuiu em uma unidade para cada produto. Anote o número do pedido para testar o cancelamento.

### 3. Verificar o bloqueio por saldo insuficiente

1. Anote os saldos atuais dos dois produtos e a quantidade de pedidos na lista de vendas.
2. Na **Frente de Caixa**, adicione primeiro uma unidade de um produto com saldo suficiente. Depois, adicione o segundo produto com uma quantidade maior que o saldo disponível. Se houver duas unidades em estoque, por exemplo, peça três.
3. Preencha os dados do cliente e tente finalizar. O sistema deve indicar qual produto está com saldo insuficiente.
4. No dashboard, confira se os dois saldos continuam iguais aos valores anotados. Em **Vendas**, verifique se a quantidade de pedidos continua igual. Com a conta de Gerente, confira também se o histórico de movimentações ficou sem novas saídas dessa tentativa.

### 4. Cancelar a venda e conferir o estoque

1. Entre como **Gerente**. Em **Vendas**, abra o pedido concluído no teste 2.
2. Clique em **Cancelar venda** e confirme. O pedido deve aparecer como cancelado.
3. No dashboard, confira se uma unidade de cada produto voltou ao estoque. Na área de movimentações, confira as entradas registradas pelo cancelamento.

## Estrutura do projeto completo

```text
techstock/
├── app.py
├── database.sql
├── database_vendas.sql
├── README.md
├── requirements.txt
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── cadastros.html
    ├── dashboard.html
    ├── fornecedor_form.html
    ├── login.html
    ├── movimentacao.html
    ├── pdv.html
    ├── produto_form.html
    ├── venda_detalhe.html
    └── vendas.html
```