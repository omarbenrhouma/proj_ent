# Plateforme d'évaluation de candidats

Plateforme dédiée à une campagne de recrutement unique, avec variantes de test équivalentes, scoring déterministe et dashboard recruteur.

## Documentation de conception

- [Architecture technique](docs/architecture.md)
- [Schéma de données](docs/database-schema.md)
- [Contrats API](docs/api-contract.md)
- [Plan d'implémentation](docs/implementation-plan.md)

## État actuel

La première tranche fonctionnelle est disponible :

- inscription et connexion candidat avec JWT;
- campagne et version de test seedées;
- attribution idempotente;
- timer serveur avec expiration;
- sauvegarde des réponses;
- scoring déterministe et résultats par catégorie;
- interface React responsive pour le parcours candidat;
- Docker Compose avec PostgreSQL, backend et frontend.

Les écrans recruteur/admin, les CV privés, les blueprints configurables, les variantes avancées, les exports et les migrations Alembic restent les prochaines tranches du plan. Ils ne sont pas simulés dans cette V1.

## Lancer localement sans Docker

```powershell
cd backend
python -m pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000
```

Dans un autre terminal :

```powershell
cd frontend
npm install
$env:VITE_API_URL = "http://localhost:8000"
npm run dev
```

Créer un compte depuis l'écran candidat, puis démarrer le test. Le compte `admin@example.com` / `Admin123!` est réservé au développement et n'est pas encore connecté à un dashboard d'administration.

## Lancer avec Docker

```powershell
docker compose up --build
```

Frontend : `http://localhost:4173`  
API et documentation OpenAPI : `http://localhost:8000/docs`  
Health check : `http://localhost:8000/health`

## Tests

```powershell
cd backend
pytest -q
cd ../frontend
npm run build
```

## Importer une banque de questions

Les QCM externes sont importés comme brouillons : ils doivent être relus et validés par un administrateur avant toute publication dans une version de test.

```powershell
cd backend
python import_questions.py C:\Users\omarb\Downloads\questions_entretien_complet.json
```

### Processus candidat simplifié

1. Créer un compte et déposer son CV.
2. Démarrer un seul QCM de 25 minutes.
3. Répondre à 15 questions à choix unique : Technique (6), Métier Retail (3), Analyse (2), Logique (4).
4. Soumettre et consulter le résultat si la campagne l’autorise.

La banque complète reste disponible à l’administration ; le candidat ne voit jamais les corrections ni les questions non sélectionnées.
