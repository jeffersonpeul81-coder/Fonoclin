# Sistema de Audiometria Ocupacional

Sistema web em Python (Streamlit) para cadastro de empresas e funcionários, registro de
audiometrias tonais ocupacionais, histórico por paciente e emissão do laudo em PDF com os
audiogramas da orelha direita e esquerda, dados da empresa, do funcionário e parecer.

## O que o sistema faz

- **Empresas**: cadastro com razão social, CNPJ, endereço, contato (RH/SESMT).
- **Funcionários**: nome, CPF, RG, nascimento, sexo, empresa, função, setor, admissão.
- **Audiometria**: data, tipo (admissional, periódico, retorno, mudança de riscos,
  demissional, monitoração pontual), repouso auditivo, meatoscopia OD/OE, audiômetro e
  calibração, anamnese, limiares de via aérea e óssea (com mascaramento e "sem resposta")
  de 250 a 8.000 Hz, logoaudiometria (LRF, IPRF, LDV) e parecer.
- **Análise automática (auxiliar)** pela NR-7, Anexo II: limites aceitáveis, sugestivo ou
  não sugestivo de PAINPSE, médias 0,5/1/2 kHz e 3/4/6 kHz, grau (Lloyd & Kaplan) e
  comparação com o exame de referência (desencadeamento/agravamento). A sugestão só vai
  para o parecer se a Cris clicar em "Usar sugestão" — e pode ser editada livremente.
- **Histórico**: todos os exames do funcionário, gráfico de evolução, reemissão do PDF,
  edição e exclusão.
- **Laudo PDF**: cabeçalho com logotipo e dados da profissional, audiogramas com a
  simbologia padrão (OD vermelho O/</[, OE azul X/>/]), tabela de limiares, logoaudiometria,
  parecer e campos de assinatura (aceita assinatura digitalizada).
- **Backup** completo em JSON (menu Configurações).

## Arquivos

| Arquivo | Função |
|---|---|
| `app.py` | Telas do sistema |
| `db.py` | Banco de dados (tabelas e consultas) |
| `classificacao.py` | Critérios NR-7 / Lloyd & Kaplan |
| `audiograma.py` | Desenho dos audiogramas |
| `relatorio.py` | Geração do laudo em PDF |

---

## Colocando no ar (gratuito) — passo a passo

Arquitetura: **Neon** (banco PostgreSQL gratuito, 1 GB — milhares de exames) +
**Streamlit Community Cloud** (hospedagem gratuita) + **GitHub** (guarda o código).

### 1. Banco de dados — Neon
1. Acesse https://neon.com e crie uma conta (pode entrar com o Google).
2. Crie um projeto (ex.: `audiometria`), região **AWS São Paulo (sa-east-1)**.
3. Clique em **Connect** e copie a *connection string* (começa com `postgresql://` e
   termina com `?sslmode=require`).

As tabelas são criadas automaticamente no primeiro acesso ao sistema.

### 2. Código — GitHub
1. Crie uma conta em https://github.com.
2. Crie um repositório **privado** (ex.: `audiometria-cris`).
3. Envie os arquivos desta pasta (botão *Add file > Upload files*), **incluindo a pasta
   `.streamlit` só com o arquivo `secrets.toml.exemplo`** — nunca envie senhas ao GitHub.

### 3. Hospedagem — Streamlit Community Cloud
1. Acesse https://share.streamlit.io e entre com a conta do GitHub.
2. **Create app > Deploy a public app from GitHub** → escolha o repositório, branch `main`,
   arquivo `app.py`. Em *App URL* escolha um endereço (ex.: `audiometria-cris`).
3. Em **Advanced settings > Secrets**, cole:
   ```toml
   DATABASE_URL = "cole-aqui-a-connection-string-do-neon"
   APP_PASSWORD = "uma-senha-forte"
   ```
4. Clique em **Deploy**. Em ~2 minutos o sistema estará em
   `https://audiometria-cris.streamlit.app`, acessível de qualquer computador ou celular.

### 4. Primeiro uso
1. Entre com a senha.
2. **Configurações**: preencha nome, CRFa, clínica, contatos, audiômetro e data de
   calibração; envie o logotipo (e a assinatura, se quiser).
3. **Empresas**: cadastre as empresas atendidas.
4. **Nova audiometria**: escolha a empresa e o funcionário (ou cadastre na hora), preencha
   e salve. O botão **Baixar laudo (PDF)** aparece logo após salvar.

### Observações importantes
- **Hibernação**: o Streamlit gratuito "dorme" após 12 horas sem uso; o primeiro acesso do
  dia pode levar ~30 segundos para acordar. O Neon também suspende o banco quando parado e
  acorda sozinho em poucos segundos. Nenhum dado é perdido.
- **Privacidade (LGPD)**: são dados de saúde (dados sensíveis). O app é protegido por senha
  e o banco exige conexão criptografada (SSL). Use senha forte, não compartilhe o link com
  a senha e faça o backup mensal pelo menu Configurações.
- **Plano gratuito do Streamlit**: permite 1 app privado; o app aqui é protegido pela senha
  do próprio sistema, então pode ser publicado como "público" sem expor dados.
- **Testar no computador** (opcional): `pip install -r requirements.txt` e
  `streamlit run app.py`. Sem `DATABASE_URL` ele usa um banco local `audiometria_local.db`.

### Responsabilidade técnica
A classificação automática é apenas um apoio. A interpretação e o parecer final são de
responsabilidade da fonoaudióloga, conforme a NR-7 e as resoluções do CFFa.
