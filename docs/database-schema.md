# Schéma de données

Les identifiants sont des UUID. Les timestamps sont stockés en UTC avec timezone. Les enums sont contrôlés côté application et, pour les valeurs critiques, par contraintes PostgreSQL.

## Tables principales

### `campaigns`

- `id`, `name`, `job_title`, `description`
- `status` : `DRAFT | OPEN | CLOSED`
- `duration_seconds`
- `show_result_to_candidate`
- `created_at`, `updated_at`

Une seule ligne active est attendue pour la campagne de ce produit.

### `users`

- `id`, `email` unique, `password_hash`
- `role` : `CANDIDATE | RECRUITER | ADMIN`
- `is_active`, `created_at`, `updated_at`, `last_login_at`

### `candidate_profiles`

- `user_id` PK/FK `users.id`
- `first_name`, `last_name`, `phone`
- `education`, `experience`, `bio`
- `created_at`, `updated_at`

### `cv_documents`

- `id`, `candidate_id` FK
- `original_filename`, `storage_key`, `mime_type`, `size_bytes`, `sha256`
- `uploaded_at`, `deleted_at`

Le contenu binaire n'est pas dans PostgreSQL.

### `categories`

- `id`, `code` unique, `label`, `display_order`, `is_active`

### `skills`

- `id`, `category_id` FK, `name`, `description`, `is_active`
- contrainte unique `(category_id, name)`

### `questions`

- `id`, `category_id` FK, `skill_id` FK
- `sub_skill`, `difficulty` : `EASY | MEDIUM | HARD`
- `question_type` : `SINGLE_CHOICE | MULTIPLE_CHOICE | TRUE_FALSE | NUMERIC | TEXT`
- `statement`, `explanation`, `points`, `recommended_time_seconds`
- `status` : `DRAFT | PENDING_REVIEW | VALIDATED | ARCHIVED`
- `source`, `validated_by`, `validated_at`, `created_at`, `updated_at`

Une question ne peut être sélectionnée pour une version officielle que si elle est `VALIDATED`.

### `question_options`

- `id`, `question_id` FK
- `option_key`, `label`, `is_correct`
- contrainte unique `(question_id, option_key)`

Les champs `is_correct` ne sont jamais renvoyés dans les réponses destinées au candidat.

### `test_blueprints`

- `id`, `campaign_id` FK
- `version`, `duration_seconds`, `is_active`
- `created_at`, `updated_at`

### `blueprint_slots`

- `id`, `blueprint_id` FK
- `category_id`, `skill_id` nullable pour les catégories sans compétence
- `difficulty`, `question_count`, `points_each`

La somme des slots définit le nombre total de questions et le score maximal.

### `test_versions`

- `id`, `campaign_id` FK, `blueprint_id` FK
- `code` (`A`, `B`, `C`), `status` : `DRAFT | VALIDATED | PUBLISHED | RETIRED`
- `total_questions`, `max_points`, `duration_seconds`
- `validation_report` JSONB, `published_at`, `created_at`

### `test_version_questions`

- `test_version_id` FK, `question_id` FK
- `position`, `category_id`, `skill_id`, `difficulty`, `points`
- PK composée `(test_version_id, question_id)` et unique `(test_version_id, position)`

Les attributs de mesure sont copiés au moment de la génération afin de préserver la traçabilité si la question est ensuite modifiée.

## Workflow de composition d'une version

Le recruteur/admin ne modifie jamais une version déjà publiée. Le workflow est :

```text
Question importée
	-> DRAFT
	-> validation humaine
	-> VALIDATED
	-> sélection dans une TestVersion DRAFT
	-> contrôle nombre/points/doublons
	-> publication
	-> TestVersion publiée immuable
	-> attribution au candidat
```

Endpoints de pilotage :

- `GET /api/v1/admin/test-versions` : liste les brouillons et versions publiées.
- `POST /api/v1/admin/test-versions` : crée une version brouillon pour une campagne.
- `PUT /api/v1/admin/test-versions/{id}/questions` : remplace la sélection de questions par des questions `VALIDATED`.
- `POST /api/v1/admin/test-versions/{id}/publish` : publie la version si elle contient au moins une question; l’ancienne version publiée de la campagne est retirée.

Une version publiée conserve ses liens `test_version_questions`. Les candidats déjà attribués continuent d’utiliser leur version, même si une nouvelle version est publiée ensuite.

### `candidate_tests`

- `id`, `campaign_id` FK, `candidate_id` FK, `test_version_id` FK
- `status` : `ASSIGNED | IN_PROGRESS | SUBMITTED | EXPIRED`
- `started_at`, `expires_at`, `submitted_at`
- `session_id`, `reconnections`, `created_at`, `updated_at`
- contrainte unique `(campaign_id, candidate_id)`

### `candidate_answers`

- `id`, `candidate_test_id` FK, `question_id` FK
- `answer_payload` JSONB, `marked_for_review`
- `answered_at`, `updated_at`
- contrainte unique `(candidate_test_id, question_id)`

Le payload est validé selon le type de question. Il est immuable après soumission.

### `candidate_scores`

- `id`, `candidate_test_id` FK unique
- `earned_points`, `maximum_points`, `normalized_score`
- `level`, `calculated_at`, `scoring_version`

### `candidate_score_breakdowns`

- `id`, `candidate_score_id` FK
- `dimension_type` : `CATEGORY | SKILL`
- `dimension_id`, `label`
- `earned_points`, `maximum_points`, `normalized_score`

### `audit_events`

- `id`, `actor_user_id` nullable, `event_type`, `entity_type`, `entity_id`
- `metadata` JSONB, `created_at`, `ip_hash`

## Indexes

- `users(email)` unique.
- `candidate_tests(campaign_id, status)`.
- `candidate_tests(candidate_id, campaign_id)` unique.
- `candidate_scores(normalized_score)`.
- `questions(status, category_id, skill_id, difficulty)`.
- `candidate_profiles(last_name, first_name)`.
- `audit_events(entity_type, entity_id, created_at)`.

## Invariants

1. Une attribution possède exactement une version publiée.
2. Une réponse ne peut exister que pour une question de la version attribuée.
3. Une soumission ne peut être modifiée, même par répétition de requête.
4. Le score maximal est la somme des points figés dans `test_version_questions`.
5. Chaque variante publiée satisfait le blueprint associé.
6. Les calculs de score sont reproductibles avec `scoring_version`.
