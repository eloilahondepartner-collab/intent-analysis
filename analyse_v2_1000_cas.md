# Évaluation des prompts V2 — 1 000 dossiers aléatoires

## Protocole

- **Échantillon** : 1 000 dossiers uniques tirés aléatoirement (`random_state=42`) parmi les 9 197 dossiers routés par l'IA.
- **Texte** : objet et corps complets des e-mails, nettoyés du HTML et de l'historique de réponse (13 corps tronqués à 3 000 caractères).
- **Classification à l'aveugle** : chaque message a été lu et classé par un LLM appliquant strictement les 9 intentions V2, sans accès à l'ancien domaine ni à l'équipe finale. Les seuils et le mapping vers les domaines ont ensuite été appliqués par script.
- **Vérité terrain** : dernier domaine de `[CORE] Current Teams (Case)`.
- **Comparaison appariée** : sur les mêmes 1 000 dossiers, comparaison de l'ancien routage et de V2 avec un test exact de McNemar et un bootstrap apparié (10 000 tirages).

## Résultat principal

| Métrique | Ancien bot | Prompts V2 | Écart V2 − ancien | IC95 de l'écart | McNemar *p* |
|---|---:|---:|---:|---:|---:|
| Taux d'erreur, formule notebook (n = 1 000) | **12,60 %** [10,69 ; 14,80] | **30,50 %** [27,73 ; 33,42] | **+17,9 pts** | [+15,0 ; +20,7] | 7 × 10⁻³³ |
| Désaccord strict avec l'équipe finale (n = 964 avec vérité connue) | 37,14 % | 49,90 % | +12,8 pts | [+9,2 ; +16,2] | 8 × 10⁻¹³ |
| Volume fallback (Other + No detection) | 258 (25,8 %) | 183 (18,3 %) | −7,5 pts | — | — |

Sur les dossiers discordants de la formule notebook, V2 corrige **34** erreurs de l'ancien bot et en introduit **213**.

**Conclusion : sur ce test, les prompts V2 ne font pas mieux que l'ancien routage.** Ils sont nettement moins performants, et l'écart est statistiquement très significatif selon les deux métriques. Le taux de 12,60 % de l'ancien bot est cohérent avec la référence du notebook (12,22 %), ce qui confirme la représentativité de l'échantillon.

## Anomalies ciblées présentes dans l'échantillon aléatoire

| Anomalie historique | Corrigée par V2 |
|---|---:|
| Faux positifs B2B → Aftersales | 8/15 (53 %) |
| Fuites Aftersales → Marketplace | 5/52 (10 %) |
| Faux positifs Legal → Aftersales | 2/3 (67 %) |

V2 réduit une partie des faux positifs B2B et Legal, mais ce gain porte sur peu de dossiers et ne compense pas les erreurs introduites ailleurs.

## Exactitude par équipe finale

| Équipe finale | Dossiers | Ancien bot | V2 |
|---|---:|---:|---:|
| Aftersales | 484 | 61,8 % | **72,5 %** |
| Marketplace | 301 | **68,1 %** | 26,9 % |
| Presales | 116 | **50,0 %** | 13,8 % |
| B2B | 30 | **93,3 %** | 70,0 % |
| Services | 25 | 36,0 % | **40,0 %** |
| Legal | 7 | **100 %** | 57,1 % |

## Causes principales des erreurs V2

1. **Marketplace → Aftersales : 189 dossiers**, première source d'écart. La règle V2 exige une mention explicite d'un vendeur tiers, alors que le client l'écrit très rarement : un indice explicite apparaît dans 4 extraits sur 189. L'ancien bot routait correctement 122 de ces dossiers, probablement à l'aide d'un signal absent du texte, comme des métadonnées de commande. Le suffixe de commande `-A` ne concerne que 46 dossiers Marketplace sur 301.
2. **Presales → Other : 57 dossiers**. Les demandes de compte, de fidélité, de carte cadeau ou de code promo sont mappées vers `Other` en V2, alors qu'elles sont traitées par l'équipe **Presales** dans l'organisation actuelle. Il s'agit d'un problème de mapping des domaines.
3. **Aftersales → No detection : 58 dossiers**. Les messages composés seulement d'un objet ou d'un numéro de commande passent en fallback, alors que l'équipe finale les traite en Aftersales.
4. **Faux B2B : 23 dossiers**. Des prospections commerciales de fournisseurs, des dons ou des clubs sont classés B2B, alors que leur équipe finale est Aftersales ou Marketplace.

## Tests de sensibilité (exploratoires, a posteriori)

| Scénario | Formule notebook : ancien vs V2 | Désaccord strict : ancien vs V2 |
|---|---:|---:|
| V2 tel quel | 12,6 % vs 30,5 % | 37,1 % vs 49,9 % |
| + Compte Client mappé vers Presales | 12,6 % vs 34,2 % | 37,1 % vs 44,5 % (*p* = 3 × 10⁻⁵) |
| + commandes `-A` routées vers Marketplace | 12,6 % vs 32,0 % | 37,1 % vs 42,2 % (*p* = 0,003) |

Même après ces corrections favorables à V2, l'ancien routage reste significativement meilleur. Ces scénarios ont été ajustés sur le même échantillon : ils servent au diagnostic et ne constituent pas une validation.

## Recommandations

1. **Ne pas déployer V2 en l'état.**
2. **Marketplace** : ne pas dépendre uniquement du texte. Ajouter un signal de métadonnées (vendeur, canal ou format de commande), ou assouplir la règle quand le texte évoque un suivi de commande sans preuve d'expédition par Decathlon.
3. **Mapping** : aligner les domaines cibles sur l'organisation réelle, notamment Compte Client / Loyalty → Presales.
4. **Fallback** : utiliser l'objet du message ; les e-mails composés seulement d'un numéro de commande relèvent par défaut d'Aftersales.
5. **B2B** : exclure explicitement la prospection commerciale entrante, les candidatures et les demandes de dons.
6. **Validation** : après correction, refaire le test sur un **nouveau** tirage aléatoire, avec un autre seed, en utilisant le modèle de production (`gpt-4o-mini`) dans un environnement autorisé.

## Limites

- La classification a été réalisée par un LLM appliquant les règles V2, pas par `gpt-4o-mini` en production. Les résultats évaluent donc d'abord la taxonomie et ses règles ; le modèle de production pourrait obtenir des résultats un peu différents.
- La vérité terrain correspond à l'équipe qui a finalement traité le dossier. Elle reflète aussi l'organisation interne et les métadonnées, pas uniquement le contenu du texte.
- La formule du notebook ne compte pas un fallback comme une erreur. Elle avantage donc l'ancien bot, qui produit plus de fallback ; c'est pourquoi la métrique stricte est aussi présentée. V2 reste moins performant avec cette métrique.

## Fichiers

- `benchmark_1000_cases_v2.csv` : 1 000 lignes (`_Case_ID`, `Clean_Subject`, `Old_Domain`, `True_Domain`, `V2_Intent`, `V2_Confidence`, `V2_Domain`, `Is_V2_Error`, `Reasoning` et colonnes d'audit)
- `v2_1000_kpi_summary.csv`, `v2_1000_per_domain.csv`, `v2_1000_confusion_matrix.csv`
- `v2_1000_remaining_errors.csv` : 481 écarts exacts `V2_Domain != True_Domain`
- `evaluate_v2_1000.py` : script reproductible de calcul des statistiques
