# Conferi AI

Conferência e organização de notas fiscais para escritórios de contabilidade.

O Conferi AI lê os XMLs de NF-e e NFC-e dos clientes do escritório, organiza tudo por empresa,
remove notas repetidas, trata cancelamentos, confere as notas com regras automáticas e com a
relação da Sefaz, e entrega planilhas e relatórios prontos. **Tudo roda no computador do
escritório: nenhum XML é enviado para a internet.**

> Os alertas são pontos para conferência. A decisão fiscal continua sendo do profissional
> responsável. Regras em transição (como IBS/CBS) são configuráveis e devem ser confirmadas nas
> notas técnicas vigentes.

---

## Funcionalidades do MVP

| Área | O que faz |
|---|---|
| **Importação** | Pastas (com subpastas), XMLs soltos e `.zip`, por arrastar e soltar. NF-e, NFC-e, lotes, eventos de cancelamento e inutilizações. |
| **Organização** | Empresas identificadas automaticamente pelos XMLs; confirmação rápida de quem é cliente; repetidas ignoradas pela chave de acesso; nota sem protocolo atualizada quando chega a versão autorizada. |
| **Conferência** | Lacunas na numeração (descontando inutilizações), soma dos itens, composição do total, CFOP × operação, CFOP × destino, UF × destino, CFOP de venda em devolução, NCM (formato e, opcionalmente, tabela vigente), campos de IBS/CBS, notas sem protocolo, denegadas e de homologação. |
| **Cliente × Sefaz** | Cruza as notas do cliente com o arquivo do portal (CSV, TXT ou XLSX): faltando no escritório, fora da Sefaz, canceladas só de um lado. |
| **Pendências** | Filtros por cliente, período, nível e regra; marcar como resolvida ou ignorada (a decisão sobrevive ao recálculo). |
| **Relatórios** | Excel completo (resumo, notas, itens, por fornecedor, comprador, CFOP, NCM, mês, pendências) e PDF de pendências. |
| **Dados e backup** | SQLite local; backup automático antes de importar, ao fechar e diariamente, na pasta escolhida (Drive, servidor, disco); verificação de integridade ao abrir e restauração em dois cliques. |

## Como rodar (Linux/Kali ou Windows)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run_conferi.py
```

No Kali/Debian, se o Qt reclamar de bibliotecas do sistema ao abrir a janela:

```bash
sudo apt install libxcb-cursor0 libxkbcommon-x11-0
```

## Testar com dados de demonstração

Dentro do aplicativo: **Configurações → Gerar e importar demonstração**.

Ou pela linha de comando:

```bash
python scripts/gerar_demo.py ~/demo_conferi
```

A pasta traz XMLs fictícios de três clientes (uma padaria com NFC-e, uma distribuidora no regime
normal e uma loja), com problemas conhecidos: lacunas, total divergente, CFOP e UF incoerentes,
NCM inválido, IBS/CBS ausente, cancelamento, inutilização, notas repetidas dentro de um `.zip`,
um arquivo corrompido e um arquivo da Sefaz (`sefaz_padaria_outubro.csv`). O arquivo
`gabarito.json` diz o que o Conferi AI deve encontrar.

## Testes automáticos

```bash
pytest -q
ruff check conferi tests
```

- `tests/test_parser.py`: leitura de XML (com e sem protocolo e namespace, NFC-e, eventos,
  inutilização, arquivos inválidos, proteção contra entidades maliciosas, Latin-1).
- `tests/test_fluxo_completo.py`: importação, clientes, regras, Sefaz, exportações e backup,
  conferidos contra o gabarito.
- `tests/test_ui_smoke.py`: abre todas as telas sem exibir janelas (`QT_QPA_PLATFORM=offscreen`).

## Gerar o instalador para Windows

```powershell
.\scripts\build_windows.ps1
```

Gera `dist\ConferiAI\ConferiAI.exe` com PyInstaller e, se o Inno Setup estiver instalado, o
instalador em `dist\instalador`.

## Estrutura

```
conferi/
├── core/                 # núcleo, sem dependência de interface
│   ├── parser.py         # leitura segura dos XMLs (defusedxml)
│   ├── sources.py        # fontes de entrada plugáveis (pasta/.zip; Sefaz na etapa 3)
│   ├── db.py             # schema SQLite (valores em centavos, WAL)
│   ├── importer.py       # importação, repetidas e cancelamentos
│   ├── clientes.py       # sugestão e confirmação de clientes
│   ├── rules.py          # regras de conferência e pendências
│   ├── sefaz.py          # conferência cliente × Sefaz
│   ├── backup.py         # backup, verificação e restauração
│   ├── consultas.py      # consultas das telas
│   ├── servico.py        # operações de alto nível
│   └── exporters/        # Excel e PDF
├── ui/                   # interface PySide6 (tema, telas, diálogos)
├── testing/              # gerador de XMLs fictícios e cenário de demonstração
└── assets/fonts/         # Lora, Poppins e Carlito (SIL OFL 1.1)
```

## Onde ficam os dados

- Base local: pasta de dados do usuário (`~/.local/share/Conferi AI` no Linux,
  `%LOCALAPPDATA%\MARCOS C. DATA\Conferi AI` no Windows).
- Backups: pasta escolhida em Configurações (padrão: subpasta `backups` da pasta de dados).
- O banco em uso nunca deve ficar dentro de uma pasta sincronizada; só as cópias vão para lá.

## Próximas etapas

- **Extras:** painel da carteira com alertas de limite, pagamento integrado das NFC-e (Ceará),
  variação de preço e curva ABC, relatório mensal por cliente, NFS-e nacional, conciliação com
  extrato e maquininha, backup criptografado, licença por escritório.
- **Etapa 3:** captura automática com certificado digital e integração com o sistema contábil.
