"""
=====================================================================
 PASSO 3 - TAXAS DE CÂMBIO E CONVERSÃO PARA EUROS
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   A direção quer ver os valores em libras (GBP) e em euros (EUR).
   O Banco Central Europeu dá uma taxa média por mês: quantas libras
   vale 1 euro (ex.: 0,80). Por isso:  EUR = GBP / taxa
   Exemplo do enunciado: 100 GBP / 0,80 = 125 EUR.

   Regras importantes (do enunciado):
     - cada linha é convertida com a taxa do SEU mês, e só depois se
       somam os valores (nunca se converte um total com uma média);
     - tem de existir exatamente UMA taxa por mês, e positiva;
     - juntar as taxas às vendas não pode criar linhas a mais nem
       alterar o valor em libras.

 O QUE FAZ
   1. validar_taxas(): procura meses em falta, repetidos ou taxas <= 0.
   2. juntar_taxas(): junta a taxa a cada linha, calcula o valor em EUR
      e confirma que o nº de linhas e o total em GBP não mudaram.

 BIBLIOTECAS USADAS
   - logging: escreve mensagens de progresso no ecrã e no log.
     Usada nas linhas: 56, 58, 83  (importada na linha 30)
   - configuracao (cfg): lista dos 13 meses que têm de ter taxa.
     Usada nas linhas: 40  (importada na linha 32)
=====================================================================
"""
import logging

import configuracao as cfg


def validar_taxas(taxas, meses_das_vendas):
    """Devolve uma lista de problemas. Lista vazia = está tudo bem."""
    problemas = []

    # 1) Meses que deviam ter taxa (os 13 do enunciado + os que aparecem nas vendas)
    meses_necessarios = sorted(set(cfg.MESES_ANALISE) | set(meses_das_vendas))
    meses_em_falta = [mes for mes in meses_necessarios if mes not in taxas["AnoMes"].values]
    if meses_em_falta:
        problemas.append(f"meses sem taxa: {meses_em_falta}")

    # 2) Meses com mais do que uma taxa
    repetidos = taxas.loc[taxas["AnoMes"].duplicated(), "AnoMes"].tolist()
    if repetidos:
        problemas.append(f"meses com mais de uma taxa: {repetidos}")

    # 3) Taxas vazias, zero ou negativas
    invalidas = taxas.loc[taxas["TaxaGBPporEUR"].isna() | (taxas["TaxaGBPporEUR"] <= 0), "AnoMes"]
    if len(invalidas) > 0:
        problemas.append(f"taxas vazias ou não positivas em: {invalidas.tolist()}")

    if problemas:
        logging.warning(f"Problemas nas taxas de câmbio: {problemas}")
    else:
        logging.info("Taxas de câmbio validadas: 1 taxa positiva por mês, sem meses em falta.")
    return problemas


def juntar_taxas(elegiveis, taxas):
    """Junta a taxa do mês a cada linha e calcula o ValorEUR."""
    linhas_antes = len(elegiveis)
    gbp_antes = elegiveis["ValorGBP"].sum()

    # merge = "PROCV" do Excel: para cada linha, vai buscar a taxa do mesmo AnoMes.
    # validate="many_to_one" obriga a que cada mês tenha só uma taxa;
    # se houvesse duas, o Python dava erro em vez de duplicar linhas.
    elegiveis = elegiveis.merge(taxas, on="AnoMes", how="left", validate="many_to_one")

    # Conversão linha a linha
    elegiveis["ValorEUR"] = elegiveis["ValorGBP"] / elegiveis["TaxaGBPporEUR"]

    # Guardar os números para o controlo de qualidade da junção
    resultado_juncao = {
        "linhas_antes": linhas_antes,
        "linhas_depois": len(elegiveis),
        "gbp_antes": gbp_antes,
        "gbp_depois": elegiveis["ValorGBP"].sum(),
        "linhas_sem_taxa": int(elegiveis["TaxaGBPporEUR"].isna().sum()),
    }
    logging.info(f"Câmbio aplicado a {len(elegiveis)} linhas.")
    return elegiveis, resultado_juncao
