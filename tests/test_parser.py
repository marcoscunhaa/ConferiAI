from datetime import date
from decimal import Decimal

from conferi.core.chave import calcular_dv, chave_valida, cnpj_valido, decompor
from conferi.core.models import Evento, Inutilizacao, Invalido, NaoSuportado, Nota
from conferi.core.parser import ler_documentos
from conferi.testing.cenario import DISTRIBUIDORA, PADARIA
from conferi.testing.gerador import ItemFake, NotaFake, xml_cancelamento, xml_inutilizacao, xml_nota


def _nota(**kw):
    base = dict(emitente=DISTRIBUIDORA, numero=10, data=date(2026, 10, 5),
                itens=[ItemFake("ARROZ", "10063021", "5102", Decimal("2"), Decimal("10.50"))])
    base.update(kw)
    return NotaFake(**base)


def test_chave_dv_e_decomposicao():
    chave, _ = xml_nota(_nota())
    assert chave_valida(chave)
    assert calcular_dv(chave[:43]) == int(chave[-1])
    partes = decompor(chave)
    assert partes.cnpj == DISTRIBUIDORA.cnpj
    assert partes.ano_mes == "2026-10"
    assert partes.numero == 10 and partes.serie == 1 and partes.modelo == "55"
    assert cnpj_valido(DISTRIBUIDORA.cnpj)


def test_le_nfeproc_completa():
    chave, xml = xml_nota(_nota(frete=Decimal("5")))
    [doc] = ler_documentos(xml)
    assert isinstance(doc, Nota)
    assert doc.chave == chave
    assert doc.emit_doc == DISTRIBUIDORA.cnpj and doc.emit_crt == "3"
    assert doc.totais["vProd"] == 2100 and doc.totais["vFrete"] == 500 and doc.totais["vNF"] == 2600
    assert doc.n_prot and doc.c_stat == "100"
    assert doc.itens[0].ncm == "10063021" and doc.itens[0].ibscbs_presente
    assert doc.itens[0].cst_ibscbs == "000" and doc.itens[0].cclasstrib == "000001"


def test_le_nfe_sem_protocolo_e_sem_namespace():
    _, xml = xml_nota(_nota(com_protocolo=False, com_namespace=False))
    [doc] = ler_documentos(xml)
    assert isinstance(doc, Nota)
    assert not doc.tem_protocolo


def test_nfce_com_pagamento_integrado():
    from conferi.testing.gerador import PagamentoFake
    _, xml = xml_nota(NotaFake(PADARIA, 5, date(2026, 10, 2), modelo="65",
                               itens=[ItemFake("PAO", "19059090", "5102", Decimal("1"), Decimal("9.9"))],
                               pagamentos=[PagamentoFake("03", integrado=True, cnpj_credenciadora="1" * 14,
                                                         c_aut="ABC")]))
    [doc] = ler_documentos(xml)
    assert doc.modelo == "65"
    assert doc.pagamentos[0].tp_integra == "1" and doc.pagamentos[0].c_aut == "ABC"


def test_evento_e_inutilizacao():
    chave, _ = xml_nota(_nota())
    [ev] = ler_documentos(xml_cancelamento(chave, DISTRIBUIDORA.cnpj, date(2026, 10, 6)))
    assert isinstance(ev, Evento) and ev.e_cancelamento and ev.registrado and ev.chave == chave
    [inut] = ler_documentos(xml_inutilizacao(PADARIA.cnpj, "CE", "65", 1, 20, 22, 2026))
    assert isinstance(inut, Inutilizacao) and (inut.n_ini, inut.n_fin) == (20, 22) and inut.homologada


def test_arquivos_invalidos_e_nao_suportados():
    assert isinstance(ler_documentos(b"")[0], Invalido)
    assert isinstance(ler_documentos(b"<nfeProc><NFe><infNFe")[0], Invalido)
    assert isinstance(ler_documentos(b"isto nao e xml")[0], Invalido)
    assert isinstance(ler_documentos(b"<resNFe><chNFe>1</chNFe></resNFe>")[0], NaoSuportado)
    # entidades maliciosas são bloqueadas
    bomba = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
             b"<NFe>&b;</NFe>")
    assert isinstance(ler_documentos(bomba)[0], Invalido)


def test_chave_com_dv_errado_e_rejeitada():
    chave, xml = xml_nota(_nota())
    errada = chave[:-1] + str((int(chave[-1]) + 1) % 10)
    [doc] = ler_documentos(xml.replace(chave.encode(), errada.encode()))
    assert isinstance(doc, Invalido)


def test_latin1_rotulado_como_utf8():
    _, xml = xml_nota(_nota(itens=[ItemFake("AÇÚCAR CRISTAL", "17019900", "5102", Decimal("1"), Decimal("5"))]))
    latin = xml.decode("utf-8").encode("latin-1")
    [doc] = ler_documentos(latin)
    assert isinstance(doc, Nota)
    assert doc.itens[0].descricao == "AÇÚCAR CRISTAL"
