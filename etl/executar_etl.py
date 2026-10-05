"""
=====================================================================
 PROGRAMA PRINCIPAL DO ETL  ->  python etl/executar_etl.py
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   É o ficheiro que se executa. Não tem regras de negócio: só chama
   os passos pela ordem certa, como um índice do processo:

     Passo 1  Ler o Excel de vendas e o CSV de câmbios
     Passo 2  Marcar duplicados, normalizar e classificar cada linha
     Passo 3  Validar as taxas e converter cada linha para EUR
     Passo 4  Criar as tabelas do modelo em estrela
     Passo 5  Correr os controlos (pára se um controlo crítico falhar)
     Passo 6  Criar as tabelas de qualidade para a página 5
     Passo 7  Gravar tudo em CSV (substituindo os ficheiros anteriores)

   Cada execução cria um ficheiro de log em etl/logs/ com tudo o que
   aconteceu. O ETL funciona sem internet: só lê dados/origem/.

 BIBLIOTECAS USADAS
   - logging: configura as mensagens para irem para o ecrã E para
     um ficheiro de log.
     Usada nas linhas: 56, 57, 60, 68, 138, 139, 140, 141, 142, 143,
       144, 145, 155  (importada na linha 38)
   - sys: terminar o programa com código de erro se algo falhar.
     Usada nas linhas: 156  (importada na linha 39)
   - datetime: data e hora de início (nome do log e registo da execução).
     Usada nas linhas: 66  (importada na linha 40)
   - configuracao (cfg): caminhos das pastas.
     Usada nas linhas: 54, 55, 133, 134  (importada na linha 42)
   - ler_dados ... passo7: os nossos ficheiros, um por cada passo.
     Usados nas linhas: 71, 72, 73, 74, 77, 78, 79, 80, 81, 82, 83, 89,
       90, 91, 93, 94, 97, 98, 99, 100, 101, 102, 103, 105, 106, 107,
       108, 111, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124,
       133, 134, 137  (importada na linha 43, 44, 45, 46, 47, 48, 49)
=====================================================================
"""
import logging
import sys
from datetime import datetime

import configuracao as cfg
import functions.ler_dados as ler_dados
import functions.limpar_classificar as limpar_classificar
import functions.cambio as cambio
import functions.criar_modelo as criar_modelo
import functions.controlos as controlos
import functions.tabelas_qualidade as tabelas_qualidade
import functions.guardar as guardar


def preparar_log(inicio):
    """Mensagens vão para o ecrã e para etl/logs/etl_AAAAMMDD_HHMMSS.log"""
    cfg.PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    ficheiro_log = cfg.PASTA_LOGS / f"etl_{inicio.strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(ficheiro_log, encoding="utf-8"), logging.StreamHandler()],
    )
    return ficheiro_log


def main():
    inicio = datetime.now()
    ficheiro_log = preparar_log(inicio)
    logging.info("===== INÍCIO DO ETL =====")

    # ---------------- PASSO 1: LER ----------------
    vendas = ler_dados.ler_vendas()
    taxas = ler_dados.ler_cambio()
    controlos.controlo_linhas_entrada(vendas)
    nulos = controlos.controlo_nulos(vendas)

    # ---------------- PASSO 2: LIMPAR E CLASSIFICAR ----------------
    vendas = limpar_classificar.marcar_duplicados(vendas)
    vendas = limpar_classificar.normalizar(vendas)
    vendas = limpar_classificar.classificar(vendas)
    controlos.controlo_duplicados(vendas)
    controlos.controlo_exclusoes(vendas)
    controlos.controlo_conservacao_linhas(vendas)
    controlos.parar_se_houver_falhas("depois da classificação")

    # Daqui para a frente só trabalhamos com as linhas elegíveis
    elegiveis = vendas[vendas["Estado"] == "Elegível"].copy()

    # ---------------- PASSO 3: CÂMBIO ----------------
    problemas_cambio = cambio.validar_taxas(taxas, elegiveis["AnoMes"].unique())
    controlos.controlo_cambio(problemas_cambio, taxas)
    controlos.parar_se_houver_falhas("na validação do câmbio")

    elegiveis, resultado_juncao = cambio.juntar_taxas(elegiveis, taxas)
    controlos.controlo_juncao(resultado_juncao)

    # ---------------- PASSO 4: MODELO ----------------
    fvendas = criar_modelo.criar_fvendas(elegiveis)
    dproduto = criar_modelo.criar_dproduto(elegiveis)
    dcliente = criar_modelo.criar_dcliente(elegiveis)
    dpais = criar_modelo.criar_dpais(elegiveis)
    dcalendario = criar_modelo.criar_dcalendario(elegiveis)
    dcambio = criar_modelo.criar_dcambio(taxas)
    dmoeda, dfaixas = criar_modelo.criar_tabelas_auxiliares()

    controlos.controlo_reconciliacao(vendas, fvendas)
    controlos.controlo_modelo(fvendas, dproduto, dcliente, dpais, dcalendario, dcambio)
    controlos.controlo_sem_duplicacao(fvendas)
    controlos.parar_se_houver_falhas("depois de criar o modelo")

    # ---------------- PASSO 6: TABELAS DE QUALIDADE ----------------
    controlos_ = controlos.tabela_controlos()
    qualidade = {
        "qa_controlos.csv": controlos_,
        "qa_nulos.csv": tabelas_qualidade.tabela_nulos(nulos),
        "qa_resumo_estados.csv": tabelas_qualidade.tabela_resumo_estados(vendas),
        "qa_reconciliacao.csv": tabelas_qualidade.tabela_reconciliacao(vendas, fvendas),
        "qa_problemas_decisoes.csv": tabelas_qualidade.tabela_problemas_decisoes(vendas, fvendas, dproduto),
        "qa_cobertura_cambio.csv": tabelas_qualidade.tabela_cobertura_cambio(taxas, fvendas),
        "qa_amostras_validacao.csv": tabelas_qualidade.tabela_amostras(fvendas),
        "qa_quantidades_extremas.csv": tabelas_qualidade.tabela_quantidades_extremas(fvendas, dproduto),
        "qa_codigos_fora_padrao.csv": tabelas_qualidade.tabela_codigos_fora_padrao(vendas),
        "qa_linhas_fora_da_analise.csv": tabelas_qualidade.tabela_linhas_fora(vendas),
        "qa_fontes.csv": tabelas_qualidade.tabela_fontes(),
        "etl_ultima_execucao.csv": tabelas_qualidade.tabela_execucao(inicio, len(vendas), len(fvendas), controlos_),
    }

    # ---------------- PASSO 7: GRAVAR ----------------
    modelo = {
        "fVendas.csv": fvendas, "dProduto.csv": dproduto, "dCliente.csv": dcliente,
        "dPais.csv": dpais, "dCalendario.csv": dcalendario, "dCambio.csv": dcambio,
        "dMoeda.csv": dmoeda, "dFaixaEncomendas.csv": dfaixas,
    }
    guardar.gravar_tudo(modelo, cfg.PASTA_TRATADOS)
    guardar.gravar_tudo(qualidade, cfg.PASTA_QUALIDADE, arredondar=True)

    # ---------------- RESUMO FINAL ----------------
    ind = tabelas_qualidade.calcular_indicadores(fvendas)
    logging.info("===== ETL CONCLUÍDO COM SUCESSO =====")
    logging.info(f"Linhas lidas: {len(vendas)} | Linhas na fVendas: {len(fvendas)}")
    logging.info(f"Vendas brutas: {ind['VendasBrutasGBP']:,.2f} GBP | {ind['VendasBrutasEUR']:,.2f} EUR")
    logging.info(f"Estornos: {ind['EstornosGBP']:,.2f} GBP | {ind['EstornosEUR']:,.2f} EUR")
    logging.info(f"Vendas líquidas: {ind['VendasLiquidasGBP']:,.2f} GBP | {ind['VendasLiquidasEUR']:,.2f} EUR")
    logging.info(f"Encomendas de venda: {ind['EncomendasVenda']}")
    logging.info(f"Resultados dos controlos: {controlos_['Resultado'].value_counts().to_dict()}")
    logging.info(f"Log desta execução: {ficheiro_log}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise          # paragem controlada (a mensagem já foi mostrada)
    except Exception:
        # Erro inesperado: fica registado no log com todos os detalhes
        logging.exception("Erro inesperado. O ETL parou e os resultados anteriores não foram alterados.")
        sys.exit(1)
