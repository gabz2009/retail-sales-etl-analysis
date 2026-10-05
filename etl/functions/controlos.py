"""
=====================================================================
 PASSO 5 - CONTROLOS DE QUALIDADE
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   O enunciado pede pelo menos 6 controlos (contagens, nulos,
   duplicados, anomalias, cobertura cambial e reconciliação).
   Um controlo é uma verificação automática: "isto bate certo?".
   Cada controlo fica registado com: o que se esperava, o que se obteve
   e o resultado (OK, AVISO, FALHA ou INFO).

   Controlos CRÍTICOS: se um deles falhar, o ETL pára ANTES de gravar
   os resultados. Assim nunca ficam ficheiros errados na pasta
   "tratados", e o erro fica visível no ecrã e no log.

 CONTROLOS
   C01 Linhas de entrada               C06 Cobertura cambial (crítico)
   C02 Valores em falta (nulos)        C07 Junção cambial (crítico)
   C03 Duplicados                      C08 Reconciliação de valor (crítico)
   C04 Exclusões e anomalias           C09 Chaves do modelo (crítico)
   C05 Contagem entrada/saída (crít.)  C10 Sem linhas repetidas (crítico)

 BIBLIOTECAS USADAS
   - pandas (pd): transformar a lista de controlos numa tabela.
     Usada nas linhas: 154  (importada na linha 35)
   - logging: escreve cada controlo no ecrã e no log.
     Usada nas linhas: 50, 52, 54  (importada na linha 33)
   - configuracao (cfg): nº de linhas esperado, pasta de logs e a
     função que pára o programa com erro.
     Usada nas linhas: 59, 60, 101, 161, 164  (importada na linha 37)
=====================================================================
"""
import logging

import pandas as pd

import configuracao as cfg

# Lista onde vamos juntando os resultados de todos os controlos
controlos = []


def registar(codigo, nome, esperado, obtido, resultado, critico, detalhe=""):
    controlos.append({
        "Controlo": codigo, "Descricao": nome, "Esperado": esperado, "Obtido": obtido,
        "Resultado": resultado, "Critico": "Sim" if critico else "Não", "Detalhe": detalhe,
    })
    mensagem = f"[{codigo}] {nome}: {resultado} (obtido: {obtido}) {detalhe}"
    if resultado == "FALHA":
        logging.error(mensagem)
    elif resultado == "AVISO":
        logging.warning(mensagem)
    else:
        logging.info(mensagem)


def controlo_linhas_entrada(vendas):
    total = len(vendas)
    resultado = "OK" if total == cfg.LINHAS_ESPERADAS else "AVISO"
    registar("C01", "Linhas lidas do Excel de vendas", cfg.LINHAS_ESPERADAS, total, resultado, False,
             "" if resultado == "OK" else "O número é diferente do indicado no enunciado")


def controlo_nulos(vendas):
    colunas = ["InvoiceNo", "StockCode", "Description", "Quantity",
               "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    nulos = {coluna: int(vendas[coluna].isna().sum()) for coluna in colunas}
    detalhe = "; ".join(f"{coluna}={n}" for coluna, n in nulos.items() if n > 0)
    registar("C02", "Valores em falta por coluna", "-", sum(nulos.values()), "INFO", False, detalhe)
    return nulos


def controlo_duplicados(vendas):
    duplicados = vendas[vendas["Estado"] == "Duplicada"]
    registar("C03", "Duplicados exatos (8 colunas iguais)", "-", len(duplicados), "INFO", False,
             f"Valor removido: {duplicados['ValorGBP'].sum():.2f} GBP")


def controlo_exclusoes(vendas):
    fora = vendas[vendas["Estado"].isin(["Excluída", "Anomalia"])]
    partes = []
    for motivo, grupo in fora.groupby("Motivo"):
        partes.append(f"{motivo}={len(grupo)} ({grupo['ValorGBP'].sum():.2f} GBP)")
    registar("C04", "Linhas excluídas e anomalias por motivo", "-", len(fora), "INFO", False,
             "; ".join(partes))


def controlo_conservacao_linhas(vendas):
    # Cada linha tem de ter exatamente um estado: a soma dos estados = entrada
    contagem = vendas["Estado"].value_counts()
    soma = int(contagem.sum())
    resultado = "OK" if soma == len(vendas) and vendas["Estado"].notna().all() else "FALHA"
    detalhe = " + ".join(f"{estado}={n}" for estado, n in contagem.items())
    registar("C05", "Entrada = elegíveis + duplicadas + excluídas + anomalias",
             len(vendas), soma, resultado, True, detalhe)


def controlo_cambio(problemas_cambio, taxas):
    resultado = "OK" if len(problemas_cambio) == 0 else "FALHA"
    registar("C06", "Cobertura cambial: 1 taxa positiva por mês, sem meses em falta",
             f"{len(cfg.MESES_ANALISE)} meses", f"{taxas['AnoMes'].nunique()} meses",
             resultado, True, "; ".join(problemas_cambio))


def controlo_juncao(res):
    tudo_igual = (res["linhas_antes"] == res["linhas_depois"]
                  and abs(res["gbp_antes"] - res["gbp_depois"]) < 0.01
                  and res["linhas_sem_taxa"] == 0)
    registar("C07", "Junção do câmbio não cria linhas nem altera o valor GBP",
             f"{res['linhas_antes']} linhas / {res['gbp_antes']:.2f} GBP",
             f"{res['linhas_depois']} linhas / {res['gbp_depois']:.2f} GBP",
             "OK" if tudo_igual else "FALHA", True,
             f"Linhas sem taxa: {res['linhas_sem_taxa']}")


def controlo_reconciliacao(vendas, fvendas):
    # O valor total do Excel tem de ser igual a: valor do que ficou de fora + valor da fVendas
    total_origem = vendas["ValorGBP"].sum()
    total_fora = vendas.loc[vendas["Estado"] != "Elegível", "ValorGBP"].sum()
    total_modelo = fvendas["ValorGBP"].sum()
    diferenca = total_origem - (total_fora + total_modelo)
    registar("C08", "Reconciliação: valor origem = valor fora + valor fVendas (GBP)",
             f"{total_origem:.2f}", f"{total_fora + total_modelo:.2f}",
             "OK" if abs(diferenca) < 0.01 else "FALHA", True, f"Diferença: {diferenca:.6f} GBP")


def controlo_modelo(fvendas, dproduto, dcliente, dpais, dcalendario, dcambio):
    problemas = []
    # a) As chaves das dimensões não podem ter repetidos
    for nome, tabela, chave in [("dProduto", dproduto, "StockCode"), ("dCliente", dcliente, "ClienteKey"),
                                ("dPais", dpais, "PaisKey"), ("dCalendario", dcalendario, "Data"),
                                ("dCambio", dcambio, "AnoMes")]:
        repetidos = tabela[chave].duplicated().sum()
        if repetidos > 0:
            problemas.append(f"{nome} tem {repetidos} chaves repetidas")
    # b) Todas as chaves da fVendas têm de existir nas dimensões
    for coluna, tabela in [("StockCode", dproduto), ("ClienteKey", dcliente),
                           ("PaisKey", dpais), ("Data", dcalendario)]:
        em_falta = (~fvendas[coluna].isin(tabela[coluna])).sum()
        if em_falta > 0:
            problemas.append(f"{em_falta} linhas da fVendas com {coluna} sem correspondência")
    registar("C09", "Chaves únicas nas dimensões e todas as ligações da fVendas existem",
             0, len(problemas), "OK" if not problemas else "FALHA", True, "; ".join(problemas))


def controlo_sem_duplicacao(fvendas):
    # Cada linha do Excel só pode aparecer uma vez na fVendas
    repetidas = int(fvendas["LinhaOrigem"].duplicated().sum())
    registar("C10", "Cada linha de origem aparece uma só vez na fVendas", 0, repetidas,
             "OK" if repetidas == 0 else "FALHA", True)


def tabela_controlos():
    return pd.DataFrame(controlos)


def parar_se_houver_falhas(momento):
    """Se algum controlo crítico falhou, grava os controlos no log e pára."""
    falhas = [c for c in controlos if c["Resultado"] == "FALHA" and c["Critico"] == "Sim"]
    if falhas:
        ficheiro = cfg.PASTA_LOGS / "controlos_com_falha.csv"
        tabela_controlos().to_csv(ficheiro, index=False, encoding="utf-8")
        lista = "; ".join(f"{c['Controlo']} {c['Descricao']} ({c['Detalhe']})" for c in falhas)
        cfg.parar_com_erro(f"Controlos críticos falharam ({momento}): {lista}. "
                           f"Os resultados anteriores NÃO foram alterados. Ver {ficheiro}")
