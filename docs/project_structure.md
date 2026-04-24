# Organisation du projet MLOps

Ce document explique pourquoi chaque dossier et fichier existe, son rôle dans le workflow MLOps, et à quoi il ressemblera une fois rempli.

---

## Vue d'ensemble

```
PyCharmMiscProject/
├── data/
│   ├── raw/
│   └── processed/
├── models/
├── steps/
│   ├── ingest.py
│   ├── preprocess.py
│   ├── train.py
│   └── evaluate.py
├── flows/
│   └── training_flow.py
├── api/
│   └── main.py
├── docs/
├── dvc.yaml
├── params.yaml
└── requirements.txt
```

---

## `data/`

### Pourquoi ce dossier ?
En ML classique, on charge les données directement dans le notebook. En MLOps, les données sont **versionnées** comme du code. Ce dossier est tracké par DVC, pas par Git (les fichiers peuvent être lourds). Git ne voit que les métadonnées `.dvc`.

### `data/raw/`
Données brutes, telles qu'elles viennent de la source. **On ne les modifie jamais.** Si on a besoin de corriger quelque chose, ça se fait en preprocessing — pas ici. C'est la source de vérité.

Exemple de contenu : `california_housing.csv`

### `data/processed/`
Données après nettoyage et transformation : features encodées, valeurs manquantes traitées, train/test splitté. Ces fichiers sont le résultat direct de `steps/preprocess.py`.

Exemple de contenu : `X_train.csv`, `X_test.csv`, `y_train.csv`, `y_test.csv`

---

## `models/`

### Pourquoi ce dossier ?
Le modèle entraîné est sauvegardé ici sous forme de fichier (`.pkl`, `.joblib`…). Comme `data/`, ce dossier est tracké par **DVC**, pas Git. Ça permet de savoir exactement quel modèle correspond à quel dataset et quels hyperparamètres.

Exemple de contenu : `linear_regression.pkl`

---

## `steps/`

### Pourquoi ce dossier ?
C'est le cœur du code ML. Chaque fichier représente **une étape du pipeline**, isolée et testable indépendamment. En MLOps, on découpe le pipeline en étapes discrètes plutôt qu'un seul script monolithique. Ça permet de :
- rejouer uniquement l'étape qui a changé (DVC fait ça automatiquement)
- tester chaque étape séparément
- comprendre d'un coup d'œil ce que fait le pipeline

### `steps/ingest.py`
Charge les données depuis la source et les dépose dans `data/raw/`. C'est le point d'entrée du pipeline.

Ce qu'il fera : télécharger ou charger le dataset California Housing, le sauvegarder en CSV dans `data/raw/`.

### `steps/preprocess.py`
Prend les données brutes de `data/raw/`, les nettoie, les transforme, les splitte en train/test, et sauvegarde le résultat dans `data/processed/`.

Ce qu'il fera : normalisation des features, gestion des valeurs manquantes, split 80/20.

### `steps/train.py`
Prend les données de `data/processed/`, lit les hyperparamètres dans `params.yaml`, entraîne le modèle, et le sauvegarde dans `models/`.

Ce qu'il fera : instancier un `LinearRegression`, l'entraîner sur `X_train`, sauvegarder le modèle.

### `steps/evaluate.py`
Charge le modèle depuis `models/` et les données de test depuis `data/processed/`, calcule les métriques (RMSE, MAE, R²), et les écrit dans un fichier de résultats.

Ce qu'il fera : produire un fichier `metrics.json` avec les scores — DVC peut lire ce fichier pour comparer les runs.

---

## `flows/`

### Pourquoi ce dossier ?
Les fichiers dans `steps/` sont des fonctions ML isolées. `flows/` contient l'**orchestration** : dans quel ordre appeler ces étapes, comment gérer les erreurs, comment logger l'exécution.

C'est ici qu'intervient **Prefect**.

### `flows/training_flow.py`
Définit le pipeline complet comme un **Flow Prefect** : une séquence de tasks (ingest → preprocess → train → evaluate). Prefect ajoute :
- un historique visuel des runs dans son UI
- la gestion des retries en cas d'échec
- des logs structurés pour chaque task

Exemple de ce à quoi ça ressemblera :
```python
@flow
def training_flow():
    ingest()
    preprocess()
    train()
    evaluate()
```

La différence avec un simple script qui appelle les fonctions : Prefect sait si une task a échoué, peut la relancer, et garde une trace de chaque exécution.

---

## `api/`

### Pourquoi ce dossier ?
Un modèle entraîné ne sert à rien s'il ne peut pas être appelé. `api/` expose le modèle via une **API REST** construite avec FastAPI. N'importe quelle application peut envoyer des données et recevoir une prédiction en retour.

### `api/main.py`
Définit un endpoint `/predict` qui :
1. reçoit des features en JSON
2. charge le modèle depuis `models/`
3. retourne la prédiction

Exemple de ce à quoi ça ressemblera :
```
POST /predict
Body: {"MedInc": 8.3, "HouseAge": 41.0, ...}
Response: {"prediction": 4.526}
```

---

## `dvc.yaml`

### Pourquoi ce fichier ?
C'est la **définition du pipeline pour DVC**. Il décrit chaque étape (stage) : quel script lancer, quels fichiers il lit en entrée (deps), quels fichiers il produit en sortie (outs).

Grâce à ce fichier, DVC peut :
- rejouer uniquement les étapes dont les inputs ont changé
- versionner automatiquement les outputs (data, modèles, métriques)
- reproduire un run complet avec `dvc repro`

Exemple de ce à quoi ça ressemblera :
```yaml
stages:
  ingest:
    cmd: python steps/ingest.py
    outs:
      - data/raw/california_housing.csv

  preprocess:
    cmd: python steps/preprocess.py
    deps:
      - data/raw/california_housing.csv
    outs:
      - data/processed/X_train.csv
      - data/processed/X_test.csv

  train:
    cmd: python steps/train.py
    deps:
      - data/processed/X_train.csv
      - params.yaml
    outs:
      - models/linear_regression.pkl
    params:
      - params.yaml:
          - model.alpha

  evaluate:
    cmd: python steps/evaluate.py
    deps:
      - models/linear_regression.pkl
      - data/processed/X_test.csv
    metrics:
      - metrics.json
```

Si seul `params.yaml` change (ex: tu modifies l'alpha), DVC relance uniquement `train` et `evaluate` — pas `ingest` ni `preprocess`.

---

## `params.yaml`

### Pourquoi ce fichier ?
Centralise tous les **hyperparamètres et configurations** du projet. Au lieu d'avoir des valeurs en dur dans le code, tout est ici. DVC lit ce fichier et sait quand un paramètre a changé pour décider si un stage doit être relancé.

Exemple de ce à quoi ça ressemblera :
```yaml
data:
  test_size: 0.2
  random_state: 42

model:
  alpha: 1.0

evaluate:
  metrics: [rmse, mae, r2]
```

Changer `test_size` ici et relancer `dvc repro` → DVC relance automatiquement preprocess, train et evaluate.

---

## `requirements.txt`

Liste toutes les dépendances Python du projet avec leurs versions. Permet à n'importe qui (ou un serveur CI/CD) de recréer l'environnement exactement avec `pip install -r requirements.txt`.

Exemple de ce à quoi ça ressemblera :
```
scikit-learn==1.4.0
pandas==2.2.0
numpy==1.26.0
dvc==3.67.1
prefect==3.6.28
fastapi==0.136.1
uvicorn==0.46.0
```

---

## Ce qui est dans `.gitignore` mais pas dans `.dvcignore`

| Élément | Git | DVC |
|---|---|---|
| `data/raw/` | ignoré (trop lourd) | tracké |
| `data/processed/` | ignoré | tracké |
| `models/` | ignoré | tracké |
| `metrics.json` | versionné | lu comme métrique |
| `.venv/` | ignoré | ignoré |
| `dvc.yaml` | versionné | — |
| `params.yaml` | versionné | lu comme paramètre |

---

## Résumé du flux complet

```
params.yaml ──┐
              ▼
ingest → preprocess → train → evaluate → metrics.json
              │                   │
         data/raw/           models/*.pkl
         data/processed/          │
                                  ▼
                              api/main.py → endpoint /predict
```

DVC orchestre et version les données/modèles. Prefect orchestre l'exécution et les logs. FastAPI expose le résultat final.