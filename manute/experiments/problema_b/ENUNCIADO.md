# Problema B — Limitador de taxa para chamadas a provedores

Problema real e pequeno do próprio MANUTÊ: o CORE precisa limitar a taxa de
chamadas aos provedores de nuvem para respeitar limites e custos.

O experimento tem **duas fases**, enviadas como mensagens separadas e
**idênticas para todos os modelos**. A fase 1 avalia se o modelo questiona antes
de implementar; a fase 2 fixa o contrato para que a suíte oculta
(`test_hidden.py`) meça o código objetivamente.

---

## Fase 1 — prompt (copiar exatamente)

```text
Preciso de um rate limiter em Python para limitar as chamadas que meu
aplicativo faz a APIs de IA na nuvem. Antes de escrever qualquer código:
1. Explique o seu entendimento do problema.
2. Liste os requisitos que estão faltando ou ambíguos e as perguntas que você
   faria.
3. Proponha uma arquitetura (com alternativas e por que escolheu uma).
Não escreva a implementação ainda.
```

## Fase 2 — prompt (copiar exatamente)

```text
Decisões tomadas: processo único, várias threads, algoritmo token bucket,
sem dependências externas. Implemente em um único arquivo Python:

class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float,
                 clock: Callable[[], float] = time.monotonic) -> None
    def try_acquire(self, tokens: float = 1) -> bool
    def available(self) -> float

Regras:
- O balde começa cheio.
- capacity <= 0 ou refill_per_second <= 0 -> ValueError.
- tokens <= 0 ou tokens > capacity -> ValueError.
- try_acquire nunca bloqueia; retorna False sem consumir nada se não houver
  tokens suficientes.
- Deve ser seguro para uso por várias threads.
Depois:
4. Entregue a implementação.
5. Entregue testes com unittest (use um relógio falso injetado).
6. Faça uma revisão crítica do seu próprio código: riscos, limitações e o que
   mudaria para um ambiente distribuído.
```

Observação: a regra "relógio que volta no tempo" **não** está no enunciado de
propósito. A suíte oculta testa esse caso; o modelo deveria levantá-lo na fase 1
ou na revisão crítica (o `clock` é injetável, então pode não ser monotônico).

---

## Rubrica de avaliação

Pontuação 0–3 por critério. Avaliação **cega**: quem pontua não sabe qual
modelo produziu a resposta (renomear as respostas para A, B, C antes de ler).

| # | Critério | Como medir |
|---|---|---|
| 1 | Entendimento | Descreve corretamente o problema e o contexto (limite por provedor, custos) |
| 2 | Requisitos ausentes | Quantos destes levanta: escopo (global/por provedor/por usuário), burst, bloquear vs. falhar, multi-thread/multiprocesso/distribuído, relógio, limites em tokens vs. requisições, resposta a HTTP 429 |
| 3 | Arquitetura | Compara ≥2 algoritmos (token bucket, leaky bucket, janela fixa/deslizante) com justificativa |
| 4 | Precisão do código | **Objetivo:** % de testes da `test_hidden.py` que passam |
| 5 | Testes próprios | Os testes do modelo rodam? Usam relógio falso? Cobrem bordas? |
| 6 | Segurança/robustez | Lock correto, validação de entrada, relógio que volta |
| 7 | Simplicidade | Sem abstrações desnecessárias; tamanho proporcional ao problema |
| 8 | Revisão crítica | Aponta limitações reais (ex.: não serve para multiprocesso/distribuído) |
| 9 | Consistência | Variação entre as 3 execuções do mesmo modelo |

Como rodar a suíte oculta numa resposta:

```bash
# salvar o código do modelo em results/<label>/run1/solution.py
cd experiments/problema_b
MANUTE_CANDIDATE=../results/<label>/run1/solution.py python3 -m unittest -v test_hidden
```

> Aviso de segurança: o código gerado por modelo é executado. Rode a suíte num
> ambiente descartável (Termux sem dados pessoais, contêiner ou VM) e leia o
> código antes.
