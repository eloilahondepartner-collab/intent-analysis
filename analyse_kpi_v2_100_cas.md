# Analyse comparative — intentions V2

## Résultats sur 100 dossiers

L'échantillon est stratifié : 20 cas B2B litigieux, 20 cas Aftersales vers Marketplace, 10 cas Legal litigieux et 50 cas aléatoires. Il est donc utile pour examiner des anomalies ciblées, mais son taux total n'est pas représentatif de la population.

| Cohorte | Dossiers | Erreur ancien domaine | Erreur V2 | Fallback V2 |
|---|---:|---:|---:|---:|
| B2B ciblé | 20 | 100 % | 40 % | 3 |
| Marketplace ciblé | 20 | 100 % | 90 % | 1 |
| Legal ciblé | 10 | 100 % | 80 % | 0 |
| Aléatoire | 50 | 8 % | 20 % | 9 |
| **Total stratifié** | **100** | **54 %** | **44 %** | **13** |

Le taux d'erreur suit la formule du notebook : le dénominateur inclut tous les dossiers ; une vérité terrain « Non renseigné » ou une prédiction « Other » / « No detection » ne compte pas comme erreur.

## Comparaison générale sur les 50 cas aléatoires

L'ancien routage a 8 % d'erreurs contre 20 % pour V2, soit une hausse observée de 12 points. L'intervalle de confiance de Wilson à 95 % du taux V2 est de 11,24 % à 33,04 %. Le test exact de McNemar donne *p* = 0,1094 : l'écart n'est pas statistiquement significatif au seuil de 5 %, et l'estimation ponctuelle ne montre pas d'amélioration.

Le taux historique de 12,22 % porte sur la population complète. Il ne doit pas être directement comparé au taux total de 44 % du lot stratifié, qui contient volontairement 50 cas litigieux.

## Correction des anomalies ciblées

| Anomalie | Corrigée vers la vérité terrain |
|---|---:|
| Faux positifs B2B réorientés vers Aftersales | 9/20 (45 %) |
| Fuites Aftersales vers Marketplace | 1/20 (5 %) |
| Faux positifs Legal réorientés vers Aftersales | 2/10 (20 %) |

## Tirage aléatoire de 1 000 dossiers

Un tirage reproductible (`random_state=42`) de 1 000 dossiers uniques a été effectué parmi les 9 197 dossiers. Selon la formule du notebook, l'ancien routage présente **126 erreurs sur 1 000, soit 12,60 %**. L'intervalle de confiance de Wilson à 95 % est **[10,69 % ; 14,80 %]**. Le taux historique de 12,22 % est dans cet intervalle ; l'écart observé de +0,38 point n'est pas statistiquement significatif à 5 %.

Le fichier de ce tirage est `benchmark_1000_random_cases.csv` et sa synthèse baseline est `v2_kpi_1000_baseline.csv`.

## Limites et prochaine étape

Les prédictions V2 des 100 cas sont issues d'une revue manuelle, pas d'une exécution des prompts par un modèle. Pour le tirage de 1 000, les colonnes de prédiction V2 restent vides : le taux d'erreur V2, la comparaison appariée et le test de McNemar ne sont donc pas encore calculables.

Il faut produire des prédictions V2 valides sur ces mêmes 1 000 dossiers avant de conclure à une amélioration. Une taille d'échantillon de 1 000 augmente la précision, mais ne garantit pas à elle seule une différence statistiquement significative : cela dépend de l'écart entre méthodes et de leurs erreurs discordantes.

Les désaccords exacts du benchmark manuel de 100 cas sont listés dans `v2_remaining_errors.csv`.