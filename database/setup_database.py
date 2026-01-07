from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime, timedelta
import logging

# Configuração do banco de dados MySQL
DATABASE_URL = ""
# engine = create_engine(DATABASE_URL, echo=False)
engine = None  # Temporariamente desabilitado
Base = declarative_base()

# Sessão para interagir com o banco de dados
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = None  # Temporariamente desabilitado

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tabelas
class Membro(Base):  
    __tablename__ = "membros"  
    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String(100), ForeignKey("formularios.discord_id"))
    nome = Column(String(150), index=True, nullable=False)
    apelido = Column(String(100), nullable=False)
    cargo = Column(String(50), nullable=True)
    data_entrada = Column(String(30), default=lambda: (datetime.utcnow() - timedelta(hours=3)).strftime("%d-%m-%Y %H:%M:%S"))
    status_formulario = Column(String(30), default="pendente")
    formularios = relationship("Formulario", back_populates="membro")

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

# Cria as tabelas no banco de dados
def criar_tabelas():
    logger.info("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas com sucesso!")

def registrar_punicao(user_id, regra, nome=None):
    session = SessionLocal()
    try:
        punicao = session.query(Punicao).filter_by(user_id=str(user_id), regra=regra).first()
        if punicao:
            punicao.instancia += 1
            punicao.ultima_punicao = datetime.utcnow()
            if nome:
                punicao.nome = nome
        else:
            punicao = Punicao(user_id=str(user_id), regra=regra, instancia=1, nome=nome)
            session.add(punicao)
        session.commit()
        return punicao.instancia
    finally:
        session.close()

if __name__ == "__main__":
    criar_tabelas()