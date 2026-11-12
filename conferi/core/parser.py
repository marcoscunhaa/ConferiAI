"""Leitura dos XMLs fiscais.

Aceita:
- NF-e e NFC-e (modelos 55 e 65), com ou sem a "casca" de autorização (nfeProc);
- lotes de envio (enviNFe) com várias notas;
- eventos (procEventoNFe / evento), como cancelamento e carta de correção;
- inutilização de numeração (procInutNFe / inutNFe).

Usa defusedxml para não processar entidades maliciosas em arquivos de terceiros.
Os namespaces são removidos, para tolerar emissores que omitem ou alteram o namespace.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, ParseError

from defusedxml import DefusedXmlException
from defusedxml import ElementTree as SafeET

from .chave import chave_valida, somente_digitos
from .models import Documento, Evento, Inutilizacao, Invalido, Item, NaoSuportado, Nota, Pagamento
from .money import to_cents

TAMANHO_MAXIMO = 30 * 1024 * 1024  # 30 MB por arquivo

CAMPOS_TOTAL = (
    "vBC", "vICMS", "vICMSDeson", "vFCP", "vBCST", "vST", "vFCPST", "vFCPSTRet", "vProd", "vFrete",
    "vSeg", "vDesc", "vII", "vIPI", "vIPIDevol", "vPIS", "vCOFINS", "vOutro", "vNF",
)


# ----------------------------------------------------------------- utilidades XML

def _remover_namespaces(raiz: Element) -> Element:
    for el in raiz.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return raiz


def carregar_xml(dados: bytes) -> Element:
    """Converte bytes em árvore XML, tolerando BOM e arquivos em Latin-1 rotulados como UTF-8."""
    dados = dados.lstrip(b"\xef\xbb\xbf").strip()
    if not dados:
        raise ParseError("arquivo vazio")
    try:
        raiz = SafeET.fromstring(dados)
    except ParseError:
        # Tentativa de recuperação: conteúdo em Latin-1 com declaração UTF-8.
        try:
            texto = dados.decode("utf-8")
        except UnicodeDecodeError:
            texto = dados.decode("latin-1")
            if texto.startswith("<?xml"):
                fim = texto.find("?>")
                texto = texto[fim + 2:] if fim != -1 else texto
            raiz = SafeET.fromstring(texto.encode("utf-8"))
        else:
            raise
    return _remover_namespaces(raiz)


def _t(el: Element | None, caminho: str, padrao: str = "") -> str:
    if el is None:
        return padrao
    achado = el.find(caminho)
    if achado is None or achado.text is None:
        return padrao
    return achado.text.strip()


def _int(texto: str, padrao: int = 0) -> int:
    try:
        return int(texto)
    except (TypeError, ValueError):
        return padrao


# ----------------------------------------------------------------- notas

def _ler_item(det: Element) -> Item:
    prod = det.find("prod")
    imposto = det.find("imposto")
    ibscbs = imposto.find(".//IBSCBS") if imposto is not None else None
    return Item(
        n_item=_int(det.get("nItem", "0")),
        codigo=_t(prod, "cProd"),
        descricao=_t(prod, "xProd"),
        ncm=_t(prod, "NCM"),
        cfop=_t(prod, "CFOP"),
        unidade=_t(prod, "uCom"),
        quantidade=_t(prod, "qCom", "0"),
        valor_unitario=_t(prod, "vUnCom", "0"),
        v_prod=to_cents(_t(prod, "vProd")),
        v_desc=to_cents(_t(prod, "vDesc")),
        v_frete=to_cents(_t(prod, "vFrete")),
        v_seg=to_cents(_t(prod, "vSeg")),
        v_outro=to_cents(_t(prod, "vOutro")),
        ind_tot=_int(_t(prod, "indTot", "1"), 1),
        ibscbs_presente=ibscbs is not None,
        cst_ibscbs=_t(ibscbs, "CST") if ibscbs is not None else "",
        cclasstrib=_t(ibscbs, "cClassTrib") if ibscbs is not None else "",
    )


def _ler_pagamentos(inf: Element) -> list[Pagamento]:
    pagamentos = []
    for det in inf.findall("pag/detPag"):
        card = det.find("card")
        pagamentos.append(Pagamento(
            t_pag=_t(det, "tPag"),
            valor=to_cents(_t(det, "vPag")),
            tp_integra=_t(card, "tpIntegra") if card is not None else "",
            cnpj_credenciadora=_t(card, "CNPJ") if card is not None else "",
            c_aut=_t(card, "cAut") if card is not None else "",
        ))
    return pagamentos


def _ler_nota(nfe: Element, prot: Element | None) -> Documento:
    inf = nfe.find("infNFe")
    if inf is None:
        return Invalido("NF-e sem o grupo infNFe")

    chave = somente_digitos(inf.get("Id", ""))
    if len(chave) != 44 and prot is not None:
        chave = somente_digitos(_t(prot, "chNFe"))
    if len(chave) != 44:
        return Invalido("chave de acesso ausente ou com tamanho incorreto")
    if not chave_valida(chave):
        return Invalido(f"chave de acesso com dígito verificador inválido ({chave})")

    ide = inf.find("ide")
    emit = inf.find("emit")
    dest = inf.find("dest")
    dh = _t(ide, "dhEmi") or _t(ide, "dEmi")

    tot = inf.find("total/ICMSTot")
    totais = {campo: to_cents(_t(tot, campo)) for campo in CAMPOS_TOTAL}
    totais["vServ"] = to_cents(_t(inf, "total/ISSQNtot/vServ"))

    nota = Nota(
        chave=chave,
        versao=inf.get("versao", ""),
        modelo=_t(ide, "mod", chave[20:22]),
        serie=_int(_t(ide, "serie")),
        numero=_int(_t(ide, "nNF")),
        dh_emissao=dh,
        data_emissao=dh[:10],
        tp_nf=_int(_t(ide, "tpNF", "1"), 1),
        id_dest=_int(_t(ide, "idDest", "1"), 1),
        fin_nfe=_int(_t(ide, "finNFe", "1"), 1),
        tp_amb=_int(_t(ide, "tpAmb", "1"), 1),
        nat_op=_t(ide, "natOp"),
        emit_doc=_t(emit, "CNPJ") or _t(emit, "CPF"),
        emit_nome=_t(emit, "xNome"),
        emit_fantasia=_t(emit, "xFant"),
        emit_uf=_t(emit, "enderEmit/UF"),
        emit_municipio=_t(emit, "enderEmit/xMun"),
        emit_crt=_t(emit, "CRT"),
        dest_doc=(_t(dest, "CNPJ") or _t(dest, "CPF") or _t(dest, "idEstrangeiro")) if dest is not None else "",
        dest_nome=_t(dest, "xNome") if dest is not None else "",
        dest_uf=_t(dest, "enderDest/UF") if dest is not None else "",
        dest_municipio=_t(dest, "enderDest/xMun") if dest is not None else "",
        totais=totais,
        tem_ibscbs_total=inf.find("total/IBSCBSTot") is not None,
        itens=[_ler_item(det) for det in inf.findall("det")],
        pagamentos=_ler_pagamentos(inf),
    )
    if prot is not None:
        nota.c_stat = _t(prot, "cStat")
        nota.n_prot = _t(prot, "nProt")
        nota.dh_recebimento = _t(prot, "dhRecbto")
    if not nota.data_emissao:
        return Invalido("nota sem data de emissão")
    return nota


# ----------------------------------------------------------------- eventos e inutilização

def _ler_evento(evento: Element, ret: Element | None) -> Documento:
    inf = evento.find("infEvento")
    if inf is None:
        return Invalido("evento sem o grupo infEvento")
    chave = somente_digitos(_t(inf, "chNFe"))
    if len(chave) != 44:
        return Invalido("evento sem chave de acesso válida")
    det = inf.find("detEvento")
    return Evento(
        chave=chave,
        tipo=_t(inf, "tpEvento"),
        sequencia=_int(_t(inf, "nSeqEvento", "1"), 1),
        dh_evento=_t(inf, "dhEvento"),
        descricao=_t(det, "descEvento"),
        justificativa=_t(det, "xJust") or _t(det, "xCorrecao"),
        c_stat=_t(ret, "cStat") if ret is not None else "",
        protocolo=(_t(ret, "nProt") if ret is not None else "") or _t(det, "nProt"),
    )


def _ler_inutilizacao(inut: Element, ret: Element | None) -> Documento:
    inf = inut.find("infInut")
    if inf is None:
        return Invalido("inutilização sem o grupo infInut")
    return Inutilizacao(
        cnpj=_t(inf, "CNPJ") or _t(inf, "CPF"),
        modelo=_t(inf, "mod"),
        serie=_int(_t(inf, "serie")),
        n_ini=_int(_t(inf, "nNFIni")),
        n_fin=_int(_t(inf, "nNFFin")),
        ano=_t(inf, "ano"),
        justificativa=_t(inf, "xJust"),
        c_stat=_t(ret, "cStat") if ret is not None else "",
        protocolo=_t(ret, "nProt") if ret is not None else "",
    )


# ----------------------------------------------------------------- ponto de entrada

def ler_documentos(dados: bytes) -> list[Documento]:
    """Lê um arquivo e devolve um ou mais documentos (um lote pode ter várias notas)."""
    if len(dados) > TAMANHO_MAXIMO:
        return [Invalido("arquivo maior que o limite de 30 MB")]
    try:
        raiz = carregar_xml(dados)
    except (ParseError, DefusedXmlException, UnicodeDecodeError, ValueError) as erro:
        return [Invalido(f"não é um XML válido ({erro.__class__.__name__})")]

    tag = raiz.tag
    if tag == "nfeProc":
        nfe = raiz.find("NFe")
        if nfe is None:
            return [Invalido("nfeProc sem a NF-e")]
        return [_ler_nota(nfe, raiz.find("protNFe/infProt"))]
    if tag == "NFe":
        return [_ler_nota(raiz, None)]
    if tag == "enviNFe":
        notas = raiz.findall("NFe")
        return [_ler_nota(n, None) for n in notas] or [Invalido("lote sem notas")]
    if tag == "procEventoNFe":
        evento = raiz.find("evento")
        if evento is None:
            return [Invalido("procEventoNFe sem o evento")]
        return [_ler_evento(evento, raiz.find("retEvento/infEvento"))]
    if tag == "evento":
        return [_ler_evento(raiz, None)]
    if tag == "envEvento":
        return [_ler_evento(e, None) for e in raiz.findall("evento")] or [Invalido("lote de eventos vazio")]
    if tag == "procInutNFe":
        inut = raiz.find("inutNFe")
        if inut is None:
            return [Invalido("procInutNFe sem a inutilização")]
        return [_ler_inutilizacao(inut, raiz.find("retInutNFe/infInut"))]
    if tag == "inutNFe":
        return [_ler_inutilizacao(raiz, None)]
    if tag in ("resNFe", "resEvento"):
        return [NaoSuportado(tag, "resumo de documento (sem os dados completos da nota)")]
    if tag in ("cteProc", "CTe"):
        return [NaoSuportado(tag, "CT-e ainda não é lido pelo Conferi AI")]
    if tag in ("NFSe", "CompNfse", "DPS"):
        return [NaoSuportado(tag, "NFS-e prevista para uma próxima etapa")]
    return [NaoSuportado(tag, f"tipo de documento não reconhecido ({tag})")]
