from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from datetime import datetime, date
import sqlite3
import json

app = Flask(__name__)
app.secret_key = 'butterfly_secret_2024'

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

DB = 'butterfly.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL,
            custo REAL NOT NULL,
            estoque INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 5,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total REAL NOT NULL,
            desconto REAL DEFAULT 0,
            forma_pagamento TEXT NOT NULL,
            status TEXT DEFAULT 'concluida',
            observacao TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS itens_venda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );

        CREATE TABLE IF NOT EXISTS caixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE NOT NULL UNIQUE,
            saldo_inicial REAL NOT NULL DEFAULT 0,
            saldo_final REAL,
            status TEXT DEFAULT 'aberto',
            observacao TEXT,
            aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fechado_em TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movimentacoes_caixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caixa_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            descricao TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (caixa_id) REFERENCES caixa(id)
        );
    ''')

    # Dados de exemplo
    c.execute("SELECT COUNT(*) FROM produtos")
    if c.fetchone()[0] == 0:
        produtos = [
            ('Caderno Universitário 96fls', 'Cadernos', 18.90, 9.00, 30, 5),
            ('Caneta Azul BIC', 'Canetas', 1.50, 0.50, 120, 20),
            ('Lápis HB Faber-Castell', 'Lápis', 2.00, 0.80, 80, 15),
            ('Borracha Branca Faber', 'Borrachas', 1.20, 0.40, 60, 10),
            ('Tesoura Escolar 13cm', 'Acessórios', 8.90, 4.00, 25, 5),
            ('Cola Bastão 20g', 'Colas', 3.50, 1.50, 45, 10),
            ('Régua 30cm Transparente', 'Acessórios', 3.00, 1.20, 40, 8),
            ('Marca-texto Amarelo', 'Canetas', 4.50, 2.00, 35, 10),
            ('Papel Sulfite A4 500fls', 'Papéis', 32.90, 18.00, 15, 3),
            ('Pasta AZ Ofício', 'Organização', 14.90, 7.00, 20, 5),
            ('Post-it 76x76 100fls', 'Organização', 12.50, 6.00, 25, 5),
            ('Apontador com Depósito', 'Acessórios', 2.50, 1.00, 50, 10),
        ]
        c.executemany(
            "INSERT INTO produtos (nome, categoria, preco, custo, estoque, estoque_minimo) VALUES (?,?,?,?,?,?)",
            produtos
        )

    conn.commit()
    conn.close()

# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    conn = get_db()
    hoje = date.today().isoformat()

    vendas_hoje = conn.execute(
        "SELECT COALESCE(SUM(total),0) as total, COUNT(*) as qtd FROM vendas WHERE DATE(criado_em)=? AND status='concluida'", (hoje,)
    ).fetchone()

    ticket_medio = (vendas_hoje['total'] / vendas_hoje['qtd']) if vendas_hoje['qtd'] > 0 else 0

    produtos_baixos = conn.execute(
        "SELECT COUNT(*) as qtd FROM produtos WHERE estoque <= estoque_minimo AND ativo=1"
    ).fetchone()['qtd']

    total_produtos = conn.execute("SELECT COUNT(*) as qtd FROM produtos WHERE ativo=1").fetchone()['qtd']

    caixa_hoje = conn.execute("SELECT * FROM caixa WHERE data=?", (hoje,)).fetchone()

    vendas_semana = conn.execute("""
        SELECT DATE(criado_em) as dia,
               COALESCE(SUM(total),0) as total,
               COUNT(*) as qtd
        FROM vendas
        WHERE DATE(criado_em) >= DATE('now','-6 days') AND status='concluida'
        GROUP BY DATE(criado_em)
        ORDER BY dia
    """).fetchall()

    top_produtos = conn.execute("""
        SELECT p.nome, SUM(iv.quantidade) as qtd_vendida, SUM(iv.subtotal) as receita
        FROM itens_venda iv
        JOIN produtos p ON p.id = iv.produto_id
        JOIN vendas v ON v.id = iv.venda_id
        WHERE DATE(v.criado_em) >= DATE('now','-30 days') AND v.status='concluida'
        GROUP BY p.id
        ORDER BY qtd_vendida DESC
        LIMIT 5
    """).fetchall()

    pagamentos = conn.execute("""
        SELECT forma_pagamento, COUNT(*) as qtd, SUM(total) as total
        FROM vendas
        WHERE DATE(criado_em)=? AND status='concluida'
        GROUP BY forma_pagamento
    """, (hoje,)).fetchall()

    conn.close()
    return render_template('dashboard.html',
        vendas_hoje=vendas_hoje,
        ticket_medio=ticket_medio,
        produtos_baixos=produtos_baixos,
        total_produtos=total_produtos,
        caixa_hoje=caixa_hoje,
        vendas_semana=vendas_semana,
        top_produtos=top_produtos,
        pagamentos=pagamentos,
        hoje=hoje
    )

# ─── PRODUTOS ────────────────────────────────────────────────────────────────

@app.route('/produtos')
def produtos():
    conn = get_db()
    busca = request.args.get('busca', '')
    categoria = request.args.get('categoria', '')
    q = "SELECT * FROM produtos WHERE ativo=1"
    params = []
    if busca:
        q += " AND nome LIKE ?"
        params.append(f'%{busca}%')
    if categoria:
        q += " AND categoria=?"
        params.append(categoria)
    q += " ORDER BY nome"
    lista = conn.execute(q, params).fetchall()
    categorias = conn.execute("SELECT DISTINCT categoria FROM produtos WHERE ativo=1 ORDER BY categoria").fetchall()
    conn.close()
    return render_template('produtos.html', produtos=lista, categorias=categorias, busca=busca, categoria=categoria)

@app.route('/produtos/novo', methods=['GET','POST'])
def novo_produto():
    if request.method == 'POST':
        conn = get_db()
        conn.execute(
            "INSERT INTO produtos (nome, categoria, preco, custo, estoque, estoque_minimo) VALUES (?,?,?,?,?,?)",
            (request.form['nome'], request.form['categoria'],
             float(request.form['preco']), float(request.form['custo']),
             int(request.form['estoque']), int(request.form['estoque_minimo']))
        )
        conn.commit()
        conn.close()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('produtos'))
    return render_template('produto_form.html', produto=None)

@app.route('/produtos/<int:id>/editar', methods=['GET','POST'])
def editar_produto(id):
    conn = get_db()
    if request.method == 'POST':
        conn.execute(
            "UPDATE produtos SET nome=?, categoria=?, preco=?, custo=?, estoque=?, estoque_minimo=? WHERE id=?",
            (request.form['nome'], request.form['categoria'],
             float(request.form['preco']), float(request.form['custo']),
             int(request.form['estoque']), int(request.form['estoque_minimo']), id)
        )
        conn.commit()
        conn.close()
        flash('Produto atualizado!', 'success')
        return redirect(url_for('produtos'))
    produto = conn.execute("SELECT * FROM produtos WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template('produto_form.html', produto=produto)

@app.route('/produtos/<int:id>/excluir', methods=['POST'])
def excluir_produto(id):
    conn = get_db()
    conn.execute("UPDATE produtos SET ativo=0 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Produto removido!', 'warning')
    return redirect(url_for('produtos'))

@app.route('/api/produtos')
def api_produtos():
    conn = get_db()
    busca = request.args.get('q', '')
    produtos = conn.execute(
        "SELECT id, nome, preco, estoque FROM produtos WHERE ativo=1 AND nome LIKE ? ORDER BY nome LIMIT 20",
        (f'%{busca}%',)
    ).fetchall()
    conn.close()
    return jsonify([dict(p) for p in produtos])

# ─── VENDAS / PDV ────────────────────────────────────────────────────────────

@app.route('/pdv')
def pdv():
    conn = get_db()
    hoje = date.today().isoformat()
    caixa = conn.execute("SELECT * FROM caixa WHERE data=?", (hoje,)).fetchone()
    conn.close()
    if not caixa or caixa['status'] == 'fechado':
        flash('O caixa precisa estar aberto para realizar vendas.', 'danger')
        return redirect(url_for('caixa'))
    return render_template('pdv.html')

@app.route('/api/venda', methods=['POST'])
def registrar_venda():
    data = request.json
    conn = get_db()
    hoje = date.today().isoformat()
    caixa = conn.execute("SELECT * FROM caixa WHERE data=? AND status='aberto'", (hoje,)).fetchone()
    if not caixa:
        return jsonify({'erro': 'Caixa fechado'}), 400

    itens = data.get('itens', [])
    if not itens:
        return jsonify({'erro': 'Nenhum item'}), 400

    total_bruto = sum(i['preco'] * i['quantidade'] for i in itens)
    desconto = float(data.get('desconto', 0))
    total = total_bruto - desconto

    cur = conn.execute(
        "INSERT INTO vendas (total, desconto, forma_pagamento, observacao) VALUES (?,?,?,?)",
        (total, desconto, data['forma_pagamento'], data.get('observacao',''))
    )
    venda_id = cur.lastrowid

    for item in itens:
        subtotal = item['preco'] * item['quantidade']
        conn.execute(
            "INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario, subtotal) VALUES (?,?,?,?,?)",
            (venda_id, item['produto_id'], item['quantidade'], item['preco'], subtotal)
        )
        conn.execute("UPDATE produtos SET estoque=estoque-? WHERE id=?", (item['quantidade'], item['produto_id']))

    conn.execute(
        "INSERT INTO movimentacoes_caixa (caixa_id, tipo, valor, descricao) VALUES (?,?,?,?)",
        (caixa['id'], 'entrada', total, f'Venda #{venda_id}')
    )
    conn.commit()
    conn.close()
    return jsonify({'sucesso': True, 'venda_id': venda_id, 'total': total})

@app.route('/vendas')
def vendas():
    conn = get_db()
    data_ini = request.args.get('ini', date.today().isoformat())
    data_fim = request.args.get('fim', date.today().isoformat())
    lista = conn.execute("""
        SELECT v.*, COUNT(iv.id) as qtd_itens
        FROM vendas v
        LEFT JOIN itens_venda iv ON iv.venda_id = v.id
        WHERE DATE(v.criado_em) BETWEEN ? AND ?
        GROUP BY v.id ORDER BY v.criado_em DESC
    """, (data_ini, data_fim)).fetchall()
    conn.close()
    return render_template('vendas.html', vendas=lista, data_ini=data_ini, data_fim=data_fim)

@app.route('/vendas/<int:id>')
def detalhe_venda(id):
    conn = get_db()
    venda = conn.execute("SELECT * FROM vendas WHERE id=?", (id,)).fetchone()
    itens = conn.execute("""
        SELECT iv.*, p.nome FROM itens_venda iv
        JOIN produtos p ON p.id=iv.produto_id
        WHERE iv.venda_id=?
    """, (id,)).fetchall()
    conn.close()
    return render_template('detalhe_venda.html', venda=venda, itens=itens)

# ─── CAIXA ───────────────────────────────────────────────────────────────────

@app.route('/caixa', methods=['GET','POST'])
def caixa():
    conn = get_db()
    hoje = date.today().isoformat()
    caixa_hoje = conn.execute("SELECT * FROM caixa WHERE data=?", (hoje,)).fetchone()

    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'abrir' and not caixa_hoje:
            saldo_inicial = float(request.form.get('saldo_inicial', 0))
            conn.execute("INSERT INTO caixa (data, saldo_inicial) VALUES (?,?)", (hoje, saldo_inicial))
            conn.commit()
            flash('Caixa aberto com sucesso!', 'success')
            return redirect(url_for('caixa'))

        elif acao == 'fechar' and caixa_hoje and caixa_hoje['status'] == 'aberto':
            vendas_dia = conn.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM vendas WHERE DATE(criado_em)=? AND status='concluida'", (hoje,)
            ).fetchone()['t']
            saldo_final = caixa_hoje['saldo_inicial'] + vendas_dia
            obs = request.form.get('observacao','')
            conn.execute(
                "UPDATE caixa SET status='fechado', saldo_final=?, observacao=?, fechado_em=CURRENT_TIMESTAMP WHERE id=?",
                (saldo_final, obs, caixa_hoje['id'])
            )
            conn.commit()
            flash('Caixa fechado com sucesso!', 'success')
            return redirect(url_for('caixa'))

        elif acao == 'sangria' and caixa_hoje and caixa_hoje['status'] == 'aberto':
            valor = float(request.form.get('valor', 0))
            descricao = request.form.get('descricao', 'Sangria')
            conn.execute(
                "INSERT INTO movimentacoes_caixa (caixa_id, tipo, valor, descricao) VALUES (?,?,?,?)",
                (caixa_hoje['id'], 'saida', valor, descricao)
            )
            conn.commit()
            flash('Sangria registrada!', 'warning')
            return redirect(url_for('caixa'))

        elif acao == 'suprimento' and caixa_hoje and caixa_hoje['status'] == 'aberto':
            valor = float(request.form.get('valor', 0))
            descricao = request.form.get('descricao', 'Suprimento')
            conn.execute(
                "INSERT INTO movimentacoes_caixa (caixa_id, tipo, valor, descricao) VALUES (?,?,?,?)",
                (caixa_hoje['id'], 'entrada', valor, descricao)
            )
            conn.commit()
            flash('Suprimento registrado!', 'success')
            return redirect(url_for('caixa'))

    movimentacoes = []
    resumo_pagamentos = []
    vendas_dia = 0
    if caixa_hoje:
        movimentacoes = conn.execute(
            "SELECT * FROM movimentacoes_caixa WHERE caixa_id=? ORDER BY criado_em DESC",
            (caixa_hoje['id'],)
        ).fetchall()
        resumo_pagamentos = conn.execute("""
            SELECT forma_pagamento, COUNT(*) as qtd, SUM(total) as total
            FROM vendas WHERE DATE(criado_em)=? AND status='concluida'
            GROUP BY forma_pagamento
        """, (hoje,)).fetchall()
        vendas_dia = conn.execute(
            "SELECT COALESCE(SUM(total),0) as t FROM vendas WHERE DATE(criado_em)=? AND status='concluida'", (hoje,)
        ).fetchone()['t']

    historico = conn.execute(
        "SELECT * FROM caixa ORDER BY data DESC LIMIT 10"
    ).fetchall()

    conn.close()
    return render_template('caixa.html',
        caixa=caixa_hoje,
        movimentacoes=movimentacoes,
        resumo_pagamentos=resumo_pagamentos,
        vendas_dia=vendas_dia,
        historico=historico,
        hoje=hoje
    )

# ─── RELATÓRIOS ──────────────────────────────────────────────────────────────

@app.route('/relatorios')
def relatorios():
    conn = get_db()
    periodo = request.args.get('periodo', '30')
    data_ini = request.args.get('ini', '')
    data_fim = request.args.get('fim', '')

    if not data_ini:
        data_ini = conn.execute(f"SELECT DATE('now', '-{periodo} days')").fetchone()[0]
    if not data_fim:
        data_fim = date.today().isoformat()

    resumo = conn.execute("""
        SELECT
            COALESCE(SUM(total),0) as receita,
            COUNT(*) as qtd_vendas,
            COALESCE(AVG(total),0) as ticket_medio,
            COALESCE(SUM(desconto),0) as descontos
        FROM vendas
        WHERE DATE(criado_em) BETWEEN ? AND ? AND status='concluida'
    """, (data_ini, data_fim)).fetchone()

    custo_periodo = conn.execute("""
        SELECT COALESCE(SUM(iv.quantidade * p.custo),0) as custo
        FROM itens_venda iv
        JOIN produtos p ON p.id=iv.produto_id
        JOIN vendas v ON v.id=iv.venda_id
        WHERE DATE(v.criado_em) BETWEEN ? AND ? AND v.status='concluida'
    """, (data_ini, data_fim)).fetchone()['custo']

    vendas_por_dia = conn.execute("""
        SELECT DATE(criado_em) as dia, SUM(total) as total, COUNT(*) as qtd
        FROM vendas
        WHERE DATE(criado_em) BETWEEN ? AND ? AND status='concluida'
        GROUP BY DATE(criado_em) ORDER BY dia
    """, (data_ini, data_fim)).fetchall()

    por_categoria = conn.execute("""
        SELECT p.categoria, SUM(iv.quantidade) as qtd, SUM(iv.subtotal) as receita
        FROM itens_venda iv
        JOIN produtos p ON p.id=iv.produto_id
        JOIN vendas v ON v.id=iv.venda_id
        WHERE DATE(v.criado_em) BETWEEN ? AND ? AND v.status='concluida'
        GROUP BY p.categoria ORDER BY receita DESC
    """, (data_ini, data_fim)).fetchall()

    por_pagamento = conn.execute("""
        SELECT forma_pagamento, COUNT(*) as qtd, SUM(total) as total
        FROM vendas
        WHERE DATE(criado_em) BETWEEN ? AND ? AND status='concluida'
        GROUP BY forma_pagamento ORDER BY total DESC
    """, (data_ini, data_fim)).fetchall()

    top_produtos = conn.execute("""
        SELECT p.nome, p.categoria, SUM(iv.quantidade) as qtd, SUM(iv.subtotal) as receita
        FROM itens_venda iv
        JOIN produtos p ON p.id=iv.produto_id
        JOIN vendas v ON v.id=iv.venda_id
        WHERE DATE(v.criado_em) BETWEEN ? AND ? AND v.status='concluida'
        GROUP BY p.id ORDER BY receita DESC LIMIT 10
    """, (data_ini, data_fim)).fetchall()

    conn.close()
    lucro = resumo['receita'] - custo_periodo
    margem = (lucro / resumo['receita'] * 100) if resumo['receita'] > 0 else 0

    return render_template('relatorios.html',
        resumo=resumo, lucro=lucro, margem=margem,
        vendas_por_dia=vendas_por_dia,
        por_categoria=por_categoria,
        por_pagamento=por_pagamento,
        top_produtos=top_produtos,
        data_ini=data_ini, data_fim=data_fim, periodo=periodo
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
