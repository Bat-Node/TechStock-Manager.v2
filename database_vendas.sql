-- TechStock Manager - modulo de vendas (SQL Server)
-- Execute DEPOIS do database.sql, no mesmo banco. Selecione tudo e clique em Executar (F5)

USE TechStock;
GO

-- Operadores e gerentes do sistema
CREATE TABLE Usuarios (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nome_completo VARCHAR(120) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    perfil_acesso VARCHAR(10) NOT NULL CHECK (perfil_acesso IN ('OPERADOR', 'GERENTE')),
    status VARCHAR(10) NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO', 'INATIVO'))
);

-- Cabecalho da venda. O numero do pedido e gerado pelo proprio banco a partir do id
CREATE TABLE Vendas (
    id INT IDENTITY(1,1) PRIMARY KEY,
    numero_pedido AS ('PED-' + RIGHT('00000000' + CAST(id AS VARCHAR(10)), 8)) PERSISTED,
    data_hora DATETIME NOT NULL DEFAULT GETDATE(),
    cliente_nome VARCHAR(120) NOT NULL,
    cliente_documento VARCHAR(14) NOT NULL,
    forma_pagamento VARCHAR(20) NOT NULL CHECK (forma_pagamento IN ('PIX', 'CARTAO_CREDITO', 'BOLETO_FATURADO')),
    valor_total DECIMAL(12,2) NOT NULL CHECK (valor_total > 0),
    status_venda VARCHAR(10) NOT NULL DEFAULT 'CONCLUIDA' CHECK (status_venda IN ('CONCLUIDA', 'CANCELADA')),
    usuario_id INT NOT NULL FOREIGN KEY REFERENCES Usuarios(id),
    CONSTRAINT UQ_Vendas_numero_pedido UNIQUE (numero_pedido)
);

-- Itens do carrinho. O preco fica congelado aqui, sem depender da tabela Produtos
CREATE TABLE Itens_Venda (
    id INT IDENTITY(1,1) PRIMARY KEY,
    venda_id INT NOT NULL FOREIGN KEY REFERENCES Vendas(id),
    produto_id INT NOT NULL FOREIGN KEY REFERENCES Produtos(id),
    quantidade_vendida INT NOT NULL CHECK (quantidade_vendida > 0),
    preco_unitario_praticado DECIMAL(10,2) NOT NULL CHECK (preco_unitario_praticado > 0),
    subtotal_item AS (quantidade_vendida * preco_unitario_praticado) PERSISTED,
    CONSTRAINT UQ_Itens_Venda_produto UNIQUE (venda_id, produto_id)
);
GO

-- Usuarios de teste (senhas: gerente123 e operador123)
INSERT INTO Usuarios (nome_completo, email, senha_hash, perfil_acesso)
VALUES ('Marina Gerente', 'gerente@techstore.com',
        'pbkdf2:sha256:1000000$f3twK4lONdoLG1G7$be70669480cfc35d10717fdc3f90169035665d2c977b424ca5af6421adf1e208',
        'GERENTE');
INSERT INTO Usuarios (nome_completo, email, senha_hash, perfil_acesso)
VALUES ('Carlos Operador', 'operador@techstore.com',
        'pbkdf2:sha256:1000000$QKhIkKUd1oMI0Lp4$978a75f30f13f234bffc13118d5b1296fabc0a1a88fd1ba8e4e0d890a6e03e4f',
        'OPERADOR');
GO
