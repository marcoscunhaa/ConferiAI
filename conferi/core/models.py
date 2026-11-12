"""Estruturas de dados extraídas dos documentos fiscais."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Item:
    n_item: int
    codigo: str = ""
    descricao: str = ""
    ncm: str = ""
    cfop: str = ""
    unidade: str = ""
    quantidade: str = "0"
    valor_unitario: str = "0"
    v_prod: int = 0
    v_desc: int = 0
    v_frete: int = 0
    v_seg: int = 0
    v_outro: int = 0
    ind_tot: int = 1
    ibscbs_presente: bool = False
    cst_ibscbs: str = ""
    cclasstrib: str = ""


@dataclass
class Pagamento:
    t_pag: str = ""
    valor: int = 0
    tp_integra: str = ""
    cnpj_credenciadora: str = ""
    c_aut: str = ""


@dataclass
class Nota:
    chave: str
    versao: str = ""
    modelo: str = "55"
    serie: int = 0
    numero: int = 0
    dh_emissao: str = ""
    data_emissao: str = ""  # AAAA-MM-DD
    tp_nf: int = 1  # 0 = entrada, 1 = saída (do ponto de vista do emitente)
    id_dest: int = 1  # 1 interna, 2 interestadual, 3 exterior
    fin_nfe: int = 1  # 1 normal, 2 complementar, 3 ajuste, 4 devolução
    tp_amb: int = 1  # 1 produção, 2 homologação
    nat_op: str = ""
    emit_doc: str = ""
    emit_nome: str = ""
    emit_fantasia: str = ""
    emit_uf: str = ""
    emit_municipio: str = ""
    emit_crt: str = ""
    dest_doc: str = ""
    dest_nome: str = ""
    dest_uf: str = ""
    dest_municipio: str = ""
    totais: dict[str, int] = field(default_factory=dict)
    tem_ibscbs_total: bool = False
    c_stat: str = ""
    n_prot: str = ""
    dh_recebimento: str = ""
    itens: list[Item] = field(default_factory=list)
    pagamentos: list[Pagamento] = field(default_factory=list)

    @property
    def tem_protocolo(self) -> bool:
        return bool(self.n_prot)

    @property
    def valor_total(self) -> int:
        return self.totais.get("vNF", 0)


@dataclass
class Evento:
    chave: str
    tipo: str  # 110111 cancelamento, 110112 cancelamento por substituição, 110110 CC-e
    sequencia: int = 1
    dh_evento: str = ""
    descricao: str = ""
    justificativa: str = ""
    c_stat: str = ""
    protocolo: str = ""

    @property
    def e_cancelamento(self) -> bool:
        return self.tipo in ("110111", "110112")

    @property
    def registrado(self) -> bool:
        # 135/136/155 = evento registrado. Sem retorno, aceitamos o arquivo como informado.
        return self.c_stat in ("", "135", "136", "155")


@dataclass
class Inutilizacao:
    cnpj: str
    modelo: str
    serie: int
    n_ini: int
    n_fin: int
    ano: str = ""
    protocolo: str = ""
    c_stat: str = ""
    justificativa: str = ""

    @property
    def homologada(self) -> bool:
        return self.c_stat in ("", "102")


@dataclass
class Invalido:
    motivo: str


@dataclass
class NaoSuportado:
    tipo: str
    motivo: str


Documento = Nota | Evento | Inutilizacao | Invalido | NaoSuportado
