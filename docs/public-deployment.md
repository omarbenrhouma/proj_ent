# Déploiement public gratuit

Cette configuration cible Render : une API FastAPI, PostgreSQL et un site React
statique. C'est adapté à une démonstration publique ; les offres gratuites ne
sont pas prévues pour des données de recrutement durables.

1. Créez un dépôt GitHub privé et envoyez ce projet.
2. Sur Render, choisissez **New > Blueprint**, sélectionnez le dépôt puis
   validez `render.yaml`.
3. Après la création de l'API, copiez son URL publique, par exemple
   `https://quiz-data-analyst-api.onrender.com`.
4. Dans les variables du service web statique, définissez
   `VITE_API_URL` avec cette URL, puis redéployez le site.
5. Dans les variables de l'API, définissez `CORS_ORIGINS` avec l'URL exacte du
   site statique, par exemple `https://quiz-data-analyst-web.onrender.com`.
6. Créez les comptes de gestion et chargez la banque de questions après le
   premier déploiement. Ne publiez jamais les mots de passe de démonstration.

Vérifications : ouvrez `/health`, puis `/docs`, connectez-vous et créez un
compte candidat. Configurez un domaine personnalisé seulement après ces tests.

## Limites de la formule gratuite

Le service API peut se mettre en veille et la base gratuite est temporaire.
Les CV ne doivent pas être conservés en production dans `STORAGE_PATH` : le
disque des services gratuits est éphémère. Avant toute utilisation réelle,
remplacez ce stockage par un bucket privé S3 ou Cloudflare R2 et prenez une base
PostgreSQL persistante.
