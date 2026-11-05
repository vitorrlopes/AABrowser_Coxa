# MANUTÊ — Missão 1: diagnóstico, alternativas e recomendação

Data: 2026-11-05 · Papel: ARQUITETO + ENGENHEIRO · Status: proposta para decisão

> **Sobre a confiabilidade deste documento.** Nada aqui foi medido no Galaxy
> S22+; os números de hardware e de desempenho são estimativas a verificar no
> Experimento A. As informações de políticas e preços de fornecedores mudam
> com frequência. Onde não consegui confirmar algo numa fonte primária, está
> marcado como **[verificar]**. A seção 9 lista as fontes consultadas.

---

## 1. Diagnóstico do ambiente

### 1.1 Este ambiente de trabalho (contêiner na nuvem)

| Item | Situação | Consequência |
|---|---|---|
| Repositório | `AABrowser_Coxa` é um **fork de um navegador para Android Auto (GPLv3)**, sem relação com o MANUTÊ | ver questionamento Q1 |
| Hardware | 4 vCPUs x86_64, 16 GB RAM, sem GPU | não representa o celular; serve só para ferramentas |
| Rede | Hugging Face **bloqueado** (proxy 403); `developers.google.com` e `developers.openai.com` sem resolução | não consigo baixar modelos nem ler parte da documentação oficial daqui |
| Android | sem `adb`, sem emulador, sem aparelho | **toda medição real precisa ser feita por você no S22+** |
| Ferramentas | Python 3.13, cmake, gcc, Node 22, Java | suficiente para o harness de experimentos |

Conclusão: daqui consigo **projetar, escrever e testar o ferramental**; os
experimentos A/B/C precisam rodar no seu aparelho (e no seu PC).

### 1.2 Galaxy S22+ — o que precisa ser identificado antes de escolher modelos

| Item | O que sei (com incerteza) | Como confirmar |
|---|---|---|
| Variante | Existem pelo menos duas famílias de SoC: **Exynos 2200** (GPU Xclipse 920, ex.: SM-S906B) e **Snapdragon 8 Gen 1** (GPU Adreno 730, ex.: SM-S906U/N/E). Acredito que a variante vendida no Brasil foi Exynos, mas **não tenho certeza** | `ro.board.platform`: `taro` ⇒ Snapdragon 8 Gen 1; `s5e9925` ⇒ Exynos 2200 (`device_info.sh`) |
| RAM | 8 GB LPDDR5 (acredito que todas as variantes) | `MemTotal` em `/proc/meminfo` |
| Android | lançado com Android 12; acredito que recebeu até 4 atualizações de sistema (até Android 16 / One UI 8) **[verificar]** | `ro.build.version.release` |
| Térmica | os dois SoCs dessa geração ficaram conhecidos por throttling sob carga sustentada | teste sustentado de 10 min (Protocolo §2.5) |
| Aceleração | CPU ARMv9 com NEON/dotprod (suportado pelo llama.cpp); GPU Vulkan; NPU existe, mas **acredito** que os runtimes atuais miram NPUs de gerações mais novas | testar CPU primeiro; GPU como segundo passo |

**Orçamento de memória (estimativa).** Dos 8 GB, Android + One UI + serviços
costumam ocupar algo em torno de 3–4 GB; um app em primeiro plano pode usar com
alguma segurança ~2,5–3,5 GB antes de o *Low Memory Killer* agir **[medir]**.
Com Q4 (~0,55–0,6 byte/parâmetro) mais cache KV:

| Faixa | Pesos Q4 aprox. | Expectativa no S22+ |
|---|---|---|
| 0,5–1B | 0,4–0,8 GB | confortável |
| 2B | 1,1–1,6 GB | confortável |
| 3–4B | 2,0–2,5 GB | viável com contexto curto (2–4k) |
| 7–8B | 4,7–5 GB | **provavelmente instável** (morte por LMK, swap/zram, aquecimento) |

Velocidade: não encontrei benchmark confiável de llama.cpp com Qwen3/Gemma
especificamente num Snapdragon 8 Gen 1 ou Exynos 2200. **Não vou chutar
tokens/s** — é exatamente o que o Experimento A mede.

---

## 2. Questionamentos às premissas (o ARQUITETO discordando)

**Q1 — Repositório errado.** O MANUTÊ não deve morar dentro de um fork GPLv3 de
navegador para Android Auto: mistura histórico, licença e CI de dois produtos.
Coloquei o material em `manute/` só porque esta sessão só tem acesso a este
repositório. **Recomendo criar um repositório próprio** e mover a pasta
(é autocontida). Também vale decidir a licença do MANUTÊ conscientemente.

**Q2 — "OAuth 2.0 com PKCE quando suportado" quase não se aplica aos
provedores listados.** Para Anthropic, a documentação atual diz que
desenvolvedores de produtos de terceiros devem usar **chave de API** (Console
ou provedor de nuvem) e que a Anthropic **não permite** oferecer login Claude.ai
em apps próprios nem rotear requisições por credenciais Free/Pro/Max. Para
OpenAI, não encontrei OAuth de API para apps de terceiros **[verificar]**. Na
prática o MANUTÊ CONNECT será, nesta fase, **BYOK (traga sua própria chave)**
com armazenamento seguro; OAuth+PKCE fica para Google/Vertex e futuros
provedores que ofereçam o fluxo.

**Q3 — "Usar minha assinatura Claude/ChatGPT dentro do MANUTÊ" não é um caminho
legítimo para a Anthropic.** Você mesmo antecipou isso no documento; confirmo
com a fonte: assinatura ≠ acesso à API. Para o Codex CLI, a OpenAI oferece login
com ChatGPT **no próprio CLI**, mas recomenda chave de API para uso
programático; não encontrei autorização para apps de terceiros reutilizarem esse
login **[verificar termos da OpenAI]**.

**Q4 — Claude Code e Codex CLI não cabem no Android nem no CORE.** São agentes
de desktop/servidor com execução de código e acesso a sistema de arquivos. O
uso correto é tratá-los como **ferramentas externas opcionais no desktop**: o
MANUTÊ prepara a tarefa, o usuário executa o binário **oficial e não
modificado**, autenticado **por ele mesmo**, e o MANUTÊ lê o resultado
(ex.: diff, relatório). Para um uso pessoal isso é compatível com o que a
documentação descreve; **distribuir isso como recurso de produto** exige
revisão dos termos comerciais antes.

**Q5 — Expectativa realista dos modelos locais.** Modelos de 1–4B **não** vão
entregar o papel de ARQUITETO com qualidade de "arquitetura corporativa". O
papel local realista é: funcionar offline, triagem e roteamento, resumo,
rascunhos, perguntas de esclarecimento e privacidade. O Experimento C existe para
**medir essa distância**, não para presumir.

**Q6 — 7–8B no S22+.** Recomendo não investir tempo de engenharia nessa faixa
além de um único teste de viabilidade.

**Q7 — Escopo do primeiro passo.** A lista de componentes (CORE, Router,
Memória, Connect, 4 interfaces, agentes) é grande para um projeto pessoal. A
proposta abaixo entrega os 6 critérios de sucesso com **um CLI + uma biblioteca
CORE**, sem backend, sem app Android ainda.

---

## 3. Alternativas e comparativo técnico

### 3.1 Runtimes de inferência local no Android

| Runtime | Pontos fortes | Pontos fracos / riscos | Atrito para a PoC |
|---|---|---|---|
| **llama.cpp** (GGUF) | maior cobertura de modelos e quantizações; CPU ARM muito otimizada; `llama-server` compatível com o formato de chat da OpenAI; licença MIT; compila no Termux | backends de GPU no Android (Vulkan/OpenCL) com suporte desigual por GPU — em Adreno 730/Xclipse 920 **[verificar]**; integração no APK via JNI exige NDK | **baixo** (Termux) |
| **LiteRT-LM** (Google) | API Kotlin; backends CPU/GPU/NPU; formato `.litertlm`; suporte oficial a Gemma, e lista também Llama, Phi-4 e Qwen; app de demonstração (AI Edge Gallery) | catálogo curado (menos modelos que GGUF); NPU focada em aparelhos novos; benchmarks oficiais publicados para aparelhos novos, não para o S22+ | **muito baixo** (app pronto) |
| **MLC LLM** | GPU via Vulkan/OpenCL | precisa compilar cada modelo; cadeia de build mais pesada | alto |
| **ONNX Runtime GenAI** | já instalado neste contêiner; bom com Phi | menos foco em LLM móvel; ecossistema de modelos menor | médio |
| **ExecuTorch** (Meta) | backends de NPU de fabricantes | exportação de modelo complexa | alto |

**Recomendação:** medir com **LiteRT-LM (via AI Edge Gallery)** e **llama.cpp
(via Termux)**. Os dois juntos cobrem "Google curado com GPU" × "catálogo
amplo em CPU" com quase nenhum código. A escolha para o APK fica para depois dos
números (decisão adiada de propósito).

### 3.2 Modelos candidatos (verificar sempre se há geração mais nova)

| Família | Tamanhos relevantes | Licença (verificar a versão) | Observação |
|---|---|---|---|
| Qwen3 | 0.6B, 1.7B, 4B, 8B | Apache 2.0 | bom em código para o tamanho; modo de raciocínio liga/desliga |
| Gemma (3 / 3n / 4) | 1B, E2B, E4B | termos próprios da Gemma | caminho mais otimizado no LiteRT-LM; a documentação lista Gemma4 E2B/E4B |
| Phi-4-mini | 3,8B | MIT | bom raciocínio para o tamanho |
| Llama 3.2 | 1B, 3B | licença comunitária da Llama | referência amplamente usada |

### 3.3 Autenticação dos provedores

| Provedor | Mecanismo para app de terceiros | Assinatura serve? | Observações |
|---|---|---|---|
| Anthropic (API) | chave de API do Console, ou credencial de Bedrock/Vertex/Foundry | **Não** — proibido rotear por planos Free/Pro/Max e coletar credenciais Claude.ai | uso cobrado por token |
| Claude Code | binário oficial **não modificado**; o usuário faz login ou usa a própria chave | só pelo próprio usuário, no binário oficial | não tratar como API HTTP; desktop |
| OpenAI (API) | chave de API | Não **[verificar termos]** | |
| Codex CLI | login ChatGPT ou chave de API, **no CLI oficial**; chave recomendada para automação | só no CLI oficial **[verificar]** | desktop |
| Google Gemini API | chave do AI Studio | não se aplica | no nível gratuito, os dados podem ser usados para melhorar produtos **[verificar termos atuais]** |
| Vertex AI | OAuth 2.0 / conta de serviço do Google Cloud | não se aplica | único caso em que OAuth+PKCE faz sentido agora |

### 3.4 Armazenamento de credenciais

| Opção | Avaliação |
|---|---|
| Chave embutida no APK | **proibido** (extraível por engenharia reversa) |
| `EncryptedSharedPreferences` (Jetpack Security) | a biblioteca foi descontinuada **[verificar status]**; evitar em código novo |
| **Android Keystore + AES-GCM** (chave não exportável) cifrando um DataStore | **recomendado** para BYOK no aparelho |
| Desktop | chaveiro do sistema operacional (Keychain / Secret Service / Credential Manager) |
| Backend intermediário | só se houver múltiplos usuários ou necessidade de ocultar uma chave da empresa; **desnecessário agora** e aumenta custo, superfície de ataque e responsabilidade sobre dados |

---

## 4. Arquitetura mínima proposta

Princípio: **um monólito modular** com uma única porta de abstração onde a
independência de fornecedor exige (o motor de IA). Sem microsserviços, sem
banco vetorial, sem backend.

```
 Interfaces           CLI (agora)  ·  Android/Compose (depois)  ·  API local (depois)
                                         │
 MANUTÊ CORE (biblioteca)  ┌─────────────┴──────────────────────────────────┐
                           │ Sessão/Contexto → monta o prompt a partir da   │
                           │                   memória + histórico           │
                           │ Policy           → permissões: local-only?      │
                           │                   nuvem permitida? limite de $  │
                           │ Router (regras)  → modo do usuário + online? +  │
                           │                   tipo de tarefa                │
                           │ Memória (SQLite + FTS5) · Log de auditoria      │
                           └─────────────┬──────────────────────────────────┘
                                         │ porta Engine (uma interface)
       ┌───────────────┬─────────────────┼──────────────────┬──────────────┐
  LocalEngine     AnthropicEngine   OpenAIEngine      GeminiEngine    (novos)
  llama.cpp /     SDK oficial       SDK oficial       SDK oficial
  LiteRT-LM
                                         │
 MANUTÊ CONNECT   cofre de credenciais (Keystore / chaveiro do SO) · testar · remover
 Ferramentas externas (só desktop, opcional): Claude Code / Codex CLI oficiais
```

### 4.1 A porta `Engine` (o contrato que permite trocar o motor)

```text
Engine.generate(messages, limits) -> Generation{text, usage, timings, finish_reason}
Engine.capabilities -> {local: bool, max_context, custo_por_token?, ...}
```

O harness em `experiments/bench.py` já usa essa ideia na forma mínima
(`Engine` + `OpenAICompatibleEngine` + testes com um motor falso), o que
demonstra o critério de sucesso 5 em pequena escala.

### 4.2 Memória (independente do modelo, sem RAG indiscriminado)

Uma tabela de **registros estruturados**, não um depósito de embeddings:

```text
record(id, project_id, kind ∈ {requisito, decisão, preferência, fato, implementação},
       content, source, confidence, version, supersedes_id, created_at, deleted_at)
audit_log(id, at, actor, action, record_id, engine, cost)
```

- Versionamento por `supersedes_id`; exclusão lógica + rotina de expurgo real
  (para atender exclusão de verdade).
- Consulta por projeto/tipo + busca textual FTS5. Embeddings **só** se a busca
  textual se mostrar insuficiente nas medições.
- `source` e `confidence` respondem à exigência de não confiar cegamente em
  documentos internos.

### 4.3 Router (versão 1 = regras, sem aprendizado)

1. Se o modo é *somente local* ou não há rede → `LocalEngine`.
2. Se o modo é *provedor manual* → o escolhido (se a Policy permitir).
3. *Automático*: tarefa marcada como `simples` → local; `arquitetura`/`código`
   → nuvem **se** permitida e dentro do limite de gasto; revisão → um motor
   diferente do que gerou.
4. Toda chamada externa passa pela Policy e vai para o `audit_log`.

Um roteador aprendido só se justifica com dados de uso reais — não agora.

### 4.4 Linguagem

- **Ferramental de experimento:** Python só com a biblioteca padrão (roda no
  Termux sem `pip`). Já entregue.
- **CORE de produto:** recomendo **Kotlin** (Android nativo + JVM no desktop;
  Kotlin Multiplatform se for preciso compartilhar). Evita manter dois CORE em
  linguagens diferentes. **Decisão adiada para depois dos Experimentos A–C**,
  porque se nenhum modelo local for útil, o desenho do app muda.

---

## 5. Riscos

| # | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | Modelos locais úteis só para tarefas triviais | alta | alto | Experimento C mede antes de investir; local como "modo offline", não como cérebro principal |
| R2 | Throttling térmico derruba a velocidade sustentada | alta | médio | teste de 10 min; respostas curtas no local |
| R3 | LMK mata o processo com modelos ≥ 4B | média | médio | medir RSS; contexto curto; ficar em ≤ 4B |
| R4 | Mudança de termos dos fornecedores (já ocorreu na Anthropic em 2026) | média | alto | só integrações oficiais; Connect isolado; revisar termos a cada versão |
| R5 | Vazamento de chave de API do usuário | baixa | alto | Keystore, nunca logar segredos, limite de gasto no console do provedor, botão "remover" |
| R6 | Execução de código gerado por modelo | média | alto | sandbox descartável; nunca executar automaticamente sem aprovação |
| R7 | Escopo grande demais para um projeto pessoal | alta | alto | plano incremental com critérios de saída por fase |
| R8 | Licenças de modelos (Gemma, Llama) com restrições | baixa | médio | registrar licença de cada modelo usado; preferir Apache/MIT |
| R9 | Benchmarks ruins (ruído, poucos dados) levarem a decisões erradas | média | médio | protocolo fixo, 3 repetições, mediana, avaliação cega |

---

## 6. Custos

| Item | Custo | Observação |
|---|---|---|
| Termux, llama.cpp, AI Edge Gallery, modelos abertos | R$ 0 | só tempo, dados móveis/Wi-Fi e desgaste de bateria |
| Experimentos A e B locais | R$ 0 | ~4–6 h do seu tempo **[estimativa]** |
| Experimento C — nuvem (Anthropic) | ver abaixo | **requer sua autorização** |
| Backend | R$ 0 (não usar) | |

Estimativa para o Experimento C com Claude (preços de tabela da API Anthropic
segundo a referência que consultei, datada de 2026-10-06 — **confirmar na página
de preços antes de gastar**): Claude Sonnet 5.5 a US$ 2 / US$ 10 por milhão de
tokens (entrada/saída); Claude Opus 5.5 a US$ 4 / US$ 20.
Supondo ~3 mil tokens de entrada e ~15 mil de saída (incluindo raciocínio) por
execução completa das duas fases **[suposição]**:

| Modelo | Por execução | 3 execuções |
|---|---|---|
| Claude Sonnet 5.5 | ≈ US$ 0,16 | ≈ US$ 0,50 |
| Claude Opus 5.5 | ≈ US$ 0,31 | ≈ US$ 0,95 |

Preços de OpenAI e Google: **não consegui confirmar** daqui; consultar as
páginas oficiais. Sugestão: definir um **limite de gasto de US$ 5** no console
do provedor antes do primeiro teste.

---

## 7. Recomendação

1. **Mover o MANUTÊ para um repositório próprio** (Q1).
2. **Fase 1 só investigativa, sem app:** Experimentos A0 → A → B → C conforme
   `experiments/PROTOCOLO.md`.
3. **Runtimes para medir:** LiteRT-LM (via AI Edge Gallery) e llama.cpp (via
   Termux). Não escolher o runtime do APK antes dos números.
4. **Modelos:** Qwen3 0.6B/1.7B/4B como linha principal (Apache 2.0) + um
   Gemma pequeno (melhor caminho no LiteRT-LM). 7–8B apenas um teste de
   viabilidade.
5. **Nuvem:** começar com **um** provedor via **chave de API própria** (BYOK).
   Nada de reaproveitar sessões de assinatura.
6. **Claude Code / Codex CLI:** ferramentas externas, oficiais e não
   modificadas, só no desktop, autenticadas por você.
7. **Arquitetura:** monólito modular, porta `Engine` única, memória em SQLite
   estruturada, Router por regras, Policy com "nada sai sem permissão".

---

## 8. Plano de execução incremental

| Fase | Entrega | Quem | Critério de saída |
|---|---|---|---|
| 0 ✅ | Este diagnóstico + harness (`bench.py`, testes) + Problema B com suíte oculta | Claude | testes do harness passando (8/8); suíte oculta validada contra a referência (9/9) |
| 1 | A0: números do AI Edge Gallery; `device_info.sh info` | você | variante/SoC confirmados; primeira linha da tabela de resultados |
| 2 | A: llama.cpp no Termux, matriz de modelos, teste sustentado | você (eu ajudo a interpretar) | tabela preenchida para ≥ 3 modelos; decisão sobre o teto de tamanho |
| 3 | B + C local: problema B nos 2 melhores modelos locais | você + Claude (avaliação cega) | pontuação de rubrica e % de testes ocultos |
| 4 | C nuvem: 1 provedor, 3 execuções | **após sua autorização de gasto** | comparação completa; decisão "o que roda local × nuvem" |
| 5 | CORE mínimo (CLI): porta Engine + 2 adaptadores (local + 1 nuvem) + memória SQLite + Policy + Router por regras | Claude | critérios de sucesso 1–6 demonstrados no desktop/Termux |
| 6 | Decidir APK (Kotlin/Compose, runtime escolhido pelos números) | decisão conjunta | ADR escrito com justificativa |

### O que preciso de você para seguir

1. Rodar `device_info.sh info` (ou só dizer o modelo exato em *Configurações →
   Sobre o telefone*) para confirmarmos Exynos × Snapdragon.
2. Dizer se aceita mover para um repositório próprio.
3. Para a Fase 4: autorizar (ou não) um teto de gasto e escolher o primeiro
   provedor.

---

## 9. Fontes consultadas

- Claude Code — *Legal and compliance* (lido diretamente em 2026-11-05):
  <https://code.claude.com/docs/en/legal-and-compliance>
- Referência interna de modelos e preços da API Claude (cache de 2026-10-06), via
  skill de API da própria ferramenta — confirmar em <https://platform.claude.com/>
- LiteRT-LM — visão geral (conteúdo obtido via resultado de busca; a página não
  abriu deste ambiente): <https://developers.google.com/edge/litert-lm/overview>
- Anúncio do LiteRT como framework universal (jan/2026, segundo a busca):
  <https://yourstory.com/ai-story/google-litert-the-universal-framework-for-on-device-ai>
- Codex — autenticação (conteúdo obtido via resultado de busca; a página não
  abriu deste ambiente): <https://developers.openai.com/codex/auth>
- Cobertura jornalística das mudanças de política da Anthropic em 2026
  (secundárias, apenas contexto):
  <https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/>,
  <https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use>
- Estudo de LLMs em celulares (dados de 2024, referência de ordem de grandeza):
  <https://arxiv.org/html/2410.03613v4>

Afirmações sobre hardware do S22+, licenças de modelos, status do Jetpack
Security e termos da OpenAI/Google vêm do meu conhecimento prévio (corte em
meados de 2026) e estão marcadas como **[verificar]** onde a incerteza importa.
