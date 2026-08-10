from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, text as sql_text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime, timedelta
import logging
from pathlib import Path

# cria o caminho absoluto para o arquivo DB dentro da pasta 'database'
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
Base = declarative_base()

# Sessão para interagir com o banco de dados
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tabelas
class Membro(Base):  
    __tablename__ = "membros"  
    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String(100), index=True, nullable=True)
    nome = Column(String(150), index=True, nullable=False)
    apelido = Column(String(100), nullable=False)
    cargo = Column(String(50), nullable=True)
    data_entrada = Column(String(30), default=lambda: (datetime.utcnow() - timedelta(hours=3)).strftime("%d-%m-%Y %H:%M:%S"))

class Punicao(Base):
    __tablename__ = "punicoes"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    discord_id = Column(String(100), nullable=False, index=True)
    aplicado_por = Column(String(100), nullable=False)
    nome = Column(String(150), nullable=True)
    regra = Column(String(100), nullable=False)
    instancia = Column(Integer, default=1, nullable=False)  
    data_punicao = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class VoipAtivo(Base):
    __tablename__ = "voip_ativos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_servidor = Column(Integer, index=True, nullable=False)
    id_voip = Column(Integer, index=True, nullable=False, unique=True)
    id_lider = Column(Integer, index=True, nullable=False)


class VoipPreferencias(Base):
    __tablename__ = "voip_preferencias"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_servidor = Column(Integer, index=True, nullable=False)
    id_usuario = Column(Integer, index=True, nullable=False)

    nome = Column(String(100), nullable=True)
    limite_usuarios = Column(Integer, nullable=True)
    regiao = Column(String(32), nullable=True)

    bloqueado = Column(Boolean, default=False, nullable=False)
    oculto = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("id_servidor", "id_usuario", name="uq_voip_prefs_servidor_usuario"),
    )

class EmbedPersonalizado(Base):
    """Embeds em construção, isoladas por usuário e compartilhadas entre os servidores."""
    __tablename__ = "embeds_personalizados"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Integer, index=True, nullable=False)
    slot = Column(Integer, nullable=False)  # numeração exibida no painel: "Embed 1", "Embed 2"...
    # Posição da embed dentro da mensagem do slot (1..10). Uma mensagem do Discord
    # aceita várias embeds empilhadas; cada uma é uma linha desta tabela.
    parte = Column(Integer, nullable=False, default=1, server_default="1")
    nome = Column(Text, nullable=True)  # apelido opcional mostrado no menu do painel

    titulo = Column(Text, nullable=True)
    titulo_url = Column(Text, nullable=True)  # deixa o título clicável
    descricao = Column(Text, nullable=True)
    cor = Column(Integer, nullable=True)
    imagem = Column(Text, nullable=True)
    thumbnail = Column(Text, nullable=True)
    autor_nome = Column(Text, nullable=True)
    autor_icone = Column(Text, nullable=True)
    autor_url = Column(Text, nullable=True)
    rodape = Column(Text, nullable=True)
    rodape_icone = Column(Text, nullable=True)

    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("id_usuario", "slot", "parte", name="uq_embed_usuario_slot_parte"),
    )

class CorPersonalizada(Base):
    """Paleta de cores do usuário, reaproveitada em qualquer embed e servidor."""
    __tablename__ = "cores_personalizadas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Integer, index=True, nullable=False)
    nome = Column(Text, nullable=False)
    cor = Column(Integer, nullable=False)

    criado_em = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("id_usuario", "nome", name="uq_cor_usuario_nome"),
    )

class FormulariosDesenvolvedor(Base):
    __tablename__ = "formularios_desenvolvedor"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Text, index=True, unique=True, nullable=False)
    id_mensagem = Column(Text, index=True, nullable=False)
    nome = Column(Text, nullable=False)
    sexo = Column(Text, nullable=False)
    genero_favorito = Column(Text, nullable=False)
    plataforma_principal = Column(Text, nullable=False)
    redes_sociais = Column(Text, nullable=True)
    status = Column(String(50), default="pendente", nullable=False)
    data_envio = Column(DateTime, default=datetime.utcnow)

class FormulariosDesenvolvedorAprovados(Base):
    __tablename__ = "formularios_desenvolvedor_aprovados"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Integer, index=True, nullable=False)
    id_mensagem = Column(String(100), index=True, nullable=False)
    nome = Column(String(150), nullable=False)
    sexo = Column(String(32), nullable=False)
    genero_favorito = Column(String(100), nullable=False)
    plataforma_principal = Column(String(100), nullable=False)
    redes_sociais = Column(Text, nullable=True)
    status = Column(String(50), default="aprovado", nullable=False)
    data_envio = Column(DateTime, default=datetime.utcnow, nullable=True)
    aprovado_por = Column(Text, index=True, nullable=False)
    data_aprovacao = Column(DateTime, default=datetime.utcnow, nullable=True)

class FormulariosDesenvolvedorRejeitados(Base):
    __tablename__ = "formularios_desenvolvedor_rejeitados"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(Integer, index=True, nullable=False)
    id_mensagem = Column(String(100), index=True, nullable=False)
    nome = Column(String(150), nullable=False)
    sexo = Column(String(32), nullable=False)
    genero_favorito = Column(String(100), nullable=False)
    plataforma_principal = Column(String(100), nullable=False)
    redes_sociais = Column(Text, nullable=True)
    motivo = Column(Text, nullable=True)
    status = Column(String(50), default="rejeitado", nullable=False)
    data_envio = Column(DateTime, default=datetime.utcnow, nullable=True)
    rejeitado_por = Column(Text, index=True, nullable=False)
    data_rejeicao = Column(DateTime, default=datetime.utcnow, nullable=True)

# Função para criar as tabelas no banco de dados
def voip_salvar_canal_ativo(id_servidor: int, id_voip: int, id_lider: int):
    session = SessionLocal()
    try:
        row = session.query(VoipAtivo).filter_by(id_voip=int(id_voip)).first()
        if row:
            row.id_servidor = int(id_servidor)
            row.id_lider = int(id_lider)
        else:
            row = VoipAtivo(
                id_servidor=int(id_servidor),
                id_voip=int(id_voip),
                id_lider=int(id_lider),
            )
            session.add(row)
        session.commit()
        return row
    finally:
        session.close()

# Função para criar as tabelas no banco de dados
def voip_remover_canal_ativo(id_voip: int):
    session = SessionLocal()
    try:
        session.query(VoipAtivo).filter_by(id_voip=int(id_voip)).delete()
        session.commit()
    finally:
        session.close()

# Função para criar as tabelas no banco de dados
def voip_get_leader_id(id_voip: int) -> int | None:
    session = SessionLocal()
    try:
        row = session.query(VoipAtivo).filter_by(id_voip=int(id_voip)).first()
        return int(row.id_lider) if row else None
    finally:
        session.close()

# Função para criar as tabelas no banco de dados
def voip_preferencias(id_servidor: int, id_usuario: int, **fields):
    allowed = {"nome", "limite_usuarios", "regiao", "bloqueado", "oculto"}

    session = SessionLocal()
    try:
        row = session.query(VoipPreferencias).filter_by(
            id_servidor=int(id_servidor),
            id_usuario=int(id_usuario),
        ).first()

        if not fields:
            return row

        if not row:
            row = VoipPreferencias(id_servidor=int(id_servidor), id_usuario=int(id_usuario))
            session.add(row)

        for k, v in fields.items():
            if k in allowed:
                setattr(row, k, v)

        session.commit()
        return row
    finally:
        session.close()

def voip_list_ativos() -> list:
    """Retorna todas as entradas da tabela VoipAtivo como lista de dicts."""
    session = SessionLocal()
    try:
        rows = session.query(VoipAtivo).all()
        result = []
        for r in rows:
            result.append({
                "id": int(r.id),
                "id_servidor": int(r.id_servidor),
                "id_voip": int(r.id_voip),
                "id_lider": int(r.id_lider),
            })
        return result
    finally:
        session.close()
def registrar_punicao(guild_id: int, user_id: int, motivo: str, autor_id: int | None = None, timestamp=None):
    """
    Registrar uma punição no banco de dados.
    Se o modelo `Punicao` não existir, faz fallback por log.
    """
    session = SessionLocal()
    try:
        try:
            Punicao  # verifica se o modelo existe
        except NameError:
            print(f"[registrar_punicao] guild={guild_id} user={user_id} motivo={motivo} autor={autor_id}")
            return None
        else:
            # ajuste os campos abaixo conforme seu modelo `Punicao`
            p = Punicao(guild_id=guild_id, user_id=user_id, motivo=motivo, autor_id=autor_id, criado_em=timestamp)
            session.add(p)
            session.commit()
            return getattr(p, "id", None)
    finally:
        session.close()

# Campos editáveis de uma embed e teto de embeds que cada usuário pode manter.
# O limite é 25 porque é o máximo de opções que um select menu do Discord aceita.
EMBED_CAMPOS = (
    "nome",
    "titulo",
    "titulo_url",
    "descricao",
    "cor",
    "imagem",
    "thumbnail",
    "autor_nome",
    "autor_icone",
    "autor_url",
    "rodape",
    "rodape_icone",
)
EMBED_LIMITE_POR_USUARIO = 25
# Teto de embeds empilhadas em uma mesma mensagem, imposto pelo Discord.
EMBED_PARTES_POR_SLOT = 10

_tabela_embeds_pronta = False


def _migrar_unique_para_parte(conn):
    """Troca o UNIQUE(id_usuario, slot) antigo por UNIQUE(id_usuario, slot, parte).

    O SQLite não altera constraint no lugar, então a tabela é reconstruída. Roda
    dentro da transação do chamador: ou a migração inteira passa, ou nada muda.
    """
    sql_atual = conn.execute(sql_text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='embeds_personalizados'"
    )).scalar()
    if not sql_atual or "uq_embed_usuario_slot " not in sql_atual + " ":
        return

    colunas = [
        linha[1] for linha in conn.execute(sql_text("PRAGMA table_info(embeds_personalizados)"))
        if linha[1] != "id"
    ]
    lista_colunas = ", ".join(f'"{c}"' for c in colunas)
    linhas = conn.execute(sql_text(
        f"SELECT {lista_colunas} FROM embeds_personalizados"
    )).fetchall()

    conn.execute(sql_text("DROP TABLE embeds_personalizados"))
    EmbedPersonalizado.__table__.create(bind=conn)

    if linhas:
        marcadores = ", ".join(f":{c}" for c in colunas)
        conn.execute(
            sql_text(f"INSERT INTO embeds_personalizados ({lista_colunas}) VALUES ({marcadores})"),
            [dict(zip(colunas, linha)) for linha in linhas],
        )
    logger.info("Tabela embeds_personalizados reconstruída com a coluna 'parte'.")


def _garantir_tabela_embeds():
    """Cria a tabela de embeds sob demanda (o projeto não roda create_all no boot)."""
    global _tabela_embeds_pronta
    if _tabela_embeds_pronta:
        return

    EmbedPersonalizado.__table__.create(bind=engine, checkfirst=True)

    with engine.begin() as conn:
        # Acrescenta colunas que não existiam em versões anteriores da tabela
        existentes = {
            linha[1] for linha in conn.execute(sql_text("PRAGMA table_info(embeds_personalizados)"))
        }
        for coluna in EmbedPersonalizado.__table__.columns:
            if coluna.name not in existentes:
                tipo = coluna.type.compile(engine.dialect)
                padrao = " NOT NULL DEFAULT 1" if coluna.name == "parte" else ""
                conn.execute(sql_text(
                    f'ALTER TABLE embeds_personalizados ADD COLUMN "{coluna.name}" {tipo}{padrao}'
                ))
                logger.info("Coluna '%s' adicionada em embeds_personalizados.", coluna.name)

        _migrar_unique_para_parte(conn)

    _tabela_embeds_pronta = True


def _embed_para_dict(row: EmbedPersonalizado) -> dict:
    dados = {campo: getattr(row, campo) for campo in EMBED_CAMPOS}
    dados["slot"] = int(row.slot)
    dados["parte"] = int(row.parte or 1)
    dados["cor"] = int(row.cor) if row.cor is not None else None
    return dados


def embed_listar(id_usuario: int) -> list[dict]:
    """Retorna as embeds do usuário (válidas em qualquer servidor), ordenadas por slot e parte."""
    _garantir_tabela_embeds()
    session = SessionLocal()
    try:
        rows = (
            session.query(EmbedPersonalizado)
            .filter_by(id_usuario=int(id_usuario))
            .order_by(EmbedPersonalizado.slot, EmbedPersonalizado.parte)
            .all()
        )
        return [_embed_para_dict(r) for r in rows]
    finally:
        session.close()


def embed_obter(id_usuario: int, slot: int, parte: int = 1) -> dict | None:
    _garantir_tabela_embeds()
    session = SessionLocal()
    try:
        row = session.query(EmbedPersonalizado).filter_by(
            id_usuario=int(id_usuario),
            slot=int(slot),
            parte=int(parte),
        ).first()
        return _embed_para_dict(row) if row else None
    finally:
        session.close()


def embed_salvar(id_usuario: int, slot: int, parte: int = 1, **campos) -> dict:
    """Cria ou atualiza uma parte do slot informado e devolve o estado salvo."""
    _garantir_tabela_embeds()
    session = SessionLocal()
    try:
        row = session.query(EmbedPersonalizado).filter_by(
            id_usuario=int(id_usuario),
            slot=int(slot),
            parte=int(parte),
        ).first()

        if not row:
            row = EmbedPersonalizado(
                id_usuario=int(id_usuario),
                slot=int(slot),
                parte=int(parte),
            )
            session.add(row)

        for k, v in campos.items():
            if k in EMBED_CAMPOS:
                setattr(row, k, v)

        session.commit()
        return _embed_para_dict(row)
    finally:
        session.close()


def embed_salvar_slot(id_usuario: int, slot: int, partes: list[dict]) -> list[dict]:
    """Grava o slot inteiro: cada item da lista vira uma parte (1..N) e as partes
    que sobraram de uma versão anterior maior são apagadas."""
    _garantir_tabela_embeds()
    for indice, dados in enumerate(partes, start=1):
        embed_salvar(
            id_usuario, slot, indice,
            **{campo: dados.get(campo) for campo in EMBED_CAMPOS},
        )
    embed_remover(id_usuario, slot, acima_de=len(partes))
    return [d for d in embed_listar(id_usuario) if d["slot"] == int(slot)]


def embed_remover(id_usuario: int, slot: int, parte: int | None = None, acima_de: int | None = None) -> bool:
    """Apaga o slot inteiro, uma parte específica, ou as partes acima de um limite.
    Retorna True se havia algo para apagar."""
    _garantir_tabela_embeds()
    session = SessionLocal()
    try:
        consulta = session.query(EmbedPersonalizado).filter_by(
            id_usuario=int(id_usuario),
            slot=int(slot),
        )
        if parte is not None:
            consulta = consulta.filter(EmbedPersonalizado.parte == int(parte))
        if acima_de is not None:
            consulta = consulta.filter(EmbedPersonalizado.parte > int(acima_de))
        removidas = consulta.delete()
        session.commit()
        return bool(removidas)
    finally:
        session.close()


def embed_criar(id_usuario: int, **campos) -> dict | None:
    """Cria uma embed no próximo slot livre. Retorna None se o limite foi atingido."""
    _garantir_tabela_embeds()
    session = SessionLocal()
    try:
        usados = {
            int(r.slot) for r in session.query(EmbedPersonalizado.slot).filter_by(
                id_usuario=int(id_usuario),
            ).all()
        }
    finally:
        session.close()

    if len(usados) >= EMBED_LIMITE_POR_USUARIO:
        return None

    slot = next(n for n in range(1, EMBED_LIMITE_POR_USUARIO + 1) if n not in usados)
    return embed_salvar(id_usuario, slot, 1, **campos)


# A opção "Sem cor" ocupa um lugar no menu, que aceita 25 no total.
COR_LIMITE_POR_USUARIO = 24

_tabela_cores_pronta = False


def _garantir_tabela_cores():
    global _tabela_cores_pronta
    if _tabela_cores_pronta:
        return
    CorPersonalizada.__table__.create(bind=engine, checkfirst=True)
    _tabela_cores_pronta = True


def cor_listar(id_usuario: int) -> list[dict]:
    """Cores salvas do usuário, na ordem em que foram criadas."""
    _garantir_tabela_cores()
    session = SessionLocal()
    try:
        rows = (
            session.query(CorPersonalizada)
            .filter_by(id_usuario=int(id_usuario))
            .order_by(CorPersonalizada.id)
            .all()
        )
        return [{"nome": r.nome, "cor": int(r.cor)} for r in rows]
    finally:
        session.close()


def cor_salvar(id_usuario: int, nome: str, cor: int) -> dict:
    """Cria a cor ou atualiza o valor de uma já existente com o mesmo nome."""
    _garantir_tabela_cores()
    session = SessionLocal()
    try:
        row = session.query(CorPersonalizada).filter_by(
            id_usuario=int(id_usuario),
            nome=nome,
        ).first()
        if not row:
            row = CorPersonalizada(id_usuario=int(id_usuario), nome=nome)
            session.add(row)
        row.cor = int(cor)
        session.commit()
        return {"nome": row.nome, "cor": int(row.cor)}
    finally:
        session.close()


def cor_remover(id_usuario: int, nome: str) -> bool:
    """Apaga a cor pelo nome. Retorna True se havia algo para apagar."""
    _garantir_tabela_cores()
    session = SessionLocal()
    try:
        removidas = session.query(CorPersonalizada).filter_by(
            id_usuario=int(id_usuario),
            nome=nome,
        ).delete()
        session.commit()
        return bool(removidas)
    finally:
        session.close()


def criar_tabelas():
    """Cria as tabelas definidas pelos models no banco de dados."""
    logger.info("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas com sucesso!")

if __name__ == "__main__":
    criar_tabelas()