"""Camada de banco de dados — SQLAlchemy (PostgreSQL na nuvem ou SQLite local)."""
import json
import os
from datetime import date, datetime

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer,
                        LargeBinary, String, Text, create_engine, func, select)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    if not url:
        url = "sqlite:///audiometria_local.db"  # modo de teste local
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
Session = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Profissional(Base):
    __tablename__ = "profissional"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), default="")
    crfa: Mapped[str] = mapped_column(String(40), default="")
    clinica: Mapped[str] = mapped_column(String(150), default="")
    cnpj_cpf: Mapped[str] = mapped_column(String(30), default="")
    endereco: Mapped[str] = mapped_column(String(250), default="")
    cidade_uf: Mapped[str] = mapped_column(String(100), default="")
    telefone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    audiometro: Mapped[str] = mapped_column(String(120), default="")
    data_calibracao: Mapped[date | None] = mapped_column(Date, nullable=True)
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    assinatura: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


class Empresa(Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    razao_social: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(25), default="")
    endereco: Mapped[str] = mapped_column(String(250), default="")
    cidade_uf: Mapped[str] = mapped_column(String(100), default="")
    telefone: Mapped[str] = mapped_column(String(40), default="")
    contato: Mapped[str] = mapped_column(String(120), default="")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    pacientes = relationship("Paciente", back_populates="empresa")


class Paciente(Base):
    __tablename__ = "pacientes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), index=True)
    cpf: Mapped[str] = mapped_column(String(20), default="")
    rg: Mapped[str] = mapped_column(String(30), default="")
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    sexo: Mapped[str] = mapped_column(String(15), default="")
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True)
    funcao: Mapped[str] = mapped_column(String(120), default="")
    setor: Mapped[str] = mapped_column(String(120), default="")
    data_admissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str] = mapped_column(Text, default="")

    empresa = relationship("Empresa", back_populates="pacientes")
    exames = relationship("Audiometria", back_populates="paciente",
                          cascade="all, delete-orphan")


class Audiometria(Base):
    __tablename__ = "audiometrias"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"), index=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True)
    data_exame: Mapped[date] = mapped_column(Date)
    tipo_exame: Mapped[str] = mapped_column(String(40))
    funcao: Mapped[str] = mapped_column(String(120), default="")
    setor: Mapped[str] = mapped_column(String(120), default="")
    repouso_horas: Mapped[str] = mapped_column(String(20), default="14")
    meatoscopia_od: Mapped[str] = mapped_column(String(80), default="Sem alterações")
    meatoscopia_oe: Mapped[str] = mapped_column(String(80), default="Sem alterações")
    audiometro: Mapped[str] = mapped_column(String(120), default="")
    data_calibracao: Mapped[date | None] = mapped_column(Date, nullable=True)
    anamnese: Mapped[str] = mapped_column(Text, default="")
    limiares_json: Mapped[str] = mapped_column(Text, default="{}")
    logo_json: Mapped[str] = mapped_column(Text, default="{}")
    referencial: Mapped[bool] = mapped_column(Boolean, default=False)
    parecer: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    paciente = relationship("Paciente", back_populates="exames")
    empresa = relationship("Empresa")

    @property
    def limiares(self) -> dict:
        return json.loads(self.limiares_json or "{}")

    @property
    def logoaudiometria(self) -> dict:
        return json.loads(self.logo_json or "{}")


_DIR = os.path.dirname(os.path.abspath(__file__))
# aceita a logo dentro de assets/ ou solta na raiz do repositório
LOGO_PADRAO = next((p for p in (os.path.join(_DIR, "assets", "logo_fonoclin.png"),
                                os.path.join(_DIR, "logo_fonoclin.png")) if os.path.exists(p)),
                   "")

# Dados pré-carregados no primeiro acesso (podem ser alterados em Configurações)
PROFISSIONAL_PADRAO = dict(
    nome="Cristiane R. Miranda Campos",
    crfa="8617-PR",
    clinica="FONOCLIN",
    endereco="Rua José Domingos Branco, 27, Centro",
    cidade_uf="Sengés/PR – CEP 84.220-000",
    telefone="(43) 98850-4641",
    audiometro="VSD 2090",
    data_calibracao=date(2026, 1, 19),
)


def init_db():
    Base.metadata.create_all(engine)
    with Session() as s:
        if not s.get(Profissional, 1):
            logo = None
            if os.path.exists(LOGO_PADRAO):
                with open(LOGO_PADRAO, "rb") as f:
                    logo = f.read()
            s.add(Profissional(id=1, logo=logo, **PROFISSIONAL_PADRAO))
            s.commit()


# ---------------------------------------------------------------- consultas
def get_profissional() -> Profissional:
    with Session() as s:
        return s.get(Profissional, 1)


def salvar(obj):
    with Session() as s:
        obj = s.merge(obj)
        s.commit()
        s.refresh(obj)
        return obj


def excluir(model, obj_id: int):
    with Session() as s:
        obj = s.get(model, obj_id)
        if obj:
            s.delete(obj)
            s.commit()


def listar_empresas(apenas_ativas=False):
    with Session() as s:
        q = select(Empresa).order_by(Empresa.razao_social)
        if apenas_ativas:
            q = q.where(Empresa.ativa.is_(True))
        return list(s.scalars(q))


def get(model, obj_id):
    with Session() as s:
        return s.get(model, obj_id)


def buscar_pacientes(nome: str = "", empresa_id: int | None = None):
    with Session() as s:
        q = select(Paciente).order_by(Paciente.nome)
        if nome:
            q = q.where(func.lower(Paciente.nome).contains(nome.lower().strip()))
        if empresa_id:
            q = q.where(Paciente.empresa_id == empresa_id)
        pacs = list(s.scalars(q))
        for p in pacs:  # carrega a empresa antes de fechar a sessão
            _ = p.empresa
        return pacs


def exames_do_paciente(paciente_id: int):
    with Session() as s:
        q = (select(Audiometria).where(Audiometria.paciente_id == paciente_id)
             .order_by(Audiometria.data_exame.desc(), Audiometria.id.desc()))
        exs = list(s.scalars(q))
        for e in exs:
            _ = e.empresa
        return exs


def exame_completo(exame_id: int):
    """Exame com paciente e empresa carregados (para o relatório)."""
    with Session() as s:
        e = s.get(Audiometria, exame_id)
        if e:
            _ = e.paciente, e.empresa
        return e


def exame_referencia(paciente_id: int, data_exame: date, exame_id: int | None = None):
    """Último exame marcado como referencial anterior ao atual;
    na falta, o primeiro exame do paciente (normalmente o admissional)."""
    with Session() as s:
        base = select(Audiometria).where(Audiometria.paciente_id == paciente_id,
                                         Audiometria.data_exame <= data_exame)
        if exame_id:
            base = base.where(Audiometria.id != exame_id)
        ref = s.scalars(base.where(Audiometria.referencial.is_(True))
                        .order_by(Audiometria.data_exame.desc())).first()
        if not ref:
            ref = s.scalars(base.order_by(Audiometria.data_exame.asc(),
                                          Audiometria.id.asc())).first()
        return ref


def exportar_tudo() -> dict:
    def row(o):
        d = {}
        for c in o.__table__.columns:
            v = getattr(o, c.name)
            if isinstance(v, (date, datetime)):
                v = v.isoformat()
            elif isinstance(v, bytes):
                v = None
            d[c.name] = v
        return d

    with Session() as s:
        return {
            "gerado_em": datetime.now().isoformat(),
            "profissional": [row(o) for o in s.scalars(select(Profissional))],
            "empresas": [row(o) for o in s.scalars(select(Empresa))],
            "pacientes": [row(o) for o in s.scalars(select(Paciente))],
            "audiometrias": [row(o) for o in s.scalars(select(Audiometria))],
        }
