# Contrats API V1

Préfixe : `/api/v1`. Les réponses d'erreur utilisent une forme stable :

```json
{
  "error": {
    "code": "TEST_ALREADY_SUBMITTED",
    "message": "Le test a déjà été soumis.",
    "details": {}
  }
}
```

## Authentification

- `POST /auth/register` : `{ email, password, first_name, last_name }` -> utilisateur candidat.
- `POST /auth/login` : `{ email, password }` -> access token + refresh token.
- `POST /auth/refresh` : renouvelle l'access token.
- `POST /auth/logout` : révoque le refresh token courant.
- `GET /auth/me` : utilisateur courant et rôle.

## Candidat

- `GET /candidate/profile` -> profil et métadonnées CV.
- `PUT /candidate/profile` -> met à jour les informations personnelles.
- `POST /candidate/cv` multipart -> valide et stocke le CV.
- `GET /candidate/test` -> état, version, durée et progression; aucune correction.
- `POST /candidate/test/start` -> démarre idempotemment et renvoie `started_at`, `expires_at`.
- `GET /candidate/test/questions` -> questions sans bonnes réponses, avec réponses déjà sauvegardées.
- `PUT /candidate/test/answers/{question_id}` -> sauvegarde une réponse idempotente.
- `POST /candidate/test/submit` -> soumission atomique et score selon la visibilité configurée.
- `GET /candidate/result` -> résultat du candidat si `show_result_to_candidate` est actif.

## Recruteur

- `GET /recruiter/dashboard` -> KPIs agrégés.
- `GET /recruiter/candidates?page=1&page_size=25&search=&status=&level=&sort=` -> liste paginée.
- `GET /recruiter/candidates/{candidate_id}` -> profil, CV metadata, test et scores.
- `GET /recruiter/candidates/{candidate_id}/answers` -> réponses, correction et points.
- `GET /recruiter/cv/{document_id}/download` -> téléchargement autorisé en flux privé.
- `POST /recruiter/comparison` `{ candidate_ids: [...] }` -> tableau comparatif.
- `GET /recruiter/export?format=csv|xlsx` -> export filtré avec content disposition contrôlé.

## Administration

- `GET /admin/categories`, `POST`, `PUT`.
- `GET /admin/skills`, `POST`, `PUT`.
- `GET /admin/questions` avec filtres et pagination.
- `POST /admin/questions`, `PUT /admin/questions/{id}`, `DELETE /admin/questions/{id}`.
- `POST /admin/questions/{id}/validate` -> validation humaine.
- `GET /admin/blueprints`, `POST /admin/blueprints`, `PUT /admin/blueprints/{id}`.
- `POST /admin/test-versions/generate` `{ blueprint_id, code }` -> version contrôlée en brouillon.
- `POST /admin/test-versions/{id}/validate` -> rapport d'équivalence.
- `POST /admin/test-versions/{id}/publish` -> publication si validation réussie.
- `GET /admin/audit-events` -> journal filtré.

## Santé

- `GET /health` -> `{ "status": "ok" }`.

## Règles HTTP

- `401` absence ou invalidité d'identité.
- `403` rôle insuffisant.
- `404` ressource absente ou non visible pour l'appelant.
- `409` conflit d'état, par exemple soumission déjà effectuée.
- `422` données invalides.
- `413` CV trop volumineux.
- `429` limite de requêtes dépassée.

## Payload candidat vs administration

Les endpoints candidat ne renvoient jamais `is_correct`, `correct_answer`, les explications, ni les scores d'autres candidats. Les endpoints recruteur/admin peuvent les renvoyer selon le rôle et l'action.
