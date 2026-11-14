import os
import io
import uuid
import base64
from datetime import datetime, date
from functools import wraps
from xml.sax.saxutils import escape

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "phd-sports-secret-key-2026")

# Configuração inteligente de Banco: PostgreSQL no Render ou SQLite local
database_url = os.environ.get("DATABASE_URL", "sqlite:///phd_avaliacoes.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

OBJETIVOS_AVALIACAO = (
    "Emagrecimento",
    "Ganho de massa muscular",
    "Condicionamento físico",
    "Saúde e qualidade de vida",
    "Performance esportiva",
    "Manutenção do peso",
    "Outro",
)

DISPONIBILIDADES_TREINO = (
    "1x por semana",
    "2x por semana",
    "3x por semana",
    "4x por semana",
    "5x por semana",
    "6x por semana",
    "Todos os dias",
    "Variável",
    "Outro",
)

# ==========================================
# MODELOS DO BANCO DE DADOS
# ==========================================


class Aluno(db.Model):
    __tablename__ = "alunos"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    sexo = db.Column(db.String(1), nullable=False)  # 'M' ou 'F'
    data_nascimento = db.Column(db.Date, nullable=False)
    telefone = db.Column(db.String(30), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    avaliacoes = db.relationship("Avaliacao", backref="aluno", lazy=True, order_by="desc(Avaliacao.data_avaliacao)")

    @property
    def idade(self):
        hoje = date.today()
        return hoje.year - self.data_nascimento.year - ((hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day))


class Avaliacao(db.Model):
    __tablename__ = "avaliacoes"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    aluno_id = db.Column(db.Integer, db.ForeignKey("alunos.id"), nullable=False)
    data_avaliacao = db.Column(db.DateTime, default=datetime.utcnow)

    # Anamnese
    peso = db.Column(db.Float, nullable=False)
    altura = db.Column(db.Float, nullable=False)  # em metros (ex: 1.75)
    objetivo = db.Column(db.Text)
    historico_atividade = db.Column(db.Text)
    doencas = db.Column(db.Text)
    remedios = db.Column(db.Text)
    historico_familiar = db.Column(db.Text)
    lesoes = db.Column(db.Text)
    profissao = db.Column(db.String(120))
    alimentacao = db.Column(db.Text)
    sono = db.Column(db.String(120))
    disponibilidade_treino = db.Column(db.String(120))

    # Circunferências (cm)
    pescoco = db.Column(db.Float)
    ombro = db.Column(db.Float)
    torax_inspirado = db.Column(db.Float)
    torax_expirado = db.Column(db.Float)
    peito = db.Column(db.Float)
    cintura = db.Column(db.Float)
    abdomen = db.Column(db.Float)
    quadril = db.Column(db.Float)

    coxa_e_relaxada = db.Column(db.Float)
    coxa_e_contraida = db.Column(db.Float)
    coxa_d_relaxada = db.Column(db.Float)
    coxa_d_contraida = db.Column(db.Float)
    panturrilha_e = db.Column(db.Float)
    panturrilha_d = db.Column(db.Float)

    braco_e_relaxado = db.Column(db.Float)
    braco_e_contraido = db.Column(db.Float)
    braco_d_relaxado = db.Column(db.Float)
    braco_d_contraido = db.Column(db.Float)
    antebraco_e = db.Column(db.Float)
    antebraco_d = db.Column(db.Float)

    # Dobras Cutâneas (mm)
    dobra_biceps = db.Column(db.Float)
    dobra_triceps = db.Column(db.Float)
    dobra_axilar = db.Column(db.Float)
    dobra_subescapular = db.Column(db.Float)
    dobra_peitoral = db.Column(db.Float)
    dobra_suprailiaca = db.Column(db.Float)
    dobra_abdominal = db.Column(db.Float)
    dobra_coxa = db.Column(db.Float)
    dobra_panturrilha = db.Column(db.Float)

    # Flexibilidade & Fechamento
    banco_well = db.Column(db.Float)
    consideracoes = db.Column(db.Text)

    # Índices Calculados
    imc = db.Column(db.Float)
    classificacao_imc = db.Column(db.String(50))
    percentual_gordura = db.Column(db.Float)
    massa_gorda = db.Column(db.Float)
    massa_magra = db.Column(db.Float)


with app.app_context():
    db.create_all()

# ==========================================
# FUNÇÕES AUXILIARES E CÁLCULOS
# ==========================================


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def to_float(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def recuperar_opcoes_salvas(valor, opcoes):
    selecionadas = []
    outro_texto = []

    for item in (valor or "").split(" | "):
        if item in opcoes:
            if item not in selecionadas:
                selecionadas.append(item)
        elif item.startswith("Outro:"):
            if "Outro" in opcoes and "Outro" not in selecionadas:
                selecionadas.append("Outro")
            detalhe = item.partition(":")[2].strip()
            if detalhe:
                outro_texto.append(detalhe)
        elif item:
            if "Outro" in opcoes and "Outro" not in selecionadas:
                selecionadas.append("Outro")
            outro_texto.append(item)

    return selecionadas, "; ".join(outro_texto)


def calcular_metricas(peso, altura, sexo, idade, dobras_7):
    # 1. IMC
    imc = round(peso / (altura**2), 2) if (peso and altura and altura > 0) else None
    classificacao = ""
    if imc:
        if imc < 18.5:
            classificacao = "Abaixo do peso"
        elif imc < 25:
            classificacao = "Peso normal"
        elif imc < 30:
            classificacao = "Sobrepeso"
        elif imc < 35:
            classificacao = "Obesidade Grau I"
        elif imc < 40:
            classificacao = "Obesidade Grau II"
        else:
            classificacao = "Obesidade Grau III"

    # 2. Pollock 7 Dobras (Peitoral, Axilar, Tríceps, Subescapular, Abdominal, Suprailíaca, Coxa)
    perc_gordura = None
    massa_gorda = None
    massa_magra = None

    if all(d is not None and d > 0 for d in dobras_7):
        soma_7 = sum(dobras_7)
        if sexo == "M":
            dc = 1.112 - (0.00043499 * soma_7) + (0.00000055 * (soma_7**2)) - (0.00028826 * idade)
        else:
            dc = 1.097 - (0.00046971 * soma_7) + (0.00000056 * (soma_7**2)) - (0.00012828 * idade)

        if dc > 0:
            perc_gordura = round(((495 / dc) - 450), 2)
            perc_gordura = max(2.0, min(perc_gordura, 65.0))
            massa_gorda = round(peso * (perc_gordura / 100), 2)
            massa_magra = round(peso - massa_gorda, 2)

    return imc, classificacao, perc_gordura, massa_gorda, massa_magra


def gerar_qr_base64(url):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111111", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ==========================================
# ROTAS DO SISTEMA
# ==========================================


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("username", "").strip()
        senha = request.form.get("password", "").strip()
        if usuario == "admin" and senha == "admin":
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha inválidos. Use admin / admin.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    busca = request.args.get("q", "").strip()
    if busca:
        alunos = Aluno.query.filter(Aluno.nome.ilike(f"%{busca}%")).order_by(Aluno.nome).all()
    else:
        alunos = Aluno.query.order_by(Aluno.criado_em.desc()).all()
    return render_template("dashboard.html", alunos=alunos, busca=busca)


@app.route("/alunos/novo", methods=["POST"])
@login_required
def novo_aluno():
    nome = request.form.get("nome", "").strip()
    sexo = request.form.get("sexo", "M")
    data_nasc_str = request.form.get("data_nascimento", "").strip()
    telefone = request.form.get("telefone", "").strip()

    if not nome or not data_nasc_str:
        flash("Preencha o nome e a data de nascimento do aluno.", "error")
        return redirect(url_for("dashboard"))

    data_nasc = None
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            data_nasc = datetime.strptime(data_nasc_str, formato).date()
            break
        except ValueError:
            continue

    if data_nasc is None:
        flash("Data de nascimento inválida. Informe no formato DD/MM/AAAA.", "error")
        return redirect(url_for("dashboard"))

    aluno = Aluno(nome=nome, sexo=sexo, data_nascimento=data_nasc, telefone=telefone)
    db.session.add(aluno)
    db.session.commit()

    return redirect(url_for("nova_avaliacao", aluno_id=aluno.id))


@app.route("/alunos/<int:aluno_id>")
@login_required
def perfil_aluno(aluno_id):
    aluno = Aluno.query.get_or_404(aluno_id)
    return render_template("aluno.html", aluno=aluno)


@app.route("/alunos/<int:aluno_id>/avaliar", methods=["GET", "POST"])
@login_required
def nova_avaliacao(aluno_id):
    aluno = Aluno.query.get_or_404(aluno_id)
    ultima_av = aluno.avaliacoes[0] if aluno.avaliacoes else None

    if request.method == "POST":
        peso = to_float(request.form.get("peso"))
        altura = to_float(request.form.get("altura"))

        if not peso or not altura:
            flash("Peso e Altura são obrigatórios para salvar a avaliação.", "error")
            return redirect(url_for("nova_avaliacao", aluno_id=aluno.id))

        # Normaliza altura caso o professor digite em cm (ex: 175 -> 1.75)
        if altura > 3:
            altura = round(altura / 100, 2)

        d_biceps = to_float(request.form.get("dobra_biceps"))
        d_triceps = to_float(request.form.get("dobra_triceps"))
        d_axilar = to_float(request.form.get("dobra_axilar"))
        d_subescapular = to_float(request.form.get("dobra_subescapular"))
        d_peitoral = to_float(request.form.get("dobra_peitoral"))
        d_suprailiaca = to_float(request.form.get("dobra_suprailiaca"))
        d_abdominal = to_float(request.form.get("dobra_abdominal"))
        d_coxa = to_float(request.form.get("dobra_coxa"))
        d_panturrilha = to_float(request.form.get("dobra_panturrilha"))

        dobras_7 = [d_peitoral, d_axilar, d_triceps, d_subescapular, d_abdominal, d_suprailiaca, d_coxa]

        imc, class_imc, perc_gordura, m_gorda, m_magra = calcular_metricas(peso, altura, aluno.sexo, aluno.idade, dobras_7)
        objetivos_selecionados = [
            item for item in request.form.getlist("objetivo_opcoes") if item in OBJETIVOS_AVALIACAO
        ]
        objetivo_outro = request.form.get("objetivo_outro", "").strip()
        if objetivo_outro and "Outro" in objetivos_selecionados:
            objetivos_selecionados.remove("Outro")
            objetivos_selecionados.append(f"Outro: {objetivo_outro}")
        objetivo = " | ".join(objetivos_selecionados) or None

        disponibilidade = request.form.get("disponibilidade_treino", "")
        if disponibilidade not in DISPONIBILIDADES_TREINO:
            disponibilidade = ""
        if disponibilidade == "Outro":
            disponibilidade_outro = request.form.get("disponibilidade_outro", "").strip()
            disponibilidade = f"Outro: {disponibilidade_outro}" if disponibilidade_outro else "Outro"

        av = Avaliacao(
            aluno_id=aluno.id,
            peso=peso,
            altura=altura,
            objetivo=objetivo,
            historico_atividade=request.form.get("historico_atividade"),
            doencas=request.form.get("doencas"),
            remedios=request.form.get("remedios"),
            historico_familiar=request.form.get("historico_familiar"),
            lesoes=request.form.get("lesoes"),
            profissao=request.form.get("profissao"),
            alimentacao=request.form.get("alimentacao"),
            sono=request.form.get("sono"),
            disponibilidade_treino=disponibilidade or None,
            pescoco=to_float(request.form.get("pescoco")),
            ombro=to_float(request.form.get("ombro")),
            torax_inspirado=to_float(request.form.get("torax_inspirado")),
            torax_expirado=to_float(request.form.get("torax_expirado")),
            peito=to_float(request.form.get("peito")),
            cintura=to_float(request.form.get("cintura")),
            abdomen=to_float(request.form.get("abdomen")),
            quadril=to_float(request.form.get("quadril")),
            coxa_e_relaxada=to_float(request.form.get("coxa_e_relaxada")),
            coxa_e_contraida=to_float(request.form.get("coxa_e_contraida")),
            coxa_d_relaxada=to_float(request.form.get("coxa_d_relaxada")),
            coxa_d_contraida=to_float(request.form.get("coxa_d_contraida")),
            panturrilha_e=to_float(request.form.get("panturrilha_e")),
            panturrilha_d=to_float(request.form.get("panturrilha_d")),
            braco_e_relaxado=to_float(request.form.get("braco_e_relaxado")),
            braco_e_contraido=to_float(request.form.get("braco_e_contraido")),
            braco_d_relaxado=to_float(request.form.get("braco_d_relaxado")),
            braco_d_contraido=to_float(request.form.get("braco_d_contraido")),
            antebraco_e=to_float(request.form.get("antebraco_e")),
            antebraco_d=to_float(request.form.get("antebraco_d")),
            dobra_biceps=d_biceps,
            dobra_triceps=d_triceps,
            dobra_axilar=d_axilar,
            dobra_subescapular=d_subescapular,
            dobra_peitoral=d_peitoral,
            dobra_suprailiaca=d_suprailiaca,
            dobra_abdominal=d_abdominal,
            dobra_coxa=d_coxa,
            dobra_panturrilha=d_panturrilha,
            banco_well=to_float(request.form.get("banco_well")),
            consideracoes=request.form.get("consideracoes"),
            imc=imc,
            classificacao_imc=class_imc,
            percentual_gordura=perc_gordura,
            massa_gorda=m_gorda,
            massa_magra=m_magra,
        )

        db.session.add(av)
        db.session.commit()
        session["completed_assessment_student_id"] = aluno.id
        return redirect(url_for("resultado_avaliacao", token=av.token))

    objetivos_selecionados, objetivo_outro = recuperar_opcoes_salvas(
        ultima_av.objetivo if ultima_av else None,
        OBJETIVOS_AVALIACAO,
    )
    disponibilidade_selecionada, disponibilidade_outro = recuperar_opcoes_salvas(
        ultima_av.disponibilidade_treino if ultima_av else None,
        DISPONIBILIDADES_TREINO,
    )
    return render_template(
        "avaliar.html",
        aluno=aluno,
        disponibilidade_opcao=disponibilidade_selecionada[0] if disponibilidade_selecionada else "",
        disponibilidade_opcoes=DISPONIBILIDADES_TREINO,
        disponibilidade_outro=disponibilidade_outro,
        objetivos_opcoes=OBJETIVOS_AVALIACAO,
        objetivos_selecionados=objetivos_selecionados,
        objetivo_outro=objetivo_outro,
        ultima_av=ultima_av,
    )


@app.route("/avaliacao/<token>")
@login_required
def resultado_avaliacao(token):
    av = Avaliacao.query.filter_by(token=token).first_or_404()
    clear_draft = session.pop("completed_assessment_student_id", None) == av.aluno_id
    avaliacoes = av.aluno.avaliacoes
    indice_avaliacao = next((i for i, item in enumerate(avaliacoes) if item.id == av.id), None)
    av_anterior = (
        avaliacoes[indice_avaliacao + 1]
        if indice_avaliacao is not None and indice_avaliacao + 1 < len(avaliacoes)
        else None
    )
    historico = []
    if indice_avaliacao is not None:
        historico = [
            {
                "data": item.data_avaliacao.strftime("%d/%m/%y"),
                "peso": item.peso,
                "percentual_gordura": item.percentual_gordura,
            }
            for item in reversed(avaliacoes[indice_avaliacao : indice_avaliacao + 6])
        ]
    pdf_url = url_for("baixar_pdf_publico", token=av.token, _external=True)
    qr_b64 = gerar_qr_base64(pdf_url)
    return render_template(
        "resultado.html",
        av=av,
        av_anterior=av_anterior,
        clear_draft=clear_draft,
        historico=historico,
        qr_b64=qr_b64,
        pdf_url=pdf_url,
    )


# ==========================================
# ROTA PÚBLICA DO QR CODE (GERAÇÃO DE PDF ON-THE-FLY)
# ==========================================


@app.route("/pdf/<token>")
def baixar_pdf_publico(token):
    av = Avaliacao.query.filter_by(token=token).first_or_404()
    aluno = av.aluno

    # Busca avaliação anterior para comparativo de evolução
    todas_avs = aluno.avaliacoes
    idx = todas_avs.index(av)
    av_anterior = todas_avs[idx + 1] if (idx + 1) < len(todas_avs) else None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=24, bottomMargin=24)

    # Paleta do site em uma versão adequada para impressão.
    PHD_DARK = colors.HexColor("#0C1523")
    PHD_BLUE = colors.HexColor("#203D68")
    PHD_ACCENT = colors.HexColor("#FFE600")
    PHD_LIGHT_ACCENT = colors.HexColor("#FFF9C2")
    PHD_GRAY_BG = colors.HexColor("#F8FAFC")
    PHD_BORDER = colors.HexColor("#D1D5DB")

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle("PhdTitle", parent=styles["Heading1"], fontSize=16, textColor=PHD_DARK, alignment=TA_LEFT, leading=20)
    style_sub = ParagraphStyle("PhdSub", parent=styles["Normal"], fontSize=9, textColor=PHD_BLUE, alignment=TA_RIGHT)
    style_sec = ParagraphStyle(
        "PhdSec", parent=styles["Heading2"], fontSize=10, textColor=PHD_DARK, backColor=PHD_ACCENT, borderPadding=(4, 6, 4, 6), spaceBefore=8, spaceAfter=4
    )
    style_cell = ParagraphStyle("PhdCell", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=PHD_DARK)

    elements = []

    def val(value):
        if value in (None, ""):
            return "-"
        return escape(str(value).replace(" | ", ", "))

    # Cabeçalho estilo Ph.D Sports
    header_data = [
        [
            Paragraph(f"<b>{val('PH.D SPORTS')}</b><br/><font size=9 color='#203D68'>RELATÓRIO DE AVALIAÇÃO FÍSICA</font>", style_title),
            Paragraph(f"<b>DATA:</b> {av.data_avaliacao.strftime('%d/%m/%Y')}<br/><b>PROTOCOLO:</b> Pollock 7 Dobras", style_sub),
        ]
    ]
    header_table = Table(header_data, colWidths=[350, 189])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, PHD_BORDER),
                ("LINEBELOW", (0, 0), (-1, -1), 3, PHD_ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 8))

    # Dados do Aluno + Indicadores Principais
    sexo_label = "Masculino" if aluno.sexo == "M" else "Feminino"
    gordura_str = f"{av.percentual_gordura}%" if av.percentual_gordura else "N/I"
    magra_str = f"{av.massa_magra} kg" if av.massa_magra else "N/I"
    gorda_str = f"{av.massa_gorda} kg" if av.massa_gorda else "N/I"

    resumo_data = [
        [
            Paragraph(f"<b>ALUNO:</b> {val(aluno.nome.upper())}", style_cell),
            Paragraph(f"<b>IDADE:</b> {aluno.idade} anos ({sexo_label})", style_cell),
            Paragraph(f"<b>PESO / ALTURA:</b> {av.peso} kg / {av.altura} m", style_cell),
        ],
        [
            Paragraph(f"<b>IMC:</b> {av.imc} ({av.classificacao_imc})", style_cell),
            Paragraph(f"<b>% GORDURA:</b> {gordura_str}", style_cell),
            Paragraph(f"<b>MASSA MAGRA / GORDA:</b> {magra_str} / {gorda_str}", style_cell),
        ],
    ]
    resumo_table = Table(resumo_data, colWidths=[215, 145, 179])
    resumo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PHD_GRAY_BG),
                ("BOX", (0, 0), (-1, -1), 0.8, PHD_DARK),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, PHD_BORDER),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(resumo_table)

    # Comparativo de Evolução (se existir avaliação anterior)
    if av_anterior:
        diff_peso = round(av.peso - av_anterior.peso, 2)
        sinal_p = "+" if diff_peso > 0 else ""
        diff_g = ""
        if av.percentual_gordura and av_anterior.percentual_gordura:
            dg = round(av.percentual_gordura - av_anterior.percentual_gordura, 2)
            sinal_g = "+" if dg > 0 else ""
            diff_g = f" | <b>Variação % Gordura:</b> {sinal_g}{dg}%"

        evo_table = Table(
            [
                [
                    Paragraph(
                        f"<b>EVOLUÇÃO DESDE {av_anterior.data_avaliacao.strftime('%d/%m/%Y')}:</b> " f"<b>Peso:</b> {sinal_p}{diff_peso} kg{diff_g}", style_cell
                    )
                ]
            ],
            colWidths=[539],
        )
        evo_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PHD_LIGHT_ACCENT),
                    ("BOX", (0, 0), (-1, -1), 0.6, PHD_ACCENT),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(Spacer(1, 4))
        elements.append(evo_table)

    # Bloco 1: Anamnese
    elements.append(Paragraph("<b>1. ANAMNESE</b>", style_sec))

    anam_data = [
        [Paragraph(f"<b>Objetivo:</b> {val(av.objetivo)}", style_cell), Paragraph(f"<b>Profissão:</b> {val(av.profissao)}", style_cell)],
        [
            Paragraph(f"<b>Histórico de Atividade:</b> {val(av.historico_atividade)}", style_cell),
            Paragraph(f"<b>Disponibilidade Treino:</b> {val(av.disponibilidade_treino)}", style_cell),
        ],
        [Paragraph(f"<b>Doenças:</b> {val(av.doencas)}", style_cell), Paragraph(f"<b>Histórico Familiar:</b> {val(av.historico_familiar)}", style_cell)],
        [Paragraph(f"<b>Remédios:</b> {val(av.remedios)}", style_cell), Paragraph(f"<b>Lesões:</b> {val(av.lesoes)}", style_cell)],
        [Paragraph(f"<b>Alimentação:</b> {val(av.alimentacao)}", style_cell), Paragraph(f"<b>Sono:</b> {val(av.sono)}", style_cell)],
    ]
    anam_table = Table(anam_data, colWidths=[269.5, 269.5])
    anam_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, PHD_BORDER),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(anam_table)

    # Bloco 2: Circunferências (cm)
    elements.append(Paragraph("<b>2. CIRCUNFERÊNCIAS (cm)</b>", style_sec))

    def fmt(num, unit=""):
        return f"{num} {unit}".strip() if num is not None else "-"

    circ_data = [
        ["Tronco", "Medida", "Membros Inferiores", "Medida", "Membros Superiores", "Medida"],
        ["Pescoço", fmt(av.pescoco), "Coxa E. Relaxada", fmt(av.coxa_e_relaxada), "Braço E. Relaxado", fmt(av.braco_e_relaxado)],
        ["Ombro", fmt(av.ombro), "Coxa E. Contraída", fmt(av.coxa_e_contraida), "Braço E. Contraído", fmt(av.braco_e_contraido)],
        ["Tórax Inspirado", fmt(av.torax_inspirado), "Coxa D. Relaxada", fmt(av.coxa_d_relaxada), "Braço D. Relaxado", fmt(av.braco_d_relaxado)],
        ["Tórax Expirado", fmt(av.torax_expirado), "Coxa D. Contraída", fmt(av.coxa_d_contraida), "Braço D. Contraído", fmt(av.braco_d_contraido)],
        ["Peito", fmt(av.peito), "Panturrilha Esq.", fmt(av.panturrilha_e), "Antebraço Esq.", fmt(av.antebraco_e)],
        ["Cintura", fmt(av.cintura), "Panturrilha Dir.", fmt(av.panturrilha_d), "Antebraço Dir.", fmt(av.antebraco_d)],
        ["Abdômen", fmt(av.abdomen), "Quadril", fmt(av.quadril), "", ""],
    ]
    circ_table = Table(circ_data, colWidths=[105, 74.6, 105, 74.6, 105, 74.8])
    circ_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PHD_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, PHD_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PHD_GRAY_BG]),
                ("PADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    elements.append(circ_table)

    # Bloco 3: Dobras Cutâneas (mm) & Flexibilidade
    elements.append(Paragraph("<b>3. DOBRAS CUTÂNEAS (mm) & FLEXIBILIDADE</b>", style_sec))
    dobras_data = [
        ["Dobra", "mm", "Dobra", "mm", "Dobra / Teste", "Resultado"],
        ["Bíceps", fmt(av.dobra_biceps), "Subescapular", fmt(av.dobra_subescapular), "Abdominal", fmt(av.dobra_abdominal)],
        ["Tríceps", fmt(av.dobra_triceps), "Peitoral", fmt(av.dobra_peitoral), "Coxa", fmt(av.dobra_coxa)],
        ["Axilar Média", fmt(av.dobra_axilar), "Suprailíaca", fmt(av.dobra_suprailiaca), "Panturrilha", fmt(av.dobra_panturrilha)],
        ["Banco de Well", fmt(av.banco_well, "cm"), "", "", "", ""],
    ]
    dobras_table = Table(dobras_data, colWidths=[105, 74.6, 105, 74.6, 105, 74.8])
    dobras_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PHD_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, PHD_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PHD_GRAY_BG]),
                ("PADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    elements.append(dobras_table)

    # Bloco 4: Considerações
    elements.append(Paragraph("<b>4. CONSIDERAÇÕES DO AVALIADOR</b>", style_sec))
    cons_table = Table([[Paragraph(val(av.consideracoes), style_cell)]], colWidths=[539])
    cons_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, PHD_BORDER),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(cons_table)

    doc.build(elements)
    buffer.seek(0)

    nome_arquivo = f"Avaliacao_PhD_{aluno.nome.replace(' ', '_')}_{av.data_avaliacao.strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=nome_arquivo, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
