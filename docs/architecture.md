# Architecture technique

## Périmètre

L'application gère une seule campagne de recrutement pour un seul poste. Elle n'est pas multi-tenant et ne contient pas de notion de catalogue d'entreprises ou de postes multiples.

Le backend est l'autorité pour l'authentification, l'autorisation, le timer, l'attribution des variantes, la sauvegarde des réponses et le scoring. Le frontend ne fait qu'afficher l'état fourni par l'API.

## Stack

- Frontend : React, Vite, TypeScript, Tailwind CSS, React Router, TanStack Query.
- Backend : Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- Données : PostgreSQL 16.
- Fichiers : abstraction `StorageService`, stockage local en développement et object storage compatible S3 en production.
- Tests : Pytest/httpx côté backend, Vitest/Testing Library côté frontend.
- Déploiement local : Docker Compose avec frontend, backend et PostgreSQL.

Redis n'est pas requis en V1. Il ne sera ajouté que si un besoin concret de rate limiting distribué, de cache ou de tâches asynchrones apparaît.

## Principes d'architecture

1. **Scoring déterministe** : `ScoringService` corrige les types de questions supportés sans appel LLM.
2. **Équivalence par blueprint** : une variante est valide uniquement si elle satisfait exactement la même matrice de compétences, catégories, difficultés, points et durée.
3. **Immutabilité après publication** : une version publiée et une attribution commencée ne sont plus modifiables.
4. **Autorisation serveur** : chaque route protégée vérifie le rôle et la propriété de la ressource.
5. **Réponses minimales au candidat** : les bonnes réponses et explications ne sont jamais incluses dans les payloads candidat avant soumission.
6. **LLM découplé** : un port `LLMService` peut produire des propositions administratives, mais aucune proposition ne devient question officielle sans validation humaine.
7. **Auditabilité** : les événements métier importants sont horodatés et auditables.

## Modules backend

```text
backend/app/
├── main.py
├── api/
│   ├── deps.py
│   └── routes/
├── core/              # configuration, logging, erreurs
├── db/                # session, base, migrations
├── models/            # SQLAlchemy
├── schemas/           # Pydantic request/response
├── repositories/      # accès aux données
├── services/          # auth, tests, scoring, storage, export
├── security/          # hash, JWT, rôles
└── integrations/      # LLM optionnel, object storage
```

Services métier principaux :

- `AuthService` : inscription candidat, connexion, rotation/expiration des tokens.
- `CandidateService` : profil et CV.
- `QuestionBankService` : questions, compétences, validation.
- `BlueprintService` : matrice et vérification de capacité de la banque.
- `VariantGenerationService` : sélection contrôlée et validation atomique.
- `CandidateTestService` : attribution idempotente, démarrage, réponses, expiration, soumission.
- `ScoringService` : correction et agrégations globales, catégorie et compétence.
- `RecruiterReportingService` : KPIs, recherche paginée, comparaison, CSV/XLSX.

## Frontend

```text
frontend/src/
├── app/
├── components/
├── layouts/
├── pages/
│   ├── auth/
│   ├── candidate/
│   ├── recruiter/
│   └── admin/
├── services/          # client HTTP et endpoints
├── hooks/
├── store/
├── types/
├── utils/
└── routes/
```

Le layout candidat reste minimal. Le layout recruteur/admin contient la navigation latérale. Le test utilise une vue dédiée sans sidebar, avec timer serveur recalculé après chaque réponse ou reconnexion.

## Flux critiques

### Attribution

1. Une campagne possède une liste de versions publiées.
2. `CandidateTestService.assign_if_missing()` verrouille la campagne et crée une attribution unique.
3. Une reconnexion retrouve la même attribution par contrainte unique sur `candidate_id` et `campaign_id`.

### Démarrage et timer

1. Le serveur écrit `started_at` et `expires_at` dans une transaction.
2. Toutes les écritures de réponse vérifient `status = IN_PROGRESS` et `now < expires_at`.
3. Une soumission après expiration est traitée comme soumission automatique.
4. `submitted_at` est fixé une seule fois et le scoring est exécuté dans la même transaction logique.

### Génération d'une variante

1. Le blueprint produit des slots `(category, skill, difficulty, points)`.
2. Le générateur sélectionne uniquement des questions validées compatibles.
3. Il refuse les doublons et les ensembles incomplets.
4. La variante est validée avant publication et ses questions sont figées.

## Sécurité et confidentialité

- Mot de passe Argon2id ou bcrypt via Passlib.
- JWT de courte durée avec refresh token révocable, ou cookies HttpOnly selon le déploiement.
- CORS par liste blanche issue de l'environnement.
- Taille, extension et type MIME du CV contrôlés côté serveur; nom de fichier généré côté stockage.
- CV servi par endpoint autorisé, jamais par URL publique.
- ORM et paramètres typés contre l'injection SQL.
- Logs sans mot de passe, token, CV ou réponse sensible.
- Rate limiting applicatif sur login et endpoints d'upload si nécessaire.
- Les événements de visibilité d'onglet sont des indicateurs, jamais une décision automatique.

## Déploiement

```text
frontend (Nginx/static) -> backend (Uvicorn/Gunicorn) -> PostgreSQL
                                      └-> storage privé des CV
```

Les secrets et URLs sont fournis par l'environnement. Les migrations Alembic sont exécutées au démarrage du déploiement, et `create_all()` n'est pas utilisé comme mécanisme de production.
