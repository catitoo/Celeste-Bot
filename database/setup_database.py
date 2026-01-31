from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
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

def criar_tabelas():
    """Cria as tabelas definidas pelos models no banco de dados."""
    logger.info("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas com sucesso!")

if __name__ == "__main__":
    criar_tabelas()