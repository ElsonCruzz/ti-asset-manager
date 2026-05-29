import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="TI Asset Manager - MSP",
    page_icon="🖥️",
    layout="wide"
)

# --- CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"Erro de configuração: {e} não encontrado in st.secrets.")
        st.stop()

supabase = init_connection()

# --- FUNÇÕES DE BANCO DE DADOS ---

def listar_empresas() -> pd.DataFrame:
    try:
        response = supabase.table("empresas").select("id, nome_fantasia, status_contrato").order("nome_fantasia").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao carregar empresas: {e}")
        return pd.DataFrame()

def listar_locais(empresa_id: str) -> pd.DataFrame:
    try:
        response = supabase.table("locais").select("id, nome").eq("empresa_id", empresa_id).order("nome").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao carregar locais: {e}")
        return pd.DataFrame()

def carregar_dashboard_dados(empresa_id: str = None) -> pd.DataFrame:
    try:
        query = supabase.table("ativos").select(
            "id, tipo, fabricante, modelo, numero_serie, status, data_compra, fim_garantia, observacoes, local_id, locais(nome)"
        )
        if empresa_id:
            query = query.eq("empresa_id", empresa_id)
            
        response = query.execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty and "locais" in df.columns:
            df["local"] = df["locais"].apply(lambda x: x["nome"] if isinstance(x, dict) else "Não Alocado")
            # Mantemos o "locais" oculto mas preservamos a estrutura se necessário
        return df
    except Exception as e:
        st.error(f"Erro ao carregar ativos: {e}")
        return pd.DataFrame()

# NOVA FUNÇÃO: Atualizar dados do ativo no Supabase
def atualizar_ativo(ativo_id: str, dados_atualizados: dict) -> bool:
    try:
        supabase.table("ativos").update(dados_atualizados).eq("id", ativo_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar equipamento: {e}")
        return False

# --- NAVEGAÇÃO PRINCIPAL (SIDEBAR AMARRAÇÃO NOVA) ---
st.sidebar.title("🛠️ TI Asset Navigation")
menu = st.sidebar.radio(
    "Navegar para:", 
    ["📊 Dashboard Geral", "🏢 Cadastrar Cliente/Local", "🖥️ Cadastrar Equipamento", "✏️ Editar / Atualizar Equipamento"]
)

st.sidebar.markdown("---")

df_empresas = listar_empresas()
df_empresas_ativas = df_empresas[df_empresas["status_contrato"] == "Ativo"] if not df_empresas.empty else pd.DataFrame()

empresa_selecionada_id = None
opcao_filtro = "Todos"

if menu == "📊 Dashboard Geral" and not df_empresas_ativas.empty:
    st.sidebar.subheader("Filtro do Dashboard")
    opcoes_empresas = ["Todos os Contratos"] + df_empresas_ativas["nome_fantasia"].tolist()
    opcao_filtro = st.sidebar.selectbox("Selecione o Cliente:", opcoes_empresas)
    
    if opcao_filtro != "Todos os Contratos":
        empresa_selecionada_id = df_empresas_ativas[df_empresas_ativas["nome_fantasia"] == opcao_filtro]["id"].values[0]

# --- MENU 1: DASHBOARD GERAL ---
if menu == "📊 Dashboard Geral":
    st.title("📊 Dashboard Geral de Infraestrutura")
    st.caption(f"Visualizando escopo: **{opcao_filtro}**")
    st.markdown("---")
    
    df_ativos = carregar_dashboard_dados(empresa_selecionada_id)
    
    if df_ativos.empty:
        st.info("Nenhum equipamento cadastrado neste escopo. Vá até a aba de cadastros para começar!")
    else:
        st.markdown("### 🔍 Filtros Avançados")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            tipos_disponiveis = sorted(df_ativos["tipo"].unique().tolist())
            tipos_selecionados = st.multiselect("Filtrar por Tipo de Equipamento:", options=tipos_disponiveis, placeholder="Todos os tipos")
            
        with col_f2:
            status_disponiveis = sorted(df_ativos["status"].unique().tolist())
            status_selecionados = st.multiselect("Filtrar por Status Operacional:", options=status_disponiveis, placeholder="Todos os status")
        
        df_filtrado = df_ativos.copy()
        
        if tipos_selecionados:
            df_filtrado = df_filtrado[df_filtrado["tipo"].isin(tipos_selecionados)]
        if status_selecionados:
            df_filtrado = df_filtrado[df_filtrado["status"].isin(status_selecionados)]
            
        st.markdown("---")
        
        if df_filtrado.empty:
            st.warning("Nenhum ativo corresponde aos filtros selecionados acima.")
        else:
            df_filtrado["fim_garantia"] = pd.to_datetime(df_filtrado["fim_garantia"])
            df_filtrado["data_compra"] = pd.to_datetime(df_filtrado["data_compra"])
            hoje = pd.Timestamp.now().normalize()
            
            total_ativos = len(df_filtrado)
            em_producao = len(df_filtrado[df_filtrado["status"] == "Em Produção"])
            garantias_vencidas = len(df_filtrado[df_filtrado["fim_garantia"] < hoje])
            
            limite_obsolescencia = hoje - pd.DateOffset(years=5)
            equipamentos_antigos = len(df_filtrado[df_filtrado["data_compra"] < limite_obsolescencia])
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ativos Filtrados", total_ativos)
            col2.metric("Em Produção", em_producao)
            col3.metric("🚨 Garantias Vencidas", garantias_vencidas, delta=f"{garantias_vencidas} pendente(s)" if garantias_vencidas > 0 else None, delta_color="inverse")
            col4.metric("⚠️ Ciclo Crítico (>5 anos)", equipamentos_antigos, delta="Substituição Recomendada" if equipamentos_antigos > 0 else None, delta_color="off")
            
            st.markdown("---")
            
            cg1, cg2 = st.columns(2)
            with cg1:
                st.write("#### Equipamentos por Tipo")
                st.bar_chart(df_filtrado["tipo"].value_counts())
            with cg2:
                st.write("#### Status dos Ativos")
                st.bar_chart(df_filtrado["status"].value_counts())
                
            st.markdown("---")
            st.write("#### 📋 Inventário Filtrado")
            df_exibicao = df_filtrado.copy()
            df_exibicao["fim_garantia"] = df_exibicao["fim_garantia"].dt.strftime('%d/%m/%Y')
            df_exibicao["data_compra"] = df_exibicao["data_compra"].dt.strftime('%d/%m/%Y')
            
            # Remove colunas internas de IDs e JSONs para limpar o visual
            colunas_exibir = [c for c in df_exibicao.columns if c not in ["locais", "local_id"]]
            st.dataframe(df_exibicao[colunas_exibir], use_container_width=True)

# --- MENU 2: CADASTRO DE CLIENTE E LOCAL ---
elif menu == "🏢 Cadastrar Cliente/Local":
    st.title("🏢 Gestão de Contratos e Locais")
    aba_empresa, aba_local = st.tabs(["➕ Nova Empresa/Contrato", "📍 Novo Local/Site"])
    
    with aba_empresa:
        st.subheader("Cadastrar Novo Cliente Contratante")
        with st.form("form_empresa", clear_on_submit=True):
            nome_fantasia = st.text_input("Nome Fantasia:*")
            razao_social = st.text_input("Razão Social:")
            cnpj = st.text_input("CNPJ:")
            status = st.selectbox("Status do Contrato:", ["Ativo", "Inativo", "Suspenso"])
            
            if st.form_submit_button("Salvar Empresa"):
                if nome_fantasia.strip():
                    try:
                        dados = {"nome_fantasia": nome_fantasia.strip(), "razao_social": razao_social.strip(), "cnpj": cnpj.strip(), "status_contrato": status}
                        supabase.table("empresas").insert(dados).execute()
                        st.success(f"Empresa '{nome_fantasia}' cadastrada com sucesso! Altere o menu para atualizar as listas.")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.warning("O campo Nome Fantasia é obrigatório.")
                    
    with aba_local:
        st.subheader("Cadastrar Local Físico")
        if df_empresas.empty:
            st.warning("Cadastre uma empresa primeiro antes de criar um local.")
        else:
            with st.form("form_local", clear_on_submit=True):
                empresa_nome = st.selectbox("Vincular à Empresa:", df_empresas["nome_fantasia"].tolist())
                emp_id = df_empresas[df_empresas["nome_fantasia"] == empresa_nome]["id"].values[0]
                nome_local = st.text_input("Nome do Local:* (Ex: DataCenter 1, CPD)")
                descricao_local = st.text_area("Descrição/Observações:")
                
                if st.form_submit_button("Salvar Local"):
                    if nome_local.strip():
                        try:
                            dados = {"empresa_id": emp_id, "nome": nome_local.strip(), "descricao": descricao_local.strip()}
                            supabase.table("locais").insert(dados).execute()
                            st.success(f"Local '{nome_local}' vinculado com sucesso!")
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                    else:
                        st.warning("O campo Nome do Local é obrigatório.")

# --- MENU 3: CADASTRO DE EQUIPAMENTO ---
elif menu == "🖥️ Cadastrar Equipamento":
    st.title("🖥️ Cadastro de Ativos de Infraestrutura")
    if df_empresas.empty:
        st.warning("Você precisa cadastrar uma Empresa e um Local antes de inserir equipamentos.")
    else:
        col_emp, col_loc = st.columns(2)
        with col_emp:
            emp_escolhida = st.selectbox("Equipamento pertence à qual cliente?", df_empresas["nome_fantasia"].tolist())
            id_da_empresa = df_empresas[df_empresas["nome_fantasia"] == emp_escolhida]["id"].values[0]
        
        df_locais_filtrados = listar_locais(id_da_empresa)
        with col_loc:
            if df_locais_filtrados.empty:
                st.error("⚠️ Este cliente não tem nenhum local cadastrado.")
                local_escolhido_id = None
            else:
                local_escolhido_nome = st.selectbox("Em qual local físico ele está?", df_locais_filtrados["nome"].tolist())
                local_escolhido_id = df_locais_filtrados[df_locais_filtrados["nome"] == local_escolhido_nome]["id"].values[0]

        if local_escolhido_id:
            st.markdown("---")
            with st.form("form_ativo", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                tipo = c1.selectbox("Tipo de Ativo:*", ["Servidor", "Switch", "Firewall", "Roteador", "Storage", "Nobreak", "Acess Point", "Outro"])
                fabricante = c2.text_input("Fabricante:*")
                modelo = c3.text_input("Modelo:*")
                
                c4, c5 = st.columns(2)
                num_serie = c4.text_input("Número de Série / Service Tag:*")
                patrimonio = c5.text_input("Patrimônio Interno (Opcional):")
                
                c6, c7, c8 = st.columns(3)
                data_compra = c6.date_input("Data de Compra:", value=None)
                fim_garantia = c7.date_input("Fim da Garantia:", value=None)
                status_ativo = c8.selectbox("Status Operacional:", ["Em Produção", "Estoque/Backup", "Manutenção", "Desativado"])
                
                st.subheader("🌐 Configuração de Rede (Opcional)")
                c9, c10, c11 = st.columns(3)
                ip_local = c9.text_input("IP Local")
                mac = c10.text_input("Endereço MAC")
                vlan = c11.number_input("VLAN ID", min_value=0, max_value=4096, value=0)
                
                obs = st.text_area("Observações Técnicas:")
                
                if st.form_submit_button("Cadastrar Equipamento"):
                    if fabricante.strip() and modelo.strip() and num_serie.strip():
                        try:
                            dados_ativo = {
                                "empresa_id": id_da_empresa, "local_id": local_escolhido_id,
                                "tipo": tipo, "fabricante": fabricante.strip(), "modelo": modelo.strip(),
                                "numero_serie": num_serie.strip(), "patrimonio_interno": patrimonio.strip(),
                                "data_compra": str(data_compra) if data_compra else None,
                                "fim_garantia": str(fim_garantia) if fim_garantia else None,
                                "status": status_ativo, "observacoes": obs.strip()
                            }
                            res_ativo = supabase.table("ativos").insert(dados_ativo).execute()
                            id_ativo_criado = res_ativo.data[0]["id"]
                            
                            if ip_local.strip() or mac.strip() or vlan > 0:
                                dados_rede = {
                                    "ativo_id": id_ativo_criado, "ip_local": ip_local.strip(),
                                    "mac_address": mac.strip(), "vlan_id": vlan if vlan > 0 else None
                                }
                                supabase.table("redes").insert(dados_rede).execute()
                                
                            st.success(f"Equipamento {tipo} cadastrado com sucesso!")
                        except Exception as e:
                            st.error(f"Erro ao inserir ativo: {e}")
                    else:
                        st.warning("Por favor, preencha todos os campos obrigatórios (*).")

# --- NOVO MENU 4: EDICÃO E ALTERAÇÃO DE STATUS ---
elif menu == "✏️ Editar / Atualizar Equipamento":
    st.title("✏️ Manutenção e Edição de Ativos")
    st.caption("Altere a localização, o status operacional ou insira logs técnicos em um equipamento existente.")
    st.markdown("---")
    
    if df_empresas.empty:
        st.warning("Nenhum cliente cadastrado.")
    else:
        # 1. Seleciona a Empresa
        emp_edicao = st.selectbox("Selecione o Cliente do ativo:", df_empresas["nome_fantasia"].tolist())
        id_emp_edicao = df_empresas[df_empresas["nome_fantasia"] == emp_edicao]["id"].values[0]
        
        # Carrega os ativos específicos desse cliente
        df_ativos_edicao = carregar_dashboard_dados(id_emp_edicao)
        
        if df_ativos_edicao.empty:
            st.info("Este cliente não possui nenhum equipamento cadastrado para edição.")
        else:
            # Cria uma string legível para o dropdown combinar Tipo + Fabricante + Série
            df_ativos_edicao["label_selectbox"] = df_ativos_edicao.apply(
                lambda r: f"{r['tipo']} - {r['fabricante']} {r['modelo']} (S/N: {r['numero_serie']})", axis=1
            )
            
            ativo_selecionado_label = st.selectbox("Selecione o Equipamento que deseja editar:", df_ativos_edicao["label_selectbox"].tolist())
            
            # Extrai a linha do ativo escolhido
            linha_ativo = df_ativos_edicao[df_ativos_edicao["label_selectbox"] == ativo_selecionado_label].iloc[0]
            ativo_id = linha_ativo["id"]
            
            st.markdown("### Formulário de Atualização")
            
            # Carrega locais do cliente para permitir mudar o equipamento de sala/filial se necessário
            df_locais_emp = listar_locais(id_emp_edicao)
            
            with st.form("form_edicao"):
                col_e1, col_e2 = st.columns(2)
                
                # Input de Status com o valor atual pré-selecionado
                lista_status = ["Em Produção", "Estoque/Backup", "Manutenção", "Desativado"]
                index_status = lista_status.index(linha_ativo["status"]) if linha_ativo["status"] in lista_status else 0
                novo_status = col_e1.selectbox("Alterar Status Operacional:", lista_status, index=index_status)
                
                # Input de Local com o valor atual pré-selecionado
                if not df_locais_emp.empty:
                    nomes_locais = df_locais_emp["nome"].tolist()
                    # Tenta descobrir o index do local atual do ativo
                    nome_local_atual = linha_ativo["local"]
                    index_local = nomes_locais.index(nome_local_atual) if nome_local_atual in nomes_locais else 0
                    novo_local_nome = col_e2.selectbox("Mover para o Local Físico:", nomes_locais, index=index_local)
                    novo_local_id = df_locais_emp[df_locais_emp["nome"] == novo_local_nome]["id"].values[0]
                else:
                    st.warning("Cadastre locais para esta empresa para poder alterar a posição do ativo.")
                    novo_local_id = linha_ativo["local_id"]
                
                # Campo de observações técnica para logs de manutenção
                obs_atual = linha_ativo["observacoes"] if pd.notna(linha_ativo["observacoes"]) else ""
                novas_obs = st.text_area("Histórico Técnico / Observações:", value=obs_atual, placeholder="Ex: Efetuado update de firmware da controladora em 28/05/2026 por João.")
                
                if st.form_submit_button("Gravar Alterações"):
                    dados_update = {
                        "status": novo_status,
                        "local_id": novo_local_id,
                        "observacoes": novas_obs.strip()
                    }
                    
                    if atualizar_ativo(ativo_id, dados_update):
                        st.success("🎉 Equipamento atualizado com sucesso no banco de dados!")
                        st.info("💡 Mude para a aba 'Dashboard Geral' para ver as alterações aplicadas.")