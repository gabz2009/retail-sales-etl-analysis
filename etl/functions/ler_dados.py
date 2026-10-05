"""
=====================================================================
 PASSO 1 - LER OS DADOS DE ORIGEM
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   Antes de tratar os dados é preciso lê-los da forma certa. O maior
   cuidado aqui é ler os códigos (fatura, produto, cliente) como TEXTO.
   Se o Python os lesse como números:
     - a fatura "C536379" e a "536365" ficavam com tipos misturados;
     - o cliente 17850 aparecia como 17850.0;
     - o produto "85123A" e o 22423 ficavam com tipos diferentes.
   Também acrescentamos a coluna LinhaOrigem (o número da linha no
   Excel) para conseguirmos seguir cada registo desde a origem até ao fim.

 O QUE FAZ
   1. ler_vendas(): lê o Excel de vendas e acerta os tipos das colunas.
   2. ler_cambio(): lê o CSV do Banco Central Europeu (taxas mensais).
   Os ficheiros originais nunca são alterados: só são lidos.

 BIBLIOTECAS USADAS
   - pandas (pd): biblioteca para trabalhar com tabelas (DataFrames).
     Usada nas linhas: 51, 75, 76, 77, 99, 103, 107  (importada na
       linha 33)
   - logging: escreve mensagens de progresso no ecrã e no log.
     Usada nas linhas: 45, 86, 109  (importada na linha 31)
   - configuracao (cfg): o nosso ficheiro com caminhos e regras.
     Usada nas linhas: 40, 41, 42, 51, 53, 61, 91, 92, 93, 99, 101
       (importada na linha 35)
=====================================================================
"""
import logging

import pandas as pd

import configuracao as cfg


def ler_vendas():
    # 1) Confirmar que o ficheiro existe
    if not cfg.FICHEIRO_VENDAS.exists():
        cfg.parar_com_erro(
            f"Não encontrei o ficheiro de vendas: {cfg.FICHEIRO_VENDAS}. "
            "Descarregue-o à mão (ver LEIA-ME) e copie-o para dados/origem/.")
        
    logging.info("A ler o Excel de vendas (pode demorar 1 a 2 minutos)...")

    # 2) Ler o Excel. As colunas de códigos e texto são lidas como texto (str).
    colunas_texto = {"InvoiceNo": str, "StockCode": str, "Description": str,
                     "CustomerID": str, "Country": str}
    try:
        vendas = pd.read_excel(cfg.FICHEIRO_VENDAS, dtype=colunas_texto)
    except PermissionError:
        cfg.parar_com_erro("Não consegui abrir o Excel de vendas. "
                           "Se estiver aberto no Excel, feche-o e volte a correr.")

    # 3) Confirmar que as 8 colunas esperadas existem
    colunas_esperadas = ["InvoiceNo", "StockCode", "Description", "Quantity",
                         "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    for coluna in colunas_esperadas:
        if coluna not in vendas.columns:
            cfg.parar_com_erro(f"O Excel de vendas não tem a coluna {coluna}.")
    vendas = vendas[colunas_esperadas]

    # 4) Número da linha no Excel (a linha 1 é o cabeçalho, os dados começam na 2)
    vendas.insert(0, "LinhaOrigem", range(2, len(vendas) + 2))

    # 5) Acertar os tipos dos números e das datas.
    #    errors="coerce": se um valor não for convertível fica vazio (NaN)
    #    em vez de o programa parar. Esses casos são contados no controlo C02
    #    e excluídos pelas regras do passo 2 (data inválida, quantidade nula...).
    #    Datas: no Excel, InvoiceDate está guardada como data verdadeira (não
    #    como texto), por isso é lida diretamente, sem risco de trocar o dia
    #    com o mês. Os números vêm do Excel já como números, por isso a
    #    vírgula/ponto decimal do computador não interfere.
    vendas["Quantity"] = pd.to_numeric(vendas["Quantity"], errors="coerce")
    vendas["UnitPrice"] = pd.to_numeric(vendas["UnitPrice"], errors="coerce")
    vendas["InvoiceDate"] = pd.to_datetime(vendas["InvoiceDate"], errors="coerce")

    # 6) Limpar espaços no início/fim dos códigos
    for coluna in ["InvoiceNo", "StockCode", "CustomerID", "Country"]:
        vendas[coluna] = vendas[coluna].str.strip()

    # 7) Por segurança: se algum cliente vier como "17850.0", fica "17850"
    vendas["CustomerID"] = vendas["CustomerID"].str.removesuffix(".0")

    logging.info(f"Li {len(vendas)} linhas do Excel de vendas.")
    return vendas


def ler_cambio():
    if not cfg.FICHEIRO_CAMBIO.exists():
        cfg.parar_com_erro(
            f"Não encontrei o ficheiro de câmbios: {cfg.FICHEIRO_CAMBIO}. "
            "Descarregue-o à mão (ver LEIA-ME) e copie-o para dados/origem/.")

    # O CSV do BCE tem muitas colunas; só precisamos de duas:
    #   TIME_PERIOD = mês (ex.: "2011-01")
    #   OBS_VALUE   = taxa média do mês (libras por 1 euro)
    cambio = pd.read_csv(cfg.FICHEIRO_CAMBIO, dtype=str)
    if "TIME_PERIOD" not in cambio.columns or "OBS_VALUE" not in cambio.columns:
        cfg.parar_com_erro("O CSV de câmbios não tem as colunas TIME_PERIOD e OBS_VALUE.")

    taxas = pd.DataFrame()
    taxas["AnoMes"] = cambio["TIME_PERIOD"].str.strip()
    # O BCE usa ponto como separador decimal (ex.: 0.8462). Convertemos
    # explicitamente para número, para não depender das definições do PC.
    taxas["TaxaGBPporEUR"] = pd.to_numeric(cambio["OBS_VALUE"], errors="coerce")

    logging.info(f"Li {len(taxas)} taxas de câmbio.")
    return taxas
