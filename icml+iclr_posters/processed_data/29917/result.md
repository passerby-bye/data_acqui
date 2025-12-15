# HelpSteer2-Preference: Complementing Ratings with Preferences

## Why do we need HelpSteer2-Preference?

It's unclear what the best approach for Reward Modelling is

Bradley-Terry models: OpenAI InstructGPT, Anthropic HH-RLHF, Meta Llama 3

○ Regression models: Nemotron 4 340B Reward, RLHFlow ArmoRM 8B

• We need matched data for both approaches to find out

○ Identical set of prompts and responses

○ Collected for Purpose: Retrofitting Regression data for preference is not sufficient

o High Quality: Garbage in; Garbage out – need to ensure high signal to noise ratio

Open-source dataset to support open science

○ Data Gap: There’s currently no open-source dataset that fulfills all of the criteria above

The community needs a high-quality, matched and open-source Preference data to accompany Regression data

<div style="text-align: center;">Regression and Bradley-Terry perform similarly but can complement each other to reach No. 1 on Reward Bench with Overall 94.1 (on 1 Oct 2024).</div>



<table border=1 style='margin: auto; width: max-content;'><tr><td rowspan="2">Model Type</td><td rowspan="2">Model</td><td rowspan="2">Overall</td><td rowspan="2">Chat</td><td colspan="2">RewardBench</td><td rowspan="2">Reasoning</td></tr><tr><td style='text-align: center;'>Chat-Hard</td><td style='text-align: center;'>Safety</td></tr><tr><td rowspan="2">SteerLM Regression</td><td style='text-align: center;'>HelpSteer Attributes</td><td style='text-align: center;'>92.4</td><td style='text-align: center;'>95.0</td><td style='text-align: center;'>85.5</td><td style='text-align: center;'>94.0</td><td style='text-align: center;'>95.1</td></tr><tr><td style='text-align: center;'>Helpfulness Only</td><td style='text-align: center;'>93.0</td><td style='text-align: center;'>97.2</td><td style='text-align: center;'>84.2</td><td style='text-align: center;'>94.6</td><td style='text-align: center;'>95.8</td></tr><tr><td rowspan="3">Bradley-Terry (from scratch)</td><td style='text-align: center;'>Regular</td><td style='text-align: center;'>91.5</td><td style='text-align: center;'>97.5</td><td style='text-align: center;'>80.3</td><td style='text-align: center;'>90.5</td><td style='text-align: center;'>97.9</td></tr><tr><td style='text-align: center;'>Margin</td><td style='text-align: center;'>91.5</td><td style='text-align: center;'>98.0</td><td style='text-align: center;'>78.5</td><td style='text-align: center;'>94.6</td><td style='text-align: center;'>94.8</td></tr><tr><td style='text-align: center;'>Scaled</td><td style='text-align: center;'>92.7</td><td style='text-align: center;'>97.8</td><td style='text-align: center;'>83.5</td><td style='text-align: center;'>93.2</td><td style='text-align: center;'>96.0</td></tr><tr><td rowspan="4">Bradley-Terry (init. with Helpfulness-only Regression Model)</td><td style='text-align: center;'>Regular</td><td style='text-align: center;'>92.7</td><td style='text-align: center;'>98.9</td><td style='text-align: center;'>82.9</td><td style='text-align: center;'>93.7</td><td style='text-align: center;'>95.4</td></tr><tr><td style='text-align: center;'>Margin</td><td style='text-align: center;'>93.0</td><td style='text-align: center;'>98.3</td><td style='text-align: center;'>83.8</td><td style='text-align: center;'>94.0</td><td style='text-align: center;'>95.8</td></tr><tr><td style='text-align: center;'>Scaled</td><td style='text-align: center;'>93.7</td><td style='text-align: center;'>98.0</td><td style='text-align: center;'>85.7</td><td style='text-align: center;'>94.3</td><td style='text-align: center;'>96.7</td></tr><tr><td style='text-align: center;'>Scaled + ExPO</td><td style='text-align: center;'>94.1</td><td style='text-align: center;'>97.5</td><td style='text-align: center;'>85.7</td><td style='text-align: center;'>95.1</td><td style='text-align: center;'>98.1</td></tr><tr><td rowspan="2">External Baselines</td><td style='text-align: center;'>Skywork-Reward-Gemma-2-27B</td><td style='text-align: center;'>93.8</td><td style='text-align: center;'>95.8</td><td style='text-align: center;'>91.4</td><td style='text-align: center;'>91.9</td><td style='text-align: center;'>96.1</td></tr><tr><td style='text-align: center;'>TextEval-Llama3.1-70B</td><td style='text-align: center;'>93.5</td><td style='text-align: center;'>94.1</td><td style='text-align: center;'>90.1</td><td style='text-align: center;'>93.2</td><td style='text-align: center;'>96.4</td></tr></table>

## Reward Modelling Results

<div style="text-align: center;">Scaled Bradley-Terry</div>


Optimal form of Bradley-Terry is Scaled Bradley-Terry which uses preference strength to scale loss proportionally

 $$ \mathcal{L}_{\mathcal{B T}}=-\log\left(\sigma(r_{\theta}(x,y_{c})-r_{\theta}(x,y_{r}))\right) $$ 

Regular BT [1]

 $$ \mathcal{L}_{\mathcal{M}\mathcal{B}\mathcal{T}}=-\log\left(\sigma(r_{\theta}(x,y_{c})-r_{\theta}(x,y_{r})-m)\right) $$ 

Margin BT [2]

 $$ \mathcal{L}_{\mathcal{S}\mathcal{B}\mathcal{T}}=-m\log\left(\sigma(r_{\theta}(x,y_{c})-r_{\theta}(x,y_{r}))\right) $$ 

Scaled BT (ours)

## HelpSteer2-Preference: Overview

reward ( $ r_{\theta} $ ) for the chosen response ( $ y_{c} $ ) and the rejected response ( $ y_{r} $ ) with the same prompt (x) magnitude (m) of this preference (1 - slightly better, 2 - better, 3 - much better)

Perspective 1 – Data Utilization: Repeated sampling of response pairs with higher preference magnitude

Perspective 2 – Model Training: Larger gradient updates from response pairs with greater preference strength

Difference from Margin BT: Does not assume that the chosen and rejected reward difference >= margin term

HelpSteer2-Preference is an open-source, CC-BY-4.0 licensed, and rich dataset for top-performing and efficient reward modelling.



- Top-performing: Used for Llama-3.1-Nemotron-70B-Reward, No. 1 on Reward Bench (94.1) at time of release (Oct 2024).

- Complementary to Ratings: Prompts and responses are identical with HelpSteer2 (which contains Likert-5 ratings of Helpfulness and other attributes), permitting fair comparison.

- Rich data: Each of 10k samples contains preference between two responses, preference strengths (slightly better, better and much better) and human-written preference justifications.

https://huggingface.co/datasets/nvidia/HelpSteer2#preferences-new---1-oct-2024 >300k downloads

<div style="text-align: center;">Model Alignment Results</div>


<div style="text-align: center;">Trained Reward Model can be used with REINFORCE algorithm during RLHF to produce top-performing model on MT-Bench, AlpacaEval 2 LC and Arena Hard</div>



<table border=1 style='margin: auto; width: max-content;'><tr><td rowspan="2">Model Type</td><td rowspan="2">Model</td><td colspan="4">Aligned Metrics</td></tr><tr><td style='text-align: center;'>MT Bench (GPT-4-Turbo)</td><td style='text-align: center;'>Mean Response Length (Char.s.)</td><td style='text-align: center;'>AlpacaEval 2.0 LC (SE)</td><td style='text-align: center;'>Arena Hard (95% CI)</td></tr><tr><td rowspan="3">Offline RLHF</td><td style='text-align: center;'>Regular DPO</td><td style='text-align: center;'>8.66</td><td style='text-align: center;'>1502.2</td><td style='text-align: center;'>40.4 (1.66)</td><td style='text-align: center;'>52.8 (-2.7, 2.7)</td></tr><tr><td style='text-align: center;'>Margin DPO</td><td style='text-align: center;'>8.58</td><td style='text-align: center;'>1496.6</td><td style='text-align: center;'>41.1 (1.67)</td><td style='text-align: center;'>52.6 (-2.7, 2.8)</td></tr><tr><td style='text-align: center;'>Scaled DPO</td><td style='text-align: center;'>8.74</td><td style='text-align: center;'>1514.8</td><td style='text-align: center;'>41.0 (1.68)</td><td style='text-align: center;'>52.9 (-2.4, 3.1)</td></tr><tr><td rowspan="2">Online RLHF</td><td style='text-align: center;'>PPO</td><td style='text-align: center;'>8.74</td><td style='text-align: center;'>1842.8</td><td style='text-align: center;'>43.8 (1.76)</td><td style='text-align: center;'>58.6 (-2.9, 2.5)</td></tr><tr><td style='text-align: center;'>REINFORCE</td><td style='text-align: center;'>8.98</td><td style='text-align: center;'>2199.8</td><td style='text-align: center;'>57.6 (1.65)</td><td style='text-align: center;'>85.0 (-1.5, 1.5)</td></tr><tr><td rowspan="4">External Baselines</td><td style='text-align: center;'>Llama-3.1-70B-Instruct</td><td style='text-align: center;'>8.22</td><td style='text-align: center;'>1728.6</td><td style='text-align: center;'>38.1 (0.90)</td><td style='text-align: center;'>55.7 (-2.9, 2.7)</td></tr><tr><td style='text-align: center;'>Llama-3.1-405B-Instruct</td><td style='text-align: center;'>8.49</td><td style='text-align: center;'>1664.7</td><td style='text-align: center;'>39.3 (1.43)</td><td style='text-align: center;'>69.3 (-2.4, 2.2)</td></tr><tr><td style='text-align: center;'>Claude-3-5-Sonnet-20240620</td><td style='text-align: center;'>8.81</td><td style='text-align: center;'>1619.9</td><td style='text-align: center;'>52.4 (1.47)</td><td style='text-align: center;'>79.2 (-1.9, 1.7)</td></tr><tr><td style='text-align: center;'>GPT-4o-2024-05-13</td><td style='text-align: center;'>8.74</td><td style='text-align: center;'>1752.2</td><td style='text-align: center;'>57.5 (1.47)</td><td style='text-align: center;'>79.3 (-2.1, 2.0)</td></tr></table>

Reward and REINFORCE models openly accessible (Llama 3.1 licensed) at https://huggingface.co/collections/nvidia/llama-31-nemotron-70b-670e93cd366feea16abc13d8

## HelpSteer2-Preference Data Analysis

<div style="text-align: center;"><img src="imgs/img_in_chart_box_2167_1984_2967_2778.jpg" alt="Image" width="20%" /></div>


- Preference and Helpfulness generally correlates: Larger helpfulness difference likely suggests stronger preference

- Correlation not perfect: Some samples have responses with identical helpfulness but show preference for one response over the other

- Position bias is weak: Humans show slight preference for latter response, possibly because of recency effect. Much lower than automated evals (e.g. GPT4/Claude in MT Bench [3])

## Reference Links

[1] https://arxiv.org/abs/2203.02155

[2] https://arxiv.org/abs/2307.09288

[3] https://arxiv.org/abs/2306.05685