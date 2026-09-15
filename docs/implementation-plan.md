# Plan d'implémentation

## Décisions de première version

- Une campagne et un poste, représentés par `campaigns` pour garder un modèle explicite sans introduire du multi-tenant.
- Questions à correction déterministe en production V1 : choix unique, choix multiple, vrai/faux et numérique. `TEXT` est accepté par le modèle mais marqué non scoré tant qu'aucune règle déterministe n'est définie.
- Attribution idempotente et une seule attribution par candidat dans la campagne.
- Résultats candidat configurables, masqués par défaut jusqu'à décision produit.

## Phases

### Phase 1 : fondation

- Créer les deux applications et la configuration par environnement.
- Ajouter Docker Compose, PostgreSQL, health check et migrations Alembic.
- Implémenter les modèles, enums, contraintes et indexes.
- Ajouter `.env.example`, README de démarrage et seed contrôlé.

**Sortie vérifiable** : migration vide puis migration initiale appliquée; health check opérationnel; seed idempotent.

### Phase 2 : identité et profils

- Hashage des mots de passe, tokens, dépendances FastAPI et contrôle de rôle.
- Inscription/login/logout/refresh.
- Profil candidat et upload CV via `StorageService`.
- Tests de permissions, validation MIME/taille et accès privé au CV.

**Sortie vérifiable** : un candidat ne peut appeler aucune route recruteur/admin.

### Phase 3 : banque de questions et blueprint

- CRUD catégories, compétences et questions.
- Validation humaine et séparation des payloads sensibles.
- CRUD blueprint et slots de compétence/difficulté/points.
- Tests de validation de blueprint et capacité de la banque.

### Phase 4 : variantes équitables

- Implémenter la sélection par slot, sans doublons.
- Générer des versions en brouillon.
- Produire un rapport de validation déterministe.
- Publier uniquement les versions valides.

**Sortie vérifiable** : deux variantes différentes ont les mêmes agrégats de catégorie, compétence, difficulté, durée et barème.

### Phase 5 : passage du test

- Attribution idempotente.
- Démarrage serveur et `expires_at`.
- Lecture des questions filtrées, autosave, navigation et indicateur à revoir.
- Soumission manuelle ou automatique sur expiration.
- Verrouillage transactionnel après soumission.

### Phase 6 : scoring et résultats

- `ScoringService` pur et testé.
- Agrégation par catégorie et compétence.
- Normalisation et niveaux configurables.
- Versionnement du calcul et audit de soumission.

### Phase 7 : dashboard recruteur

- KPIs, liste paginée, recherche, filtres et tri.
- Détail candidat, CV protégé, réponses et corrections.
- Comparaison de candidats avec limite raisonnable.
- Exports CSV/XLSX côté backend.

### Phase 8 : interface et qualité

- Construire les écrans React autour des contrats réels.
- États loading/empty/error/forbidden/404.
- Accessibilité clavier et responsive.
- Tests frontend des parcours login, candidat, soumission et dashboard.

### Phase 9 : préparation production

- Logs structurés, audit, CORS, limites d'upload et rate limiting ciblé.
- Dockerfiles de production, reverse proxy et documentation de déploiement.
- Vérification migrations, sauvegardes PostgreSQL et stockage privé.
- Revue de sécurité et tests d'intégration.

### Phase 10 : LLM optionnel

- Ajouter une interface `LLMService` et une implémentation désactivée par défaut.
- Stocker les propositions séparément des questions officielles.
- Exiger validation humaine avant promotion.
- Ne jamais connecter le LLM au parcours candidat ni au scoring.

## Critères de sortie V1

- Les cinq rôles d'usage demandés sont couverts : candidat, recruteur, administrateur, système de scoring et stockage privé.
- Les invariants d'équité sont testés par des cas nominaux et des cas d'échec.
- Une soumission répétée ou tardive ne modifie pas le résultat.
- Aucun endpoint candidat ne divulgue la correction.
- `docker compose up`, migrations, seed et tests sont documentés et reproductibles.
