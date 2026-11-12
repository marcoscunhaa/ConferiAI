"""Gerador de XMLs fictícios de NF-e, NFC-e, eventos e inutilização.

Os documentos seguem a estrutura do layout 4.00, mas não têm assinatura digital válida
nem existem na Sefaz. Servem apenas para testar o Conferi AI e para demonstrações.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape

from conferi.core.chave import calcular_dv

NS = "http://www.portalfiscal.inf.br/nfe"
CODIGO_UF = {"CE": "23", "PE": "26", "RN": "24", "PI": "22", "BA": "29", "SP": "35", "RJ": "33", "PB": "25",
             "MA": "21"}


def _cnpj_dv(base12: str) -> str:
    def dv(b: str, pesos: list[int]) -> str:
        r = sum(int(x) * y for x, y in zip(b, pesos)) % 11
        return "0" if r < 2 else str(11 - r)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(base12, p1)
    d2 = dv(base12 + d1, [6] + p1)
    return base12 + d1 + d2


def gerar_cnpj(semente: int) -> str:
    rnd = random.Random(semente)
    base = "".join(str(rnd.randint(0, 9)) for _ in range(8)) + "0001"
    return _cnpj_dv(base)


@dataclass
class EmpresaFake:
    cnpj: str
    nome: str
    uf: str = "CE"
    municipio: str = "Fortaleza"
    crt: str = "1"
    fantasia: str = ""


@dataclass
class ItemFake:
    descricao: str
    ncm: str = "61091000"
    cfop: str = "5102"
    quantidade: Decimal = Decimal("1")
    valor_unitario: Decimal = Decimal("10.00")
    ibscbs: bool = True
    cst_ibscbs: str = "000"
    cclasstrib: str = "000001"
    codigo: str = ""

    @property
    def valor_total(self) -> Decimal:
        return (self.quantidade * self.valor_unitario).quantize(Decimal("0.01"), ROUND_HALF_UP)


@dataclass
class PagamentoFake:
    t_pag: str = "01"
    valor: Decimal | None = None
    integrado: bool = False
    cnpj_credenciadora: str = ""
    c_aut: str = ""


@dataclass
class NotaFake:
    emitente: EmpresaFake
    numero: int
    data: date
    itens: list[ItemFake]
    destinatario: EmpresaFake | None = None
    dest_cpf: str = ""
    modelo: str = "55"
    serie: int = 1
    tp_nf: int = 1
    id_dest: int | None = None
    fin_nfe: int = 1
    tp_amb: int = 1
    frete: Decimal = Decimal("0")
    desconto: Decimal = Decimal("0")
    com_protocolo: bool = True
    c_stat: str = "100"
    total_informado: Decimal | None = None  # força total divergente
    v_prod_informado: Decimal | None = None
    com_namespace: bool = True
    pagamentos: list[PagamentoFake] = field(default_factory=list)
    nat_op: str = "Venda de mercadoria"

    def chave(self) -> str:
        aamm = self.data.strftime("%y%m")
        cnf = f"{(self.numero * 7919 + self.serie * 31) % 100_000_000:08d}"
        base = (f"{CODIGO_UF[self.emitente.uf]}{aamm}{self.emitente.cnpj}{self.modelo}"
                f"{self.serie:03d}{self.numero:09d}1{cnf}")
        return base + str(calcular_dv(base))


def _v(d: Decimal) -> str:
    return f"{d.quantize(Decimal('0.01'), ROUND_HALF_UP)}"


def xml_nota(n: NotaFake) -> tuple[str, bytes]:
    chave = n.chave()
    dh = datetime.combine(n.data, time(10, 30)).strftime("%Y-%m-%dT%H:%M:%S-03:00")
    if n.id_dest is None:
        if n.destinatario and n.destinatario.uf != n.emitente.uf:
            id_dest = 2
        else:
            id_dest = 1
    else:
        id_dest = n.id_dest

    v_prod = sum((i.valor_total for i in n.itens), Decimal("0"))
    v_nf = v_prod - n.desconto + n.frete
    itens_xml = []
    for k, i in enumerate(n.itens, start=1):
        ibs = ""
        if i.ibscbs:
            ibs = (f"<IBSCBS><CST>{i.cst_ibscbs}</CST><cClassTrib>{i.cclasstrib}</cClassTrib>"
                   f"<gIBSCBS><vBC>{_v(i.valor_total)}</vBC></gIBSCBS></IBSCBS>")
        itens_xml.append(
            f'<det nItem="{k}"><prod><cProd>{escape(i.codigo or f"P{k:03d}")}</cProd><cEAN>SEM GTIN</cEAN>'
            f"<xProd>{escape(i.descricao)}</xProd><NCM>{i.ncm}</NCM><CFOP>{i.cfop}</CFOP><uCom>UN</uCom>"
            f"<qCom>{i.quantidade:.4f}</qCom><vUnCom>{i.valor_unitario:.10f}</vUnCom>"
            f"<vProd>{_v(i.valor_total)}</vProd><indTot>1</indTot></prod>"
            f"<imposto><ICMS><ICMSSN102><orig>0</orig><CSOSN>102</CSOSN></ICMSSN102></ICMS>{ibs}</imposto></det>"
        )

    e = n.emitente
    emit = (f"<emit><CNPJ>{e.cnpj}</CNPJ><xNome>{escape(e.nome)}</xNome>"
            + (f"<xFant>{escape(e.fantasia)}</xFant>" if e.fantasia else "")
            + f"<enderEmit><xLgr>Rua Exemplo</xLgr><nro>100</nro><xBairro>Centro</xBairro><cMun>2304400</cMun>"
            f"<xMun>{escape(e.municipio)}</xMun><UF>{e.uf}</UF></enderEmit><IE>000000000</IE><CRT>{e.crt}</CRT></emit>")
    dest = ""
    if n.destinatario:
        d = n.destinatario
        dest = (f"<dest><CNPJ>{d.cnpj}</CNPJ><xNome>{escape(d.nome)}</xNome><enderDest><xLgr>Av. Teste</xLgr>"
                f"<nro>1</nro><xBairro>Centro</xBairro><cMun>0000000</cMun><xMun>{escape(d.municipio)}</xMun>"
                f"<UF>{d.uf}</UF></enderDest><indIEDest>9</indIEDest></dest>")
    elif n.dest_cpf:
        dest = f"<dest><CPF>{n.dest_cpf}</CPF><indIEDest>9</indIEDest></dest>"

    pag = ""
    if n.pagamentos or n.modelo == "65":
        pags = n.pagamentos or [PagamentoFake()]
        partes = []
        for p in pags:
            card = ""
            if p.t_pag in ("03", "04", "17"):
                card = (f"<card><tpIntegra>{1 if p.integrado else 2}</tpIntegra>"
                        + (f"<CNPJ>{p.cnpj_credenciadora}</CNPJ>" if p.cnpj_credenciadora else "")
                        + (f"<cAut>{p.c_aut}</cAut>" if p.c_aut else "") + "</card>")
            partes.append(f"<detPag><tPag>{p.t_pag}</tPag><vPag>{_v(p.valor if p.valor is not None else v_nf)}</vPag>"
                          f"{card}</detPag>")
        pag = "<pag>" + "".join(partes) + "</pag>"

    total = (f"<total><ICMSTot><vBC>0.00</vBC><vICMS>0.00</vICMS><vICMSDeson>0.00</vICMSDeson><vFCP>0.00</vFCP>"
             f"<vBCST>0.00</vBCST><vST>0.00</vST><vFCPST>0.00</vFCPST><vFCPSTRet>0.00</vFCPSTRet>"
             f"<vProd>{_v(n.v_prod_informado if n.v_prod_informado is not None else v_prod)}</vProd>"
             f"<vFrete>{_v(n.frete)}</vFrete><vSeg>0.00</vSeg><vDesc>{_v(n.desconto)}</vDesc><vII>0.00</vII>"
             f"<vIPI>0.00</vIPI><vIPIDevol>0.00</vIPIDevol><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS>"
             f"<vOutro>0.00</vOutro><vNF>{_v(n.total_informado if n.total_informado is not None else v_nf)}</vNF>"
             f"</ICMSTot></total>")

    ns = f' xmlns="{NS}"' if n.com_namespace else ""
    nfe = (f"<NFe{ns}><infNFe Id=\"NFe{chave}\" versao=\"4.00\"><ide><cUF>{CODIGO_UF[e.uf]}</cUF>"
           f"<cNF>{chave[35:43]}</cNF><natOp>{escape(n.nat_op)}</natOp><mod>{n.modelo}</mod><serie>{n.serie}</serie>"
           f"<nNF>{n.numero}</nNF><dhEmi>{dh}</dhEmi><tpNF>{n.tp_nf}</tpNF><idDest>{id_dest}</idDest>"
           f"<cMunFG>2304400</cMunFG><tpImp>1</tpImp><tpEmis>1</tpEmis><cDV>{chave[-1]}</cDV>"
           f"<tpAmb>{n.tp_amb}</tpAmb><finNFe>{n.fin_nfe}</finNFe><indFinal>1</indFinal><indPres>1</indPres>"
           f"<procEmi>0</procEmi><verProc>Gerador Conferi 1.0</verProc></ide>"
           f"{emit}{dest}{''.join(itens_xml)}{total}<transp><modFrete>9</modFrete></transp>{pag}</infNFe></NFe>")
    if not n.com_protocolo:
        xml = f'<?xml version="1.0" encoding="UTF-8"?>{nfe}'
    else:
        prot = (f'<protNFe versao="4.00"><infProt><tpAmb>{n.tp_amb}</tpAmb><verAplic>SVRS</verAplic>'
                f"<chNFe>{chave}</chNFe><dhRecbto>{dh}</dhRecbto><nProt>3{chave[-14:]}</nProt>"
                f"<digVal>AAAA</digVal><cStat>{n.c_stat}</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
                f"</infProt></protNFe>")
        xml = f'<?xml version="1.0" encoding="UTF-8"?><nfeProc xmlns="{NS}" versao="4.00">{nfe}{prot}</nfeProc>'
    return chave, xml.encode("utf-8")


def xml_cancelamento(chave: str, cnpj: str, quando: date, c_stat: str = "135") -> bytes:
    dh = datetime.combine(quando, time(15, 0)).strftime("%Y-%m-%dT%H:%M:%S-03:00")
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><procEventoNFe xmlns="{NS}" versao="1.00">'
        f'<evento versao="1.00"><infEvento Id="ID110111{chave}01"><cOrgao>{chave[:2]}</cOrgao><tpAmb>1</tpAmb>'
        f"<CNPJ>{cnpj}</CNPJ><chNFe>{chave}</chNFe><dhEvento>{dh}</dhEvento><tpEvento>110111</tpEvento>"
        f'<nSeqEvento>1</nSeqEvento><verEvento>1.00</verEvento><detEvento versao="1.00">'
        f"<descEvento>Cancelamento</descEvento><nProt>3{chave[-14:]}</nProt>"
        f"<xJust>Erro no endereco do destinatario</xJust></detEvento></infEvento></evento>"
        f'<retEvento versao="1.00"><infEvento><tpAmb>1</tpAmb><cStat>{c_stat}</cStat>'
        f"<xMotivo>Evento registrado</xMotivo><chNFe>{chave}</chNFe><tpEvento>110111</tpEvento>"
        f"<nProt>9{chave[-14:]}</nProt></infEvento></retEvento></procEventoNFe>"
    ).encode("utf-8")


def xml_inutilizacao(cnpj: str, uf: str, modelo: str, serie: int, n_ini: int, n_fin: int, ano: int) -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><procInutNFe xmlns="{NS}" versao="4.00">'
        f'<inutNFe versao="4.00"><infInut Id="ID{CODIGO_UF[uf]}{ano % 100:02d}{cnpj}{modelo}{serie:03d}'
        f'{n_ini:09d}{n_fin:09d}"><tpAmb>1</tpAmb><xServ>INUTILIZAR</xServ><cUF>{CODIGO_UF[uf]}</cUF>'
        f"<ano>{ano % 100:02d}</ano><CNPJ>{cnpj}</CNPJ><mod>{modelo}</mod><serie>{serie}</serie>"
        f"<nNFIni>{n_ini}</nNFIni><nNFFin>{n_fin}</nNFFin><xJust>Falha no sistema emissor</xJust></infInut>"
        f'</inutNFe><retInutNFe versao="4.00"><infInut><tpAmb>1</tpAmb><cStat>102</cStat>'
        f"<xMotivo>Inutilizacao de numero homologado</xMotivo><nProt>4{cnpj[:14]}</nProt></infInut>"
        f"</retInutNFe></procInutNFe>"
    ).encode("utf-8")
