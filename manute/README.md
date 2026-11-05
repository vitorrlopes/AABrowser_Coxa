# MANUTÊ — fase de viabilidade

Material da Missão 1 (investigação). Não há aplicativo ainda — de propósito.

> Esta pasta é autocontida e **deveria ir para um repositório próprio**: este
> repositório é um navegador para Android Auto (GPLv3) sem relação com o
> MANUTÊ. Ver `docs/01-missao-1-diagnostico.md`, questionamento Q1.

| Caminho | Conteúdo |
|---|---|
| `docs/01-missao-1-diagnostico.md` | diagnóstico, alternativas, comparativos, riscos, custos, recomendação e plano |
| `experiments/PROTOCOLO.md` | protocolo reproduzível dos Experimentos A, B e C |
| `experiments/bench.py` | harness de medição (TTFT, tokens/s) — só biblioteca padrão, roda no Termux |
| `experiments/device_info.sh` | identificação do aparelho e amostragem de temperatura/bateria via adb |
| `experiments/prompts.jsonl` | prompts fixos do Experimento A |
| `experiments/problema_b/` | Problema B: enunciado em duas fases, rubrica e suíte de testes oculta |

## Testes

```sh
cd experiments && python3 -m unittest -v                         # harness
cd experiments/problema_b && python3 -m unittest -v test_hidden  # suíte oculta vs. referência
```
