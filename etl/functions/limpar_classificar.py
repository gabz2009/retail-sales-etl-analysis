"""
=====================================================================
 PASSO 2 - LIMPAR E CLASSIFICAR AS LINHAS DE VENDA
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   Os dados brutos têm problemas: linhas repetidas, preços a zero,
   cancelamentos, códigos que não são produtos, clientes em falta,
   nomes de países diferentes para o mesmo país, etc.
   Aqui decidimos o que fazer com CADA linha, sem apagar nada às
   escondidas: cada linha recebe um Estado e um Motivo.

     Estado      Significado
     ---------   ------------------------------------------------
     Elegível    entra na análise (como Venda ou como Estorno)
     Duplicada   é uma cópia exata de uma linha anterior
     Excluída    não cumpre as regras da base elegível
     Anomalia    tem um problema que precisa de análise separada

   Cada linha fica com UM SÓ motivo (o da primeira regra que falha).
   Isto garante que no fim: entrada = elegíveis + duplicadas +
   excluídas + anomalias, sem contar a mesma linha duas vezes.

 O QUE FAZ
   1. marcar_duplicados(): encontra linhas repetidas.
   2. normalizar(): corrige códigos, descrições, países e clientes.
   3. classificar(): aplica as regras e decide o Estado de cada linha.

 BIBLIOTECAS USADAS
   - logging: escreve mensagens de progresso no ecrã e no log.
     Usada nas linhas: 56, 106, 139  (importada na linha 37)
   - configuracao (cfg): regras de negócio (códigos a excluir, países).
     Usada nas linhas: 81, 84, 127  (importada na linha 39)
   (O pandas não é importado aqui porque só usamos métodos das tabelas
    que já recebemos do passo 1.)
=====================================================================
"""
import logging

import configuracao as cfg

COLUNAS_ORIGEM = ["InvoiceNo", "StockCode", "Description", "Quantity",
                  "InvoiceDate", "UnitPrice", "CustomerID", "Country"]


def marcar_duplicados(vendas):
    # Uma linha é DUPLICADA se for igual a uma anterior nas 8 colunas.
    # Não usamos só InvoiceNo + StockCode, porque a mesma fatura pode ter
    # o mesmo produto em várias linhas com quantidades diferentes (legítimo).
    # keep="first": a primeira ocorrência fica; as seguintes são marcadas.
    vendas["Duplicado"] = vendas.duplicated(subset=COLUNAS_ORIGEM, keep="first")

    # Evidência: para cada duplicado guardamos a linha da 1.ª ocorrência
    primeira = vendas.groupby(COLUNAS_ORIGEM, dropna=False)["LinhaOrigem"].transform("min")
    vendas["LinhaPrimeiraOcorrencia"] = primeira.where(vendas["Duplicado"])

    logging.info(f"Duplicados exatos encontrados: {vendas['Duplicado'].sum()}")
    return vendas


def normalizar(vendas):
    # --- Produto: códigos em maiúsculas ("85123a" passa a "85123A") ---
    vendas["StockCodeOriginal"] = vendas["StockCode"]
    vendas["StockCode"] = vendas["StockCode"].str.upper()

    # --- Descrição: sem espaços a mais e em maiúsculas ---
    # (a coluna original Description fica guardada tal como veio)
    vendas["Descricao"] = (vendas["Description"].str.strip()
                           .str.replace(r"\s+", " ", regex=True)
                           .str.upper())

    # --- Prefixo da fatura: "C" = cancelamento (segundo a documentação) ---
    primeira_letra = vendas["InvoiceNo"].str[0]
    vendas["PrefixoC"] = primeira_letra == "C"
    # Outras letras (ex.: "A") não estão documentadas -> anomalia no passo 3
    vendas["PrefixoDesconhecido"] = (primeira_letra.str.isalpha().fillna(False).astype(bool)
                                     & ~vendas["PrefixoC"])

    # --- Cliente: se não tiver CustomerID, fica como "DESCONHECIDO" ---
    # (a venda continua a contar; só sai dos indicadores de clientes)
    vendas["ClienteIdentificado"] = vendas["CustomerID"].notna()
    vendas["ClienteKey"] = vendas["CustomerID"].fillna(cfg.CLIENTE_DESCONHECIDO)

    # --- País: corrigir nomes (EIRE -> Ireland, RSA -> South Africa, ...) ---
    vendas["PaisKey"] = vendas["Country"].fillna("Unspecified").replace(cfg.CORRECAO_PAISES)

    # --- Datas: dia (sem hora) e mês no formato "2011-01" ---
    vendas["Data"] = vendas["InvoiceDate"].dt.normalize()
    vendas["AnoMes"] = vendas["InvoiceDate"].dt.strftime("%Y-%m")

    # --- Valor da linha em libras (GBP), com sinal ---
    # Quantidade negativa dá valor negativo (estornos).
    # round(6) só tira o "lixo" dos números decimais do computador
    # (ex.: 15.299999999 -> 15.3), sem perder precisão real.
    vendas["ValorGBP"] = (vendas["Quantity"] * vendas["UnitPrice"]).round(6)

    return vendas


def aplicar_regra(vendas, condicao, estado, motivo):
    """Marca as linhas que cumprem a condição e que AINDA não têm motivo.
    Como só mexe em linhas sem motivo, cada linha fica com um só motivo."""
    ainda_sem_motivo = vendas["Motivo"] == ""
    linhas = ainda_sem_motivo & condicao.fillna(False).astype(bool)
    vendas.loc[linhas, "Estado"] = estado
    vendas.loc[linhas, "Motivo"] = motivo
    logging.info(f"Regra '{motivo}': {linhas.sum()} linhas")


def classificar(vendas):
    # No início todas as linhas são elegíveis e não têm motivo
    vendas["Estado"] = "Elegível"
    vendas["Motivo"] = ""

    # As regras são aplicadas POR ESTA ORDEM (a ordem define a prioridade)
    aplicar_regra(vendas, vendas["Duplicado"],
                  "Duplicada", "Duplicado exato")
    aplicar_regra(vendas, vendas["InvoiceDate"].isna(),
                  "Excluída", "Data inválida")
    aplicar_regra(vendas, vendas["InvoiceNo"].isna() | vendas["StockCode"].isna(),
                  "Excluída", "Fatura ou produto em falta")
    aplicar_regra(vendas, vendas["Quantity"].isna() | (vendas["Quantity"] == 0),
                  "Excluída", "Quantidade nula ou zero")
    aplicar_regra(vendas, vendas["UnitPrice"].isna() | (vendas["UnitPrice"] <= 0),
                  "Excluída", "Preço nulo, zero ou negativo")
    aplicar_regra(vendas, vendas["PrefixoC"] & (vendas["Quantity"] > 0),
                  "Anomalia", "Fatura C com quantidade positiva")
    aplicar_regra(vendas, vendas["StockCode"].isin(cfg.CODIGOS_EXCLUIR.keys()),
                  "Excluída", "Movimento não comercial")
    aplicar_regra(vendas, vendas["PrefixoDesconhecido"],
                  "Anomalia", "Prefixo de fatura desconhecido")

    # Nas linhas elegíveis: quantidade positiva = Venda, negativa = Estorno
    # (estorno com ou sem prefixo C, como diz o enunciado)
    elegivel = vendas["Estado"] == "Elegível"
    vendas["TipoMovimento"] = ""
    vendas.loc[elegivel & (vendas["Quantity"] > 0), "TipoMovimento"] = "Venda"
    vendas.loc[elegivel & (vendas["Quantity"] < 0), "TipoMovimento"] = "Estorno"

    logging.info(f"Linhas elegíveis: {elegivel.sum()} de {len(vendas)}")
    return vendas
