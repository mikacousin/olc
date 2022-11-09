# Bases du système

## Fenêtre principale
![Fenêtre principale](pictures/main_window.png)
### Channels
Affiche les niveaux des circuits envoyés.
> Les circuits non patchés auront un niveau à 0

Trois modes d'affichage :
- All : affiche tous les circuits
- Patched : affiche les circuits patchés
- Active : affiche les circuits actifs. C'est à dire, les circuits avec une valeur dans la mémoire actuelle ou la suivante et les circuits sélectionnés.
### Main Playback
Affiche la séquence principale.
![Séquence principale](pictures/main_playback.png)
En haut, avec le fond doré, la mémoire en scène.  
En dessous, avec le fond gris, la prochaine mémoire.  
Ensuite, une représentation graphique de la transition entre les deux mémoires.  
Enfin, les mémoires suivantes.
#### Détails des colonnes :
- Step : numéro de pas dans la séquence
- Cue : numéro de la mémoire
- Text : texte du pas de séquence
- Wait : temps avant de lancer automatiquement le pas suivant
- Delay Out : délais d'attente avant de baisser les niveaux de circuits
- Out : temps de la baisse des niveaux de circuits
- Delay In : délais d'attente avant de monter les niveaux de circuits
- In : temps de monté des niveaux de circuits
- Channel Time : Nombre de circuits avec un channel time
> Tous les temps sont exprimés en secondes.

## Divers
- La partie active est entourée d'un cadre doré.
- Pour effacer le buffer clavier : 'Backspace'
- Pour fermer un onglet : clique souris sur la croix de l'onglet ou 'Esc'