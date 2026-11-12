import os
import re
from contextlib import contextmanager
from datetime import timedelta
from functools import wraps

import pyodbc
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "techstock")
app.permanent_session_lifetime = timedelta(hours=8)

PAGAMENTOS = {
    "PIX": "PIX",
    "CARTAO_CREDITO": "Cartão de crédito",
    "BOLETO_FATURADO": "Boleto faturado",
}


class ErroVenda(Exception):
    """Regra de negocio violada durante uma transacao de venda."""


# Conexao com o SQL Server
# Troque o SERVER pelo nome que aparece quando voce abre o SSMS
def conectar(autocommit=False):
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost\\SQLEXPRESS;"
        "DATABASE=TechStock;"
        "Trusted_Connection=yes;",
        autocommit=autocommit,
    )


# Transacao explicita: BEGIN TRANSACTION no inicio, COMMIT se tudo der certo
# e ROLLBACK se qualquer erro acontecer dentro do bloco "with"
@contextmanager
def transacao():
    conn = conectar(autocommit=True)
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")
        yield cursor
        cursor.execute("COMMIT TRANSACTION")
    except Exception:
        cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION")
        raise
    finally:
        conn.close()


# R1 - Controle de acesso: so o login fica liberado para quem nao entrou
@app.before_request
def exigir_login():
    if request.endpoint not in ("login", "static") and "usuario_id" not in session:
        return redirect(url_for("login"))


def gerente_required(rota):
    @wraps(rota)
    def verificada(*args, **kwargs):
        if session["perfil"] != "GERENTE":
            flash("Acesso restrito ao perfil Gerente.", "erro")
            return redirect(url_for("dashboard"))
        return rota(*args, **kwargs)
    return verificada


@app.template_filter("documento")
def formatar_documento(doc):
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nome_completo, senha_hash, perfil_acesso, status
            FROM Usuarios WHERE email = ?
        """, (request.form["email"].strip(),))
        usuario = cursor.fetchone()
        conn.close()

        if (usuario is not None and usuario.status == "ATIVO"
                and check_password_hash(usuario.senha_hash, request.form["senha"])):
            session.clear()
            session.permanent = True
            session["usuario_id"] = usuario.id
            session["nome"] = usuario.nome_completo
            session["perfil"] = usuario.perfil_acesso
            return redirect(url_for("dashboard"))
        flash("Erro: e-mail ou senha invalidos, ou usuario inativo.", "erro")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# R1 - Dashboard com INNER JOIN
@app.route("/")
def dashboard():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.sku, p.nome, p.fabricante, c.nome AS categoria,
               f.razao_social AS fornecedor, p.preco, p.estoque,
               p.estoque_minimo, p.localizacao, p.licenciamento
        FROM Produtos p
        INNER JOIN Categorias c ON p.categoria_id = c.id
        INNER JOIN Fornecedores f ON p.fornecedor_id = f.id
        ORDER BY p.nome
    """)
    produtos = cursor.fetchall()
    conn.close()
    return render_template("dashboard.html", produtos=produtos)


# R2 - Cadastro de produto
@app.route("/produtos/novo", methods=["GET", "POST"])
@gerente_required
def novo_produto():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        sku = request.form["sku"].upper()
        nome = request.form["nome"]
        fabricante = request.form["fabricante"]
        tipo = request.form["tipo"]
        especificacao = request.form["especificacao"]
        licenciamento = request.form["licenciamento"]
        preco = float(request.form["preco"])
        estoque = int(request.form["estoque"])
        estoque_minimo = int(request.form["estoque_minimo"])
        localizacao = request.form["localizacao"]
        categoria_id = request.form["categoria_id"]
        fornecedor_id = request.form["fornecedor_id"]

        # licenciamento so existe para software
        if tipo != "Software" or licenciamento == "":
            licenciamento = None

        # validacoes
        cursor.execute("SELECT id FROM Produtos WHERE sku = ?", (sku,))
        sku_existente = cursor.fetchone()

        if sku_existente is not None:
            flash("Erro: ja existe um produto com esse SKU.", "erro")
        elif preco <= 0:
            flash("Erro: o preco precisa ser maior que zero.", "erro")
        elif estoque < 0 or estoque_minimo < 0:
            flash("Erro: o estoque nao pode ser negativo.", "erro")
        else:
            cursor.execute("""
                INSERT INTO Produtos (sku, nome, fabricante, tipo, especificacao,
                    licenciamento, preco, estoque, estoque_minimo, localizacao,
                    categoria_id, fornecedor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sku, nome, fabricante, tipo, especificacao, licenciamento,
                  preco, estoque, estoque_minimo, localizacao,
                  categoria_id, fornecedor_id))
            conn.commit()
            conn.close()
            flash("Produto cadastrado com sucesso!", "sucesso")
            return redirect(url_for("dashboard"))

    # busca categorias e fornecedores para os selects
    cursor.execute("SELECT id, nome FROM Categorias ORDER BY nome")
    categorias = cursor.fetchall()
    cursor.execute("SELECT id, razao_social FROM Fornecedores ORDER BY razao_social")
    fornecedores = cursor.fetchall()
    conn.close()
    return render_template("produto_form.html", categorias=categorias, fornecedores=fornecedores)


# R3 - Entrada e saida de estoque
@app.route("/movimentacao", methods=["GET", "POST"])
@gerente_required
def movimentacao():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        produto_id = request.form["produto_id"]
        tipo = request.form["tipo"]
        quantidade = int(request.form["quantidade"])
        observacao = request.form["observacao"]

        cursor.execute("SELECT nome, estoque FROM Produtos WHERE id = ?", (produto_id,))
        produto = cursor.fetchone()

        if quantidade <= 0:
            flash("Erro: a quantidade precisa ser maior que zero.", "erro")
        elif tipo == "Saida" and quantidade > produto.estoque:
            flash("Erro: saida bloqueada. Estoque disponivel de " + produto.nome +
                  ": " + str(produto.estoque) + " unidades.", "erro")
        else:
            if tipo == "Entrada":
                cursor.execute("UPDATE Produtos SET estoque = estoque + ? WHERE id = ?",
                               (quantidade, produto_id))
            else:
                cursor.execute("UPDATE Produtos SET estoque = estoque - ? WHERE id = ?",
                               (quantidade, produto_id))

            cursor.execute("""
                INSERT INTO Movimentacoes (tipo, quantidade, observacao, produto_id)
                VALUES (?, ?, ?, ?)
            """, (tipo, quantidade, observacao, produto_id))
            conn.commit()
            conn.close()
            flash("Movimentacao registrada com sucesso!", "sucesso")
            return redirect(url_for("dashboard"))

    cursor.execute("SELECT id, sku, nome, estoque FROM Produtos ORDER BY nome")
    produtos = cursor.fetchall()
    cursor.execute("""
        SELECT TOP 10 m.data_hora, p.sku, p.nome, m.tipo, m.quantidade, m.observacao
        FROM Movimentacoes m
        INNER JOIN Produtos p ON m.produto_id = p.id
        ORDER BY m.id DESC
    """)
    historico = cursor.fetchall()
    conn.close()
    return render_template("movimentacao.html", produtos=produtos, historico=historico)


# R4 - Exclusao de itens
@app.route("/produtos/<int:id>/excluir", methods=["POST"])
@gerente_required
def excluir_produto(id):
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Produtos WHERE id = ?", (id,))
        conn.commit()
        flash("Produto excluido com sucesso.", "sucesso")
    except pyodbc.IntegrityError:
        flash("Nao e possivel excluir: este produto possui movimentacoes ou vendas registradas.", "erro")
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/cadastros")
@gerente_required
def cadastros():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM Categorias ORDER BY nome")
    categorias = cursor.fetchall()
    cursor.execute("SELECT id, razao_social, cnpj FROM Fornecedores ORDER BY razao_social")
    fornecedores = cursor.fetchall()
    conn.close()
    return render_template("cadastros.html", categorias=categorias, fornecedores=fornecedores)

# Cadastro de fornecedor
@app.route("/fornecedores/novo", methods=["GET", "POST"])
@gerente_required
def novo_fornecedor():
    if request.method == "POST":
        razao_social = request.form["razao_social"]
        cnpj = request.form["cnpj"]
        telefone = request.form["telefone"]
        email = request.form["email"]

        # deixa so os numeros do CNPJ
        cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "").strip()

        if len(cnpj) != 14 or not cnpj.isdigit():
            flash("Erro: o CNPJ precisa ter 14 numeros.", "erro")
        else:
            conn = conectar()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM Fornecedores WHERE cnpj = ?", (cnpj,))
            cnpj_existente = cursor.fetchone()

            if cnpj_existente is not None:
                flash("Erro: ja existe um fornecedor com esse CNPJ.", "erro")
                conn.close()
            else:
                cursor.execute("""
                    INSERT INTO Fornecedores (razao_social, cnpj, telefone, email)
                    VALUES (?, ?, ?, ?)
                """, (razao_social, cnpj, telefone, email))
                conn.commit()
                conn.close()
                flash("Fornecedor cadastrado com sucesso!", "sucesso")
                return redirect(url_for("cadastros"))

    return render_template("fornecedor_form.html")


@app.route("/categorias/<int:id>/excluir", methods=["POST"])
@gerente_required
def excluir_categoria(id):
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Categorias WHERE id = ?", (id,))
        conn.commit()
        flash("Categoria excluida com sucesso.", "sucesso")
    except pyodbc.IntegrityError:
        flash("Nao e possivel excluir: esta categoria ainda possui produtos vinculados.", "erro")
    conn.close()
    return redirect(url_for("cadastros"))


@app.route("/fornecedores/<int:id>/excluir", methods=["POST"])
@gerente_required
def excluir_fornecedor(id):
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Fornecedores WHERE id = ?", (id,))
        conn.commit()
        flash("Fornecedor excluido com sucesso.", "sucesso")
    except pyodbc.IntegrityError:
        flash("Nao e possivel excluir: este fornecedor ainda possui produtos vinculados.", "erro")
    conn.close()
    return redirect(url_for("cadastros"))


# R2 - Frente de caixa: o carrinho fica na sessao como {id_do_produto: quantidade}
# e os precos sempre vem do banco, nunca do navegador
@app.route("/pdv")
def pdv():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, sku, nome, tipo, preco, estoque FROM Produtos ORDER BY nome")
    produtos = cursor.fetchall()
    conn.close()

    catalogo = {str(p.id): p for p in produtos}
    itens = [(catalogo[pid], qtd) for pid, qtd in session.get("carrinho", {}).items()
             if pid in catalogo]
    total = sum(p.preco * qtd for p, qtd in itens)
    return render_template("pdv.html", produtos=produtos, itens=itens, total=total,
                           pagamentos=PAGAMENTOS)


@app.route("/pdv/adicionar", methods=["POST"])
def adicionar_item():
    produto_id = request.form["produto_id"]
    quantidade = int(request.form["quantidade"])

    if quantidade <= 0:
        flash("Erro: a quantidade precisa ser maior que zero.", "erro")
    else:
        carrinho = session.get("carrinho", {})
        carrinho[produto_id] = carrinho.get(produto_id, 0) + quantidade
        session["carrinho"] = carrinho
    return redirect(url_for("pdv"))


@app.route("/pdv/remover/<int:id>", methods=["POST"])
def remover_item(id):
    carrinho = session.get("carrinho", {})
    carrinho.pop(str(id), None)
    session["carrinho"] = carrinho
    return redirect(url_for("pdv"))


# R3 - Checkout transacional: ou a venda inteira acontece, ou nada e gravado
def registrar_venda(carrinho, usuario_id, cliente_nome, documento, pagamento):
    with transacao() as cursor:
        itens = []
        for produto_id, quantidade in carrinho.items():
            cursor.execute("SELECT id, nome, preco FROM Produtos WHERE id = ?", (produto_id,))
            produto = cursor.fetchone()
            if produto is None:
                raise ErroVenda("um produto do carrinho nao existe mais.")
            itens.append((produto, quantidade))

        total = sum(p.preco * qtd for p, qtd in itens)
        cursor.execute("""
            INSERT INTO Vendas (cliente_nome, cliente_documento, forma_pagamento,
                                valor_total, usuario_id)
            OUTPUT INSERTED.id, INSERTED.numero_pedido
            VALUES (?, ?, ?, ?, ?)
        """, (cliente_nome, documento, pagamento, total, usuario_id))
        venda_id, numero_pedido = cursor.fetchone()

        for produto, quantidade in itens:
            cursor.execute("""
                INSERT INTO Itens_Venda (venda_id, produto_id, quantidade_vendida,
                                         preco_unitario_praticado)
                VALUES (?, ?, ?, ?)
            """, (venda_id, produto.id, quantidade, produto.preco))

            # o desconto so acontece se houver saldo no instante da atualizacao
            cursor.execute("""
                UPDATE Produtos SET estoque = estoque - ?
                WHERE id = ? AND estoque >= ?
            """, (quantidade, produto.id, quantidade))
            if cursor.rowcount == 0:
                raise ErroVenda(f"estoque insuficiente para {produto.nome} "
                                f"(pedido: {quantidade}). A venda foi desfeita.")

            cursor.execute("""
                INSERT INTO Movimentacoes (tipo, quantidade, observacao, produto_id)
                VALUES ('Saida', ?, ?, ?)
            """, (quantidade, f"Venda {numero_pedido}", produto.id))
    return venda_id


@app.route("/pdv/finalizar", methods=["POST"])
def finalizar_venda():
    carrinho = session.get("carrinho", {})
    cliente_nome = request.form["cliente_nome"].strip()
    documento = re.sub(r"\D", "", request.form["cliente_documento"])
    pagamento = request.form["forma_pagamento"]

    if not carrinho:
        flash("Erro: o carrinho esta vazio.", "erro")
    elif not cliente_nome:
        flash("Erro: informe o nome do cliente.", "erro")
    elif len(documento) not in (11, 14):
        flash("Erro: o documento precisa ser um CPF (11 numeros) ou CNPJ (14 numeros).", "erro")
    elif pagamento not in PAGAMENTOS:
        flash("Erro: forma de pagamento invalida.", "erro")
    else:
        try:
            venda_id = registrar_venda(carrinho, session["usuario_id"],
                                       cliente_nome, documento, pagamento)
        except ErroVenda as erro:
            flash(f"Erro: {erro}", "erro")
        except pyodbc.Error:
            flash("Erro ao registrar a venda. Nenhuma alteracao foi salva.", "erro")
        else:
            session.pop("carrinho")
            flash("Venda concluida com sucesso!", "sucesso")
            return redirect(url_for("detalhe_venda", id=venda_id))
    return redirect(url_for("pdv"))


# Lista de vendas: o operador ve so as proprias, o gerente ve todas e o faturamento
@app.route("/vendas")
def vendas():
    gerente = session["perfil"] == "GERENTE"
    filtro, parametros = ("", ()) if gerente else ("WHERE v.usuario_id = ?", (session["usuario_id"],))

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT v.id, v.numero_pedido, v.data_hora, v.cliente_nome, v.valor_total,
               v.status_venda, u.nome_completo AS operador
        FROM Vendas v
        INNER JOIN Usuarios u ON v.usuario_id = u.id
        {filtro}
        ORDER BY v.id DESC
    """, parametros)
    lista = cursor.fetchall()
    conn.close()

    faturamento = sum(v.valor_total for v in lista if v.status_venda == "CONCLUIDA")
    return render_template("vendas.html", vendas=lista, faturamento=faturamento)


# R4 - Recibo de faturamento
@app.route("/vendas/<int:id>")
def detalhe_venda(id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.numero_pedido, v.data_hora, v.cliente_nome, v.cliente_documento,
               v.forma_pagamento, v.valor_total, v.status_venda, v.usuario_id,
               u.nome_completo AS operador
        FROM Vendas v
        INNER JOIN Usuarios u ON v.usuario_id = u.id
        WHERE v.id = ?
    """, (id,))
    venda = cursor.fetchone()

    if venda is None or (session["perfil"] != "GERENTE" and venda.usuario_id != session["usuario_id"]):
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT p.sku, p.nome, p.tipo, i.quantidade_vendida,
               i.preco_unitario_praticado, i.subtotal_item
        FROM Itens_Venda i
        INNER JOIN Produtos p ON i.produto_id = p.id
        WHERE i.venda_id = ?
        ORDER BY p.nome
    """, (id,))
    itens = cursor.fetchall()
    conn.close()
    return render_template("venda_detalhe.html", venda=venda, itens=itens, pagamentos=PAGAMENTOS)


# Cancelamento: marca a venda como cancelada e devolve os itens ao estoque
@app.route("/vendas/<int:id>/cancelar", methods=["POST"])
@gerente_required
def cancelar_venda(id):
    try:
        with transacao() as cursor:
            cursor.execute("""
                UPDATE Vendas SET status_venda = 'CANCELADA'
                OUTPUT INSERTED.numero_pedido
                WHERE id = ? AND status_venda = 'CONCLUIDA'
            """, (id,))
            venda = cursor.fetchone()
            if venda is None:
                raise ErroVenda("esta venda nao existe ou ja foi cancelada.")

            cursor.execute("""
                UPDATE p SET p.estoque = p.estoque + i.quantidade_vendida
                FROM Produtos p
                INNER JOIN Itens_Venda i ON i.produto_id = p.id
                WHERE i.venda_id = ?
            """, (id,))
            cursor.execute("""
                INSERT INTO Movimentacoes (tipo, quantidade, observacao, produto_id)
                SELECT 'Entrada', quantidade_vendida, ?, produto_id
                FROM Itens_Venda WHERE venda_id = ?
            """, (f"Cancelamento da venda {venda.numero_pedido}", id))
        flash("Venda cancelada e estoque devolvido.", "sucesso")
    except ErroVenda as erro:
        flash(f"Erro: {erro}", "erro")
    except pyodbc.Error:
        flash("Erro ao cancelar a venda. Nenhuma alteracao foi salva.", "erro")
    return redirect(url_for("detalhe_venda", id=id))


if __name__ == "__main__":
    app.run(debug=True)
