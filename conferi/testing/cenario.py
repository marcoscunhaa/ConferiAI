"""Cenário de demonstração com problemas conhecidos (e o gabarito do que deve ser encontrado).

Gera uma pasta parecida com o que um escritório recebe dos clientes: subpastas, um .zip
de fornecedores, arquivos repetidos, um arquivo corrompido e uma relação da Sefaz em CSV.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from .gerador import (
    EmpresaFake,
    ItemFake,
    NotaFake,
    PagamentoFake,
    gerar_cnpj,
    xml_cancelamento,
    xml_inutilizacao,
    xml_nota,
)

PADARIA = EmpresaFake(gerar_cnpj(11), "PADARIA PAO DOURADO LTDA", "CE", crt="1", fantasia="Padaria Pão Dourado")
DISTRIBUIDORA = EmpresaFake(gerar_cnpj(22), "DISTRIBUIDORA LITORAL LTDA", "CE", crt="3")
LOJA = EmpresaFake(gerar_cnpj(33), "LOJA ESTILO FINO LTDA", "CE", crt="1", fantasia="Estilo Fino")
TEXTIL = EmpresaFake(gerar_cnpj(44), "TEXTIL NORDESTE S.A.", "PE", municipio="Recife", crt="3")
ATACADO = EmpresaFake(gerar_cnpj(55), "ATACADO CENTRAL FICTICIO LTDA", "CE", crt="3")
CLIENTE_PE = EmpresaFake(gerar_cnpj(66), "MERCADINHO RECIFE LTDA", "PE", municipio="Recife", crt="1")
CLIENTE_CE = EmpresaFake(gerar_cnpj(77), "MERCANTIL ALDEOTA LTDA", "CE", crt="1")
CREDENCIADORA = gerar_cnpj(88)

OUT = date(2026, 10, 1)
SET = date(2026, 9, 1)


def _d(mes: date, dia: int) -> date:
    return mes.replace(day=dia)


@dataclass
class Gabarito:
    arquivos_xml: int = 0
    notas_unicas: int = 0
    duplicadas: int = 0
    atualizadas: int = 0
    eventos: int = 0
    inutilizacoes: int = 0
    invalidos: int = 0
    ignorados: int = 0
    canceladas: int = 0
    lacunas: dict[str, list[str]] = field(default_factory=dict)       # cnpj -> faixas
    pendencias_esperadas: dict[str, int] = field(default_factory=dict)  # regra -> mínimo
    sefaz: dict[str, int] = field(default_factory=dict)
    chaves: dict[str, str] = field(default_factory=dict)


def gerar_cenario(pasta: str | Path) -> Gabarito:
    pasta = Path(pasta)
    (pasta / "padaria").mkdir(parents=True, exist_ok=True)
    (pasta / "distribuidora").mkdir(exist_ok=True)
    (pasta / "estilo_fino").mkdir(exist_ok=True)
    g = Gabarito()

    def salvar(caminho: Path, dados: bytes) -> None:
        caminho.write_bytes(dados)
        g.arquivos_xml += 1

    # ---------------- Padaria: NFC-e de outubro, com lacuna, inutilização e cancelamento
    chaves_padaria = {}
    for numero in range(1001, 1041):
        if numero in (1015, 1022, 1023):
            continue  # 1015 não enviada; 1022–1023 inutilizadas
        dia = 1 + (numero - 1001) * 30 // 40
        integrado = numero % 3 != 0
        n = NotaFake(
            PADARIA, numero, _d(OUT, dia), modelo="65",
            itens=[ItemFake("PAO FRANCES KG", "19059090", "5102", Decimal("2.5"), Decimal("16.90"), ibscbs=False),
                   ItemFake("CAFE COADO 200ML", "21011110", "5102", Decimal("2"), Decimal("4.50"), ibscbs=False)],
            pagamentos=[PagamentoFake("03", integrado=integrado,
                                      cnpj_credenciadora=CREDENCIADORA if integrado else "",
                                      c_aut=f"A{numero:06d}" if integrado else "")],
        )
        chave, xml = xml_nota(n)
        chaves_padaria[numero] = chave
        salvar(pasta / "padaria" / f"nfce_{numero}.xml", xml)
    salvar(pasta / "padaria" / "inutilizacao_1022_1023.xml",
           xml_inutilizacao(PADARIA.cnpj, "CE", "65", 1, 1022, 1023, 2026))
    salvar(pasta / "padaria" / "cancelamento_1030.xml", xml_cancelamento(chaves_padaria[1030], PADARIA.cnpj, _d(OUT, 21)))
    g.inutilizacoes += 1
    g.eventos += 1
    g.canceladas += 1
    g.lacunas[PADARIA.cnpj] = ["1015"]

    # ---------------- Distribuidora: NF-e de saída (regime normal), com vários problemas
    for numero in range(501, 521):
        if numero == 517:
            continue  # lacuna
        dest = CLIENTE_PE if numero in (503, 507) else CLIENTE_CE
        itens = [ItemFake("ARROZ TIPO 1 5KG", "10063021", "6102" if dest.uf != "CE" else "5102",
                          Decimal("20"), Decimal("27.40")),
                 ItemFake("FEIJAO CARIOCA 1KG", "07133399", "6102" if dest.uf != "CE" else "5102",
                          Decimal("30"), Decimal("8.15"))]
        extra = {}
        if numero == 503:  # venda para PE marcada como operação interna
            extra["id_dest"] = 1
        if numero == 507:  # venda para PE com CFOP interno
            for i in itens:
                i.cfop = "5102"
        if numero == 512:  # total divergente
            extra["total_informado"] = Decimal("788.90")
        if numero == 515:  # sem IBS/CBS
            for i in itens:
                i.ibscbs = False
        if numero == 518:  # NCM inválido
            itens[1].ncm = "0713339"
        n = NotaFake(DISTRIBUIDORA, numero, _d(OUT, 2 + (numero - 501)), itens=itens, destinatario=dest,
                     frete=Decimal("12.40") if numero == 512 else Decimal("0"), **extra)
        chave, xml = xml_nota(n)
        g.chaves[f"dist_{numero}"] = chave
        salvar(pasta / "distribuidora" / f"NFe{chave}.xml", xml)
    g.lacunas[DISTRIBUIDORA.cnpj] = ["517"]

    # ---------------- Distribuidora: setembro (histórico)
    for numero in range(480, 501):
        n = NotaFake(DISTRIBUIDORA, numero, _d(SET, 1 + (numero - 480)), destinatario=CLIENTE_CE,
                     itens=[ItemFake("OLEO DE SOJA 900ML", "15079011", "5102", Decimal("24"), Decimal("7.89"))])
        chave, xml = xml_nota(n)
        salvar(pasta / "distribuidora" / f"NFe{chave}.xml", xml)

    # ---------------- Estilo Fino: vendas e compras (zip de fornecedores com repetidas)
    for numero in range(201, 211):
        n = NotaFake(LOJA, numero, _d(OUT, 5 + numero - 201), destinatario=CLIENTE_CE,
                     itens=[ItemFake("CAMISA SOCIAL M", "62052000", "5102", Decimal("3"), Decimal("89.90"), ibscbs=False)])
        chave, xml = xml_nota(n)
        salvar(pasta / "estilo_fino" / f"venda_{numero}.xml", xml)

    compras = []
    for k, numero in enumerate(range(9001, 9011)):
        preco = Decimal("21.50") + Decimal("0.80") * k  # preço do tecido subindo
        fornecedor = TEXTIL if k % 2 == 0 else ATACADO
        cfop = "6102" if fornecedor.uf != "CE" else "5102"
        n = NotaFake(fornecedor, numero, _d(OUT, 3 + k), destinatario=LOJA,
                     itens=[ItemFake("TECIDO ALGODAO AZUL 1,60M", "52083200", cfop, Decimal("50"), preco)])
        compras.append(n)

    with zipfile.ZipFile(pasta / "fornecedores_outubro.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for n in compras:
            chave, xml = xml_nota(n)
            z.writestr(f"compras/{chave}.xml", xml)
            g.arquivos_xml += 1
        # repetidas: as duas primeiras compras de novo, com outro nome de arquivo
        for n in compras[:2]:
            chave, xml = xml_nota(n)
            z.writestr(f"reenviadas/copia_{n.numero}.xml", xml)
            g.arquivos_xml += 1
            g.duplicadas += 1

    # Uma compra chega primeiro sem protocolo e depois autorizada (deve atualizar, não duplicar)
    sem_prot = NotaFake(ATACADO, 9100, _d(OUT, 28), destinatario=LOJA, com_protocolo=False,
                        itens=[ItemFake("LINHA DE COSTURA", "54011011", "5102", Decimal("100"), Decimal("1.20"))])
    _, xml = xml_nota(sem_prot)
    salvar(pasta / "estilo_fino" / "a_compra_9100_sem_protocolo.xml", xml)
    sem_prot.com_protocolo = True
    _, xml = xml_nota(sem_prot)
    salvar(pasta / "estilo_fino" / "b_compra_9100_autorizada.xml", xml)
    g.atualizadas += 1

    # ---------------- arquivos problemáticos
    salvar(pasta / "estilo_fino" / "nota_corrompida.xml", b'<?xml version="1.0"?><nfeProc><NFe><infNFe Id="NFe')
    g.invalidos += 1
    salvar(pasta / "estilo_fino" / "resumo_nfe.xml",
           b'<?xml version="1.0"?><resNFe xmlns="http://www.portalfiscal.inf.br/nfe"><chNFe>1</chNFe></resNFe>')
    g.ignorados += 1
    (pasta / "leia-me.txt").write_text("Arquivos enviados pelos clientes em outubro.", encoding="utf-8")

    # ---------------- relação da Sefaz (Padaria, outubro)
    linhas = ["Chave de acesso;Número;Situação"]
    for numero in range(1001, 1041):
        if numero in (1022, 1023, 1038):
            continue  # inutilizadas não aparecem; 1038 propositalmente fora da relação
        chave = chaves_padaria.get(numero)
        if chave is None:  # 1015: emitida, mas não enviada ao escritório
            n = NotaFake(PADARIA, numero, _d(OUT, 11), modelo="65",
                         itens=[ItemFake("PAO DE QUEIJO", "19059090", "5102", Decimal("1"), Decimal("9.90"))])
            chave = n.chave()
        situacao = "Cancelada" if numero in (1030, 1035) else "Autorizada"
        linhas.append(f"{chave};{numero};{situacao}")
    (pasta / "sefaz_padaria_outubro.csv").write_text("\n".join(linhas), encoding="utf-8")
    g.sefaz = {"faltando_no_escritorio": 1, "fora_da_sefaz": 1, "cancelada_na_sefaz": 1,
               "cancelada_no_escritorio": 0}

    g.notas_unicas = 37 + 19 + 21 + 10 + 10 + 1
    g.pendencias_esperadas = {"sequencia": 2, "total_nota": 1, "cfop_destino": 2, "uf_destino": 1,
                              "ibscbs": 1, "ncm": 1, "cancelada": 1}
    g.chaves["padaria_1030"] = chaves_padaria[1030]
    g.chaves["padaria_1035"] = chaves_padaria[1035]
    return g


EMPRESAS = {"padaria": PADARIA, "distribuidora": DISTRIBUIDORA, "loja": LOJA, "textil": TEXTIL,
            "atacado": ATACADO}
