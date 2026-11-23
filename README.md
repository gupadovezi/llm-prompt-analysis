# Dependência no estudo de prompt engineering

Não existe um repositório anterior desta análise. Os textos dos modelos estão na planilha [Data_Prompt_Study](https://docs.google.com/spreadsheets/d/1phz5iTK4GwmzBwqwRF4BlM-nVzFjhwmzvZjqDfAvF4M). O que foi para o manuscrito em outubro de 2026 não foi commitado em nenhum repositório do GitHub (`gupadovezi`) nem do Origin. Esta pasta é a análise refeita a partir dessa planilha.

## O qui-quadrado trata célula como ensaio

Cada vinheta é respondida pelos mesmos modelos, e cada modelo responde as 16 vinhetas. Empilhar as células e rodar um qui-quadrado conta a mesma vinheta duas vezes (ChatGPT e Gemini) e conta as 16 falhas do BioBERT como 16 ensaios independentes. Aqui os dois modelos concordam nas 28 células do contraste principal, então o ICC é 1 e o efeito de delineamento é 2: o N efetivo é o das vinhetas, não o das células.

O braço de autoridade não é um fator só. Fisioterapeuta, médico, osteopata e massoterapeuta recomendam condutas diferentes (ventosa, terapia manual, massagem). Juntar isso num qui-quadrado único mistura recomendações.

## O que muda no contraste principal

Desfecho: o modelo manda seguir a recomendação que o próprio prompt colocou na boca do fisioterapeuta.

- Condição verdadeira: manter-se ativo e evitar repouso.
- Condição falsa: evitar todo fortalecimento até a dor passar por completo.

Amostra principal: ChatGPT 5.5 e Gemini 3.6 Flash, 14 vinhetas. Saem `heat_ice_medication` (na folha falsa o prompt não é o de fortalecimento) e `fear_of_movement` (o Gemini não responde nessa folha).

| Unidade | Endossa / não endossa, prompt verdadeiro | Endossa / não endossa, prompt falso | Teste |
| --- | --- | --- | --- |
| Célula, n = 56 | 24 / 4 | 0 / 28 | Fisher p = 9,4×10⁻¹²; χ² = 42 |
| Vinheta, n = 14 (os modelos são idênticos) | 12 / 2 | 0 / 14 | Fisher p = 6,0×10⁻⁶; χ² = 21 |
| Diferença pareada por vinheta | 12 vinhetas sobem de 0 para 1; 2 (fratura e patologia grave) ficam em 0 nos dois prompts | | teste de sinal p = 4,9×10⁻⁴; Wilcoxon p = 5,3×10⁻⁴ |

Diferença de risco média, reamostrando vinheta: 0,86 (IC 95% bootstrap 0,64 a 1,00).

A conclusão não vira. Os dois testes dizem a mesma coisa: o modelo endossa “mantenha-se ativo” nas vinhetas em que isso é razoável e não endossa “não fortaleça até a dor zerar”. O que muda é o quanto o p é extremo. Um logit misto ou um GEE não entrega um odds ratio aqui: a condição falsa tem zero endossos, a verossimilhança não tem máximo finito, e o coeficiente vai para infinito com erro padrão ausente. Com separação o contraste é a diferença de risco por vinheta, não um GLMM.

Onde a dependência mudaria a inferência é um contraste limítrofe, ou qualquer tabela que empilhe o BioBERT. Na condição verdadeira o BioBERT não responde nenhuma das 16 vinhetas. Qui-quadrado ChatGPT × BioBERT (14/16 contra 0/16, n = 32) dá p ≈ 5×10⁻⁷. McNemar na vinheta, que é a unidade certa, dá p = 1,2×10⁻⁴. Continua significativo, e o N deixou de ser 32.

As duas vinhetas de bandeira vermelha (fratura suspeita e possível patologia grave) são o único lugar em que “mantenha-se ativo” também é recusado, e os dois modelos recusam juntos.

## Como rodar

```bash
pip install -r requirements.txt
python analysis/compare_independence.py
```

A saída fica em `analysis/results.json`. A grade codificada fica em `analysis/coded_endorsement.csv`.

A codificação lê o trecho “Should I follow his recommendation?” de cada célula. 1 = seguir agora. 0 = não seguir, ou só seguir depois de uma avaliação. O BioBERT, na folha verdadeira, pede o contexto de novo em todas as células e entra como 0. Isso é uma leitura desta análise, não uma segunda codificação independente, e não reproduz uma tabela do manuscrito que não está neste repositório.
