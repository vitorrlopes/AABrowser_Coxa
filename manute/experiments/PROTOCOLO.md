# Protocolo experimental — PoC 1 do MANUTÊ

Objetivo: obter **números reais** do Galaxy S22+ do usuário e uma comparação
justa entre modelo local pequeno, modelo local maior e modelo de nuvem.
Nada aqui foi medido ainda: todas as tabelas de resultado começam vazias.

## 0. Pré-condições (registrar no início de cada sessão)

| Item | Valor exigido | Por quê |
|---|---|---|
| Variante e SoC | saída de `ADB=1 ./device_info.sh info` | Exynos 2200 e Snapdragon 8 Gen 1 se comportam de forma diferente |
| Bateria | 80–100 %, **fora do carregador** | carregar aquece e falseia a bateria |
| Rede | modo avião (Experimento A) | garante execução 100 % local e menos ruído |
| Tela | ligada, brilho fixo, app em primeiro plano | evita que o Android suspenda o processo |
| Temperatura inicial | bateria < 32 °C (`temperature` < 320 em dumpsys) | throttling térmico distorce a medição |
| Apps em segundo plano | todos fechados | memória disponível varia muito |
| Modo de desempenho | padrão de fábrica, anotar se mudou | o usuário decide; não alterar sem anotar |

## 1. Experimento A0 — sem código (≈ 30 min)

Objetivo: ter um primeiro número de referência antes de compilar qualquer coisa.

1. Instalar o **Google AI Edge Gallery** (app de demonstração do LiteRT-LM;
   verificar disponibilidade atual na Play Store ou no GitHub do Google AI Edge).
2. Baixar um modelo Gemma pequeno sugerido pelo app (ex.: variante E2B).
3. Executar os 4 prompts de `prompts.jsonl` com backend **CPU** e depois **GPU**.
4. Anotar os números exibidos pelo app (tempo até o primeiro token, prefill e
   decode em tokens/s) na tabela de resultados.

## 2. Experimento A — llama.cpp no Termux (≈ 2–3 h)

### 2.1 Preparação
```sh
# Termux (instalar pelo F-Droid ou GitHub oficial do Termux; a versão da Play Store é antiga)
pkg update && pkg install -y git cmake clang python
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
git rev-parse --short HEAD        # registrar o commit
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 8 --target llama-bench llama-server llama-cli
```

### 2.2 Modelos (GGUF, quantização Q4_K_M; baixar no PC e copiar, ou via `curl` no Termux)
Matriz mínima — 1 modelo por faixa, priorizando licenças permissivas:

| Faixa | Candidato principal | Alternativa | Arquivo aprox.* |
|---|---|---|---|
| 0,5–1B | Qwen3-0.6B | Gemma 3 1B | ~0,4–0,8 GB |
| 2B | Qwen3-1.7B | Gemma E2B (3n/4) | ~1,1–1,6 GB |
| 3–4B | Qwen3-4B | Phi-4-mini (3,8B) / Llama 3.2 3B | ~2,0–2,5 GB |
| 7–8B | Qwen3-8B | Llama 3.1 8B | ~4,7–5 GB |

\* Estimativa a partir de ~0,55–0,6 byte/parâmetro em Q4_K_M. **Verificar o
tamanho real do arquivo.** Verificar também se há geração mais nova de cada
família (o cenário muda a cada poucos meses) e a licença de cada modelo.

### 2.3 Throughput bruto (llama-bench)
```sh
for m in models/*.gguf; do
  ./build/bin/llama-bench -m "$m" -p 512 -n 128 -t 4 -r 3 -o jsonl >> ~/results-llamabench.jsonl
done
```
Repetir com `-t 4` e `-t 6`/`-t 8` uma vez para achar o melhor número de
threads (núcleos de eficiência podem piorar o resultado). Registrar o melhor.

### 2.4 TTFT, carga e qualidade (llama-server + bench.py)
```sh
/usr/bin/time -v ./build/bin/llama-server -m models/X.gguf -c 4096 -t 4 \
  --host 127.0.0.1 --port 8080 2> server.log &
# tempo de carregamento = instante do log "server is listening" - início
python bench.py --label s22p-<soc>-<modelo>-q4km-cpu --prompts prompts.jsonl \
  --runs 3 --out results/a.jsonl --device-info results/device.txt
```
- **Memória:** pico de RSS do `llama-server` (`/usr/bin/time -v`, ou
  `adb shell dumpsys meminfo <pid>`).
- **Morte do processo:** se o Android encerrar o processo (LMK), registrar
  "inviável" para aquele modelo/contexto — isso também é resultado.

### 2.5 Sustentado: temperatura e bateria (10 min por modelo)
No PC, em paralelo: `ADB=1 ./device_info.sh sample 5 > results/sensors-<label>.csv`.
No celular: rodar o prompt `a4-contexto-longo` em laço por 10 minutos
(`--runs 20`). Registrar: queda de tokens/s entre o 1º e o último minuto,
temperatura máxima e variação do `charge_counter` (µAh).

> Medir energia pelo percentual da bateria é grosseiro; o `charge_counter` é
> melhor, mas a precisão depende do fabricante. Tratar como estimativa.

## 3. Experimento B — problema de engenharia

Ver `problema_b/ENUNCIADO.md`. Para cada modelo: 3 execuções completas
(fase 1 + fase 2), salvar as respostas brutas em
`results/<label>/runN/{fase1.md,fase2.md,solution.py}` e rodar a suíte oculta.

## 4. Experimento C — comparação

Mesmo problema, mesmas mensagens, 3 execuções por modelo:

| Papel | Sugestão |
|---|---|
| Local pequeno | melhor modelo de 1–2B do Experimento A |
| Local maior | melhor modelo de 3–4B (ou 7–8B se não for morto pelo Android) |
| Nuvem | **somente após autorização de gasto** — 1 provedor primeiro |

Notas de justiça da comparação:
- Modelos locais: `temperature=0` (o harness já envia).
- A API do Claude deixou de aceitar `temperature`/`top_p`/`top_k` nos modelos
  atuais; não é possível fixar a amostragem. Por isso são 3 execuções por
  modelo e o critério 9 (consistência) da rubrica.
- Limite de saída igual para todos (ex.: 4096 tokens), registrar truncamentos.
- Avaliação cega pela rubrica (renomear respostas para A/B/C).

## 5. Tabela de resultados (preencher; não inventar valores)

| Label | SoC | Backend | Carga (s) | TTFT mediana (s) | Decode tok/s | Prefill tok/s | RSS pico (GB) | Temp máx (°C) | Δ bateria 10 min | Testes ocultos | Rubrica (0–27) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | |
