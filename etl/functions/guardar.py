"""
=====================================================================
 PASSO 7 - GRAVAR OS RESULTADOS
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   Depois de tudo validado, gravamos as tabelas em ficheiros CSV que o
   Power BI vai ler. Três cuidados:

   1. Os ficheiros são SEMPRE substituídos (nunca acrescentados).
      Por isso, correr o ETL duas vezes dá exatamente o mesmo resultado
      e não duplica linhas (requisito do enunciado).
   2. Este passo só corre DEPOIS dos controlos críticos. Se algum
      falhar, o programa pára antes e os ficheiros antigos ficam intactos.
   3. Formato fixo: UTF-8, vírgula a separar colunas, PONTO decimal
      e datas AAAA-MM-DD. No Power BI, os tipos são convertidos com a
      região "Inglês (Estados Unidos)" para ler bem o ponto decimal.

 BIBLIOTECAS USADAS
   - logging: regista cada ficheiro gravado.
     Usada nas linhas: 47  (importada na linha 23)
=====================================================================
"""
import logging


def gravar_csv(tabela, pasta, nome, arredondar):
    pasta.mkdir(parents=True, exist_ok=True)      # cria a pasta se não existir
    tabela = tabela.copy()

    # As colunas de data ficam em texto no formato ISO, igual em qualquer PC
    for coluna in tabela.columns:
        if str(tabela[coluna].dtype).startswith("datetime"):
            if coluna == "Data":
                tabela[coluna] = tabela[coluna].dt.strftime("%Y-%m-%d")
            else:
                tabela[coluna] = tabela[coluna].dt.strftime("%Y-%m-%d %H:%M:%S")

    # Nas tabelas de qualidade (resumos) arredondamos a 6 casas decimais só
    # para ficarem legíveis (ex.: 387.68000000002 -> 387.68). Na fVendas NÃO
    # arredondamos, para os totais no Power BI não acumularem diferenças.
    if arredondar:
        tabela = tabela.round(6)

    caminho = pasta / nome
    # mode="w" (o normal): se o ficheiro já existir, é substituído
    tabela.to_csv(caminho, index=False, encoding="utf-8", sep=",", decimal=".")
    logging.info(f"Gravado {caminho.name} ({len(tabela)} linhas)")


def gravar_tudo(tabelas, pasta, arredondar=False):
    """tabelas = dicionário {nome do ficheiro: tabela}"""
    for nome, tabela in tabelas.items():
        gravar_csv(tabela, pasta, nome, arredondar)
