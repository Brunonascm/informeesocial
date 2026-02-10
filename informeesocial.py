import streamlit as st
import pandas as pd
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from fpdf import FPDF
import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador Pro de Informes", page_icon="💼", layout="wide")

st.title("💼 Gerador de Informes de Rendimentos (eSocial)")
st.markdown("""
**Instruções:**
1. Arraste os arquivos ZIP.
2. Defina o **Ano-Calendário** abaixo.
3. Corrija pendências e mapeie as rubricas.
4. Escolha: **Gerar PDF Oficial** ou **Exportar Relatório Excel**.
""")

# --- CLASSE PDF (LAYOUT RECEITA FEDERAL - BOX) ---
class PDFLayoutReceita(FPDF):
    def __init__(self, ano_calendario):
        super().__init__()
        self.ano_calendario = ano_calendario
        self.exercicio = int(ano_calendario) + 1
        self.set_auto_page_break(auto=True, margin=10)
        self.set_line_width(0.2) 

    def header(self):
        self.set_font('Arial', 'B', 8)
        self.cell(0, 4, 'MINISTÉRIO DA FAZENDA', 0, 1, 'L')
        self.cell(0, 4, 'SECRETARIA DA RECEITA FEDERAL DO BRASIL', 0, 1, 'L')
        self.ln(2)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 5, 'COMPROVANTE DE RENDIMENTOS PAGOS E DE', 0, 1, 'C')
        self.cell(0, 5, 'IMPOSTO SOBRE A RENDA RETIDO NA FONTE', 0, 1, 'C')
        self.ln(2)
        self.set_font('Arial', 'B', 9)
        # USA O ANO SELECIONADO PELO USUÁRIO
        self.cell(0, 5, f'ANO-CALENDÁRIO: {self.ano_calendario}   |   EXERCÍCIO: {self.exercicio}', 0, 1, 'R')
        self.ln(4)
        self.set_font('Arial', '', 6)
        self.multi_cell(0, 3, "Verifique as condições e o prazo para a apresentação da Declaração do Imposto sobre a Renda da Pessoa Física...", 0, 'C')
        self.ln(3)

    def campo_box(self, label, valor, w, h=10, ln=0):
        x = self.get_x()
        y = self.get_y()
        self.rect(x, y, w, h)
        self.set_font('Arial', '', 6)
        self.set_xy(x + 1, y + 1)
        self.cell(w-2, 3, label, 0, 0)
        self.set_font('Arial', 'B', 8)
        self.set_xy(x + 1, y + 5)
        valor_str = str(valor)
        if len(valor_str) > int(w/2): self.set_font('Arial', 'B', 7)
        self.cell(w-2, 4, valor_str, 0, 0)
        if ln == 1: self.set_xy(self.l_margin, y + h)
        else: self.set_xy(x + w, y)

    def linha_tabela(self, texto, valor):
        self.set_font('Arial', '', 7)
        self.cell(160, 5, texto, 1, 0, 'L') 
        self.set_font('Arial', 'B', 8)
        self.cell(0, 5, valor, 1, 1, 'R') 

    def titulo_secao(self, numero, texto):
        self.set_fill_color(230, 230, 230) 
        self.set_font('Arial', 'B', 8)
        self.cell(0, 6, f"{numero}. {texto}", 1, 1, 'L', 1) 

def fmt(valor):
    if isinstance(valor, str): return valor
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_pdf_final(dados_calculados, dados_cadastrais, ano_base):
    pdf = PDFLayoutReceita(ano_base) # Passa o ano para a classe
    pdf.add_page()
    
    # 1. Fonte Pagadora
    pdf.titulo_secao("1", "FONTE PAGADORA PESSOA JURÍDICA OU PESSOA FÍSICA")
    pdf.campo_box("CNPJ/CPF", dados_cadastrais['Empregador_CNPJ'], w=50) 
    pdf.campo_box("Nome Empresarial / Nome Completo", dados_cadastrais['Empregador_Nome'], w=140, ln=1)
    pdf.ln(2)

    # 2. Beneficiário
    pdf.titulo_secao("2", "PESSOA FÍSICA BENEFICIÁRIA DOS RENDIMENTOS")
    pdf.campo_box("CPF", dados_cadastrais['CPF'], w=40)
    pdf.campo_box("Nome Completo", dados_cadastrais['Nome'], w=150, ln=1)
    pdf.campo_box("Natureza do Rendimento", "Rendimento do Trabalho Assalariado", w=190, h=8, ln=1)
    pdf.ln(2)

    # 3. Rendimentos
    pdf.titulo_secao("3", "RENDIMENTOS TRIBUTÁVEIS, DEDUÇÕES E IMPOSTO RETIDO NA FONTE")
    pdf.linha_tabela("1. Total dos rendimentos (inclusive férias)", fmt(dados_calculados['v_bruto']))
    pdf.linha_tabela("2. Contribuição previdenciária oficial", fmt(dados_calculados['v_inss']))
    pdf.linha_tabela("3. Contribuição a previdência complementar", "0,00")
    pdf.linha_tabela("4. Pensão alimentícia", "0,00")
    pdf.linha_tabela("5. Imposto sobre a renda retido na fonte", fmt(dados_calculados['v_irrf']))
    pdf.ln(2)

    # 4. Isentos
    pdf.titulo_secao("4", "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS")
    pdf.linha_tabela("1. Parcela isenta de aposentadoria (65 anos+)", "0,00")
    pdf.linha_tabela("7. Outros", "0,00")
    pdf.ln(2)

    # 5. Exclusiva
    pdf.titulo_secao("5", "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA (RENDIMENTO LÍQUIDO)")
    pdf.linha_tabela("1. Décimo terceiro salário", fmt(dados_calculados['v_13_liq']))
    pdf.linha_tabela("2. Imposto sobre a renda retido na fonte sobre 13º salário", fmt(dados_calculados['v_13_irrf']))
    pdf.ln(2)

    # 7. Info Complementar
    pdf.titulo_secao("7", "INFORMAÇÕES COMPLEMENTARES")
    pdf.set_font('Arial', '', 7)
    pdf.multi_cell(0, 4, dados_calculados['txt_saude'], 1, 'L')
    pdf.ln(2)

    # 8. Responsável
    pdf.titulo_secao("8", "RESPONSÁVEL PELAS INFORMAÇÕES")
    pdf.campo_box("Nome", dados_cadastrais['Empregador_Nome'], w=110)
    # Data dinâmica com o ano do exercício
    data_assinatura = datetime.date.today().strftime('%d/%m/') + str(int(ano_base)+1)
    pdf.campo_box("Data", data_assinatura, w=30)
    pdf.campo_box("Assinatura", "", w=50, ln=1)
    
    pdf.ln(5)
    pdf.set_font('Arial', '', 6)
    pdf.cell(0, 4, "Aprovado pela Instrução Normativa RFB nº 1.682, de 28 de dezembro de 2016.", 0, 0, 'C')

    return pdf

# --- PROCESSAMENTO ---
def strip_namespace(xml_content):
    try:
        it = ET.iterparse(BytesIO(xml_content))
        for _, el in it:
            if '}' in el.tag: el.tag = el.tag.split('}', 1)[1]
        return it.root
    except: return None

def processar_arquivos(uploaded_files):
    s1200_data = []
    s1210_data = []
    mapa_nomes = {} 
    
    progress = st.progress(0)
    for i, file in enumerate(uploaded_files):
        with zipfile.ZipFile(file, "r") as z:
            for filename in z.namelist():
                if not filename.endswith('.xml'): continue
                with z.open(filename) as f:
                    content = f.read()
                    root = strip_namespace(content)
                    if root is None: continue
                    
                    if root.find('.//trabalhador'):
                        try:
                            mapa_nomes[root.find('.//cpfTrab').text] = root.find('.//nmTrab').text
                        except: pass
                    
                    elif root.find('.//evtRemun'): 
                        try:
                            cpf = root.find('.//cpfTrab').text
                            per_apur = root.find('.//perApur').text 
                            cnpj_emp = root.find('.//ideEmpregador/nrInsc').text
                            for dmDev in root.findall('.//dmDev'):
                                for item in dmDev.findall('.//itensRemun'):
                                    s1200_data.append({
                                        'CPF': cpf,
                                        'Competencia': per_apur,
                                        'Rubrica': item.find('codRubr').text,
                                        'Valor': float(item.find('vrRubr').text),
                                        'CNPJ_Emp': cnpj_emp
                                    })
                        except: pass
                    
                    elif root.find('.//evtPgtos'): 
                        try:
                            ide_benef = root.find('.//ideBenef')
                            cpf = ide_benef.find('cpfBenef').text
                            for infoPgto in root.findall('.//infoPgto'):
                                s1210_data.append({'CPF': cpf, 'Competencia_Paga': infoPgto.find('perRef').text, 'Tipo': 'Pagamento_Check'})
                            for plan in root.findall('.//planSaude'):
                                s1210_data.append({
                                    'CPF': cpf, 'Tipo': 'Saude',
                                    'CNPJ': plan.find('cnpjOper').text,
                                    'ANS': plan.find('regANS').text,
                                    'Valor': float(plan.find('vlrSaudeTit').text)
                                })
                        except: pass
        progress.progress((i + 1) / len(uploaded_files))
    
    return pd.DataFrame(s1200_data), pd.DataFrame(s1210_data), mapa_nomes

# --- INTERFACE ---
uploaded_zips = st.file_uploader("📂 Faça upload dos ZIPs do eSocial", type="zip", accept_multiple_files=True)

# SELETOR DE ANO (NOVO!)
ano_selecionado = st.number_input("📅 Ano-Calendário (Ano Base)", min_value=2020, max_value=2030, value=2025, step=1)
st.caption(f"Exercício será: {ano_selecionado + 1}")

if uploaded_zips:
    if 'df_1200' not in st.session_state:
        st.info("Processando arquivos...")
        st.session_state.df_1200, st.session_state.df_1210, st.session_state.mapa_nomes = processar_arquivos(uploaded_zips)
    
    df_1200 = st.session_state.df_1200
    df_1210 = st.session_state.df_1210
    mapa_nomes = st.session_state.mapa_nomes
    
    if not df_1200.empty:
        # --- AUDITORIA ---
        cpfs = sorted(df_1200['CPF'].unique())
        pendencias_lista = []
        pagamentos_reais = set()
        if not df_1210.empty:
            df_checks = df_1210[df_1210['Tipo'] == 'Pagamento_Check']
            for _, row in df_checks.iterrows():
                pagamentos_reais.add((row['CPF'], row['Competencia_Paga']))
        
        for cpf in cpfs:
            comps_calc = df_1200[df_1200['CPF'] == cpf]['Competencia'].unique()
            for comp in comps_calc:
                # Se não achou pagamento E não é do ano seguinte (evita erro com Dezembro pago em Janeiro)
                # Na verdade, a regra simples é: Se tem S-1200, precisa ter S-1210 no ano calendário selecionado.
                if (cpf, comp) not in pagamentos_reais:
                    pendencias_lista.append({
                        "CPF": cpf, "Nome": mapa_nomes.get(cpf, f"CPF {cpf}"),
                        "Competencia Faltante": comp, "Data Pagamento (DD/MM/AAAA)": "", "IRRF Manual (R$)": 0.0
                    })
        
        df_manuais = pd.DataFrame()
        
        # --- PAINEL 1: CORREÇÃO ---
        tem_pendencias = len(pendencias_lista) > 0
        if tem_pendencias:
            with st.expander(f"⚠️ Correção de Pagamentos Faltantes ({len(pendencias_lista)} encontrados)", expanded=True):
                st.error("Alguns pagamentos não foram encontrados. Preencha a data para incluí-los.")
                df_pendencias = pd.DataFrame(pendencias_lista)
                editor_pendencias = st.data_editor(
                    df_pendencias,
                    column_config={
                        "CPF": st.column_config.TextColumn(disabled=True),
                        "Nome": st.column_config.TextColumn(disabled=True),
                        "Competencia Faltante": st.column_config.TextColumn(disabled=True),
                        "Data Pagamento (DD/MM/AAAA)": st.column_config.TextColumn("Data Pagamento", required=True),
                        "IRRF Manual (R$)": st.column_config.NumberColumn("IRRF Extra", format="R$ %.2f")
                    },
                    hide_index=True, width='stretch', key="editor_manual"
                )
                df_manuais = editor_pendencias[editor_pendencias["Data Pagamento (DD/MM/AAAA)"] != ""]
        else:
            st.success("✅ Auditoria OK! Todos os pagamentos encontrados.")

        # --- PAINEL 2: NOMES ---
        with st.expander("👥 Conferência e Edição de Nomes", expanded=False):
            df_nomes = pd.DataFrame(cpfs, columns=['CPF'])
            df_nomes['Nome'] = df_nomes['CPF'].apply(lambda x: mapa_nomes.get(x, f"FUNCIONÁRIO CPF {x}"))
            df_nomes_editado = st.data_editor(df_nomes, hide_index=True, width='stretch')
            mapa_nomes_final = dict(zip(df_nomes_editado['CPF'], df_nomes_editado['Nome']))

        # --- PAINEL 3: RUBRICAS ---
        with st.expander("📊 Totais por Rubrica (Para auxiliar no De/Para)", expanded=False):
            st.info("Consulte os totais para identificar códigos.")
            resumo_rubricas = df_1200.groupby('Rubrica').agg(Total=('Valor', 'sum'), Qtd=('Rubrica', 'count')).reset_index().sort_values('Total', ascending=False)
            resumo_rubricas['Total'] = resumo_rubricas['Total'].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(resumo_rubricas, width='stretch')

        # --- CONFIGURAÇÃO ---
        st.divider()
        st.subheader("Configuração Final")
        
        rubricas_unicas = sorted(df_1200['Rubrica'].unique())
        c1, c2 = st.columns(2)
        with c1:
            r_bruto = st.multiselect("Salário/Férias (Bruto)", rubricas_unicas)
            r_13_bruto = st.multiselect("13º Salário (Bruto)", rubricas_unicas)
        with c2:
            r_inss = st.multiselect("INSS Mensal", rubricas_unicas)
            r_inss_13 = st.multiselect("INSS s/ 13º", rubricas_unicas)
            r_irrf = st.multiselect("IRRF Mensal", rubricas_unicas)
            r_irrf_13 = st.multiselect("IRRF s/ 13º", rubricas_unicas)
            
        col_emp1, col_emp2 = st.columns([3,1])
        nome_emp = col_emp1.text_input("Nome da Empresa", "SUA EMPRESA LTDA")
        cnpj_emp = col_emp2.text_input("CNPJ", "00.000.000/0001-00")

        # --- CÁLCULO GERAL (ENGINE) ---
        def calcular_todos_funcionarios():
            resultados = []
            for cpf in cpfs:
                # 1. Filtro de dados
                itens = df_1200[df_1200['CPF'] == cpf].to_dict('records')
                saude = df_1210[(df_1210['CPF'] == cpf) & (df_1210['Tipo'] == 'Saude')].to_dict('records')
                
                # 2. Competências pagas (XML + Manual)
                comps_pagas_xml = set()
                if not df_1210.empty:
                    mask = (df_1210['CPF'] == cpf) & (df_1210['Tipo'] == 'Pagamento_Check')
                    comps_pagas_xml = set(df_1210[mask]['Competencia_Paga'].unique())
                
                comps_pagas_manual = set()
                irrf_manual_total = 0.0
                if not df_manuais.empty:
                    manual_cpf = df_manuais[df_manuais['CPF'] == cpf]
                    comps_pagas_manual = set(manual_cpf['Competencia Faltante'].unique())
                    irrf_manual_total = manual_cpf['IRRF Manual (R$)'].sum()
                
                todas_comps_pagas = comps_pagas_xml.union(comps_pagas_manual)
                itens_validos = [i for i in itens if i['Competencia'] in todas_comps_pagas or len(i['Competencia']) == 4]
                
                # 3. Somas
                def somar(rubricas): return sum(i['Valor'] for i in itens_validos if i['Rubrica'] in rubricas)
                
                v_bruto = somar(r_bruto)
                v_inss = somar(r_inss)
                v_irrf = somar(r_irrf) + irrf_manual_total
                v_13_bruto = somar(r_13_bruto)
                v_13_inss = somar(r_inss_13)
                v_13_irrf = somar(r_irrf_13)
                v_13_liq = v_13_bruto - v_13_inss
                
                # 4. Texto Saúde
                txt_saude = ""
                saude_dict = {}
                for s in saude:
                    key = (s['CNPJ'], s['ANS'])
                    if key not in saude_dict: saude_dict[key] = 0.0
                    saude_dict[key] += s['Valor']
                
                if saude_dict:
                    txt_saude += "DESPESAS MÉDICAS/ODONTOLÓGICAS:\n"
                    for (cnpj, ans), valor in saude_dict.items():
                        txt_saude += f"OPERADORA CNPJ: {cnpj} (Reg. ANS: {ans}) - VALOR ANUAL: R$ {fmt(valor)}\n"
                
                if not txt_saude: txt_saude = "Sem informações complementares."

                resultados.append({
                    'cpf': cpf,
                    'nome': mapa_nomes_final.get(cpf, f"CPF {cpf}"),
                    'calculados': {
                        'v_bruto': v_bruto, 'v_inss': v_inss, 'v_irrf': v_irrf,
                        'v_13_bruto': v_13_bruto, 'v_13_inss': v_13_inss, 'v_13_irrf': v_13_irrf,
                        'v_13_liq': v_13_liq, 'txt_saude': txt_saude
                    },
                    'cadastrais': {
                        'CPF': cpf, 'Nome': mapa_nomes_final.get(cpf, f"CPF {cpf}"),
                        'Empregador_Nome': nome_emp, 'Empregador_CNPJ': cnpj_emp
                    }
                })
            return resultados

        # --- BOTÕES DE EXPORTAÇÃO ---
        st.divider()
        col_btn_pdf, col_btn_excel = st.columns(2)
        
        with col_btn_pdf:
            if st.button("🚀 Gerar PDFs (ZIP)"):
                if not r_bruto:
                    st.warning("Selecione rubricas de Salário!")
                else:
                    dados = calcular_todos_funcionarios()
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as z_out:
                        my_bar = st.progress(0)
                        for idx, item in enumerate(dados):
                            pdf = gerar_pdf_final(item['calculados'], item['cadastrais'], str(ano_selecionado))
                            z_out.writestr(f"Informe_{item['nome']}.pdf", pdf.output(dest='S').encode('latin-1'))
                            my_bar.progress((idx + 1) / len(dados))
                    st.success("PDFs Gerados!")
                    st.download_button("📥 Baixar ZIP", zip_buffer.getvalue(), f"Informes_{ano_selecionado}.zip", "application/zip")

        with col_btn_excel:
            if st.button("📊 Baixar Relatório (Excel)"):
                if not r_bruto:
                    st.warning("Selecione rubricas de Salário!")
                else:
                    dados = calcular_todos_funcionarios()
                    lista_excel = []
                    for item in dados:
                        c = item['calculados']
                        lista_excel.append({
                            "CPF": item['cpf'], "Nome": item['nome'],
                            "Rend. Tributáveis": c['v_bruto'], "INSS Oficial": c['v_inss'], "IRRF": c['v_irrf'],
                            "13º Líquido": c['v_13_liq'], "13º Bruto": c['v_13_bruto'], "INSS 13º": c['v_13_inss'], "IRRF 13º": c['v_13_irrf'],
                            "Info Saúde": c['txt_saude'].replace('\n', ' | ')
                        })
                    
                    df_relatorio = pd.DataFrame(lista_excel)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_relatorio.to_excel(writer, index=False, sheet_name='Conferência')
                    st.success("Relatório Gerado!")
                    st.download_button("📥 Baixar Excel", output.getvalue(), "Relatorio_Conferencia.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Nenhum dado S-1200 encontrado.")