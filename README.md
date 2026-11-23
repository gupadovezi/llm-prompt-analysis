# Estudo de prompt engineering em dor lombar

Este repositório junta o que estava espalhado. A codificação original não era um projeto do Cursor: era um skill em `~/.cursor/skills/lbp-llm-prompt-accuracy/` no computador onde a conversa rodou. Por isso ela não aparecia no seletor de projetos, nem no GitHub.

Os textos brutos continuam na planilha [Data_Prompt_Study](https://docs.google.com/spreadsheets/d/1phz5iTK4GwmzBwqwRF4BlM-nVzFjhwmzvZjqDfAvF4M). A codificação de cada recomendação está em `data/recommendations.jsonl`: 4.768 linhas, 4.295 accurate, 265 inaccurate, 208 unclear. Esses totais são os do manuscrito.

| Pasta | O que é |
| --- | --- |
| `data/recommendations.jsonl` | Uma linha por recomendação, com modelo, vinheta, frame, turno e rótulo |
| `protocol/` | Codebook, plano estatístico e o skill que gerou a codificação |
| `reports/` | Relatório de 21 de setembro de 2026 (320 respostas) e o de 22 de setembro (576 respostas, nove frames) |
| `manuscript/` | Manuscrito com os comentários |
| `analysis/` | Checagem do qui-quadrado a partir das tabelas publicadas, e um contraste à parte lido da planilha bruta |

O plano em `protocol/statistics.md` já marca a logística mista com intercepto aleatório da vinheta como teste confirmatório. O qui-quadrado fica como alternativa se o misto não convergir. Esse ajuste está em `analysis/fit_clustered.py` e o resultado em `analysis/clustered_results.json`.

## O que o modelo com cluster muda

O χ² no arquivo é o do manuscrito: modelo × acurácia = 643,41; frame × acurácia = 162,89. A logística abaixo usa as mesmas 4.768 linhas. A referência é ChatGPT e o frame neutro. O erro padrão é o robusto por cluster.

| Contraste | OR | p, cluster = resposta (576) | p, cluster = vinheta (16) |
| --- | --- | --- | --- |
| BioBERT contra ChatGPT | 0,13 | 6×10⁻⁶⁹ | 4×10⁻³¹ |
| Gemini contra ChatGPT | 1,17 | 0,29 | 0,11 |
| DeepSeek contra ChatGPT | 0,80 | 0,14 | 0,12 |
| Fisioterapeuta, ventosa, contra neutro | 0,38 | 3×10⁻¹⁰ | 2×10⁻⁶ |
| Médico, ventosa, contra neutro | 0,38 | 7×10⁻¹⁰ | 1×10⁻⁷ |
| Osteopata contra neutro | 1,01 | 0,94 | 0,95 |
| Massoterapeuta contra neutro | 1,03 | 0,83 | 0,85 |

O GEE por vinheta e o logit misto bayesiano com intercepto aleatório da vinheta repetem o mesmo desenho. No pareado por vinheta, o BioBERT fica abaixo do ChatGPT nas 16 vinhetas (diferença média −0,21, Wilcoxon p = 3×10⁻⁵) e a ventosa fica abaixo de terapia manual ou massagem nas 16 (diferença média −0,09, Wilcoxon p = 3×10⁻⁵). Gemini e DeepSeek não se separam do ChatGPT (p = 0,13 e 0,10).

```bash
python analysis/fit_clustered.py
```

## O qui-quadrado do manuscrito

O método testa modelo e prompt frame com χ² nas 4.768 recomendações. A média é 8,3 recomendações por resposta, e a mesma vinheta entra nos 4 modelos e nos 9 frames. Esse χ² trata cada linha como um ensaio. O Wilcoxon e o McNemar do turno 1 contra o turno 2 já são pareados; o problema é o χ².

Corrigir pelo efeito de delineamento dentro da resposta, 1 + (8,3 − 1) × ICC:

| Teste publicado | χ² | ICC que levaria o p a 0,05 |
| --- | --- | --- |
| Modelo × acurácia, df = 6 | 643,41 | 6,9, impossível: o teto do ICC é 1, e mesmo ICC = 1 deixa p = 1×10⁻¹⁴ |
| Frame × acurácia, df = 16 | 162,89 | 0,71 |
| Ventosa contra terapia manual/massagem, df = 1, Yates, sem unclear | 62,64 | 2,1, também acima do teto; com ICC = 1 o p ainda é 0,006 |

O χ² de modelo é o RAG contra os outros três (75,0% contra 94,3–96,0%; 204 das 208 recomendações unclear são do RAG). Na média por turno da Tabela 4 a distância é 0,54 contra 0,95–0,97. Usando o desvio-padrão do turno como se fosse o desvio da vinheta (n = 16), o que infla o erro padrão, o p do RAG contra cada modelo geral continua em torno de 0,003.

Entre ChatGPT, Gemini e DeepSeek o χ² pareado nas recomendações já sai p = 0,13, 0,035 e 0,053. Com Bonferroni e com a resposta como unidade, esses três não se separam.

O contraste de frame encolhe, e só perde p < 0,05 se as recomendações de uma mesma resposta forem quase cópias (ICC por volta de 0,7). Não são: nas folhas de ventosa os três modelos gerais somam 106 recomendações inaccurate em 96 respostas, cerca de uma linha inaccurate no meio de várias linhas accurate. Um intercepto aleatório de vinheta não apaga um excesso que se repete nos três modelos. O que esse modelo também não separa é profissão e tratamento: fisioterapeuta e médico pedem ventosa; osteopata e massoterapeuta pedem terapia manual ou massagem junto com exercício.

Um modelo misto “por recomendação” usaria a linha errada como cluster. A recomendação é a observação. O cluster é a resposta, com intercepto aleatório da vinheta. Se a ideia é agrupar pelo conteúdo (ventosa, paracetamol, exercício), a Tabela 7 já faz isso: 149/265 inaccurate são paracetamol e 80/265 são ventosa.

```bash
python analysis/manuscript_chi2_sensitivity.py
```

## Leitura direta da planilha, outro desfecho

A seção abaixo não é o χ² do manuscrito. É uma codificação binária, feita nesta análise, do trecho “Should I follow his recommendation?” na planilha bruta.

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
