# Séquences
Une séquence est une succession de pas qui contiennent des mémoires.

Open Lighting Console gère une séquence principale, les autres sont utilisées pour les chenillards.

![Édition de séquences](pictures/sequences.png)

Cet onglet est divisé en 3 parties.
- En haut : la liste des séquences
	- Seq : numéro de la séquence
	- Type : Normal (séquence principale) ou Chaser (toutes les autres)
	- Name : nom de la séquence
- Au milieu : l'affichage des circuits
- En bas : la liste des pas
	- Step : numéro de pas
	- Cue : numéro de mémoire
	- Text : texte associé au pas de séquence
	- Wait : temps avant de lancer automatiquement le pas suivant
	- Delay Out : délai d'attente avant de baisser les niveaux de circuits
	- Out : temps de la baisse des niveaux de circuits
	- Delay In : délai d'attente avant de monter les niveaux de circuits
	- In : temps de monté des niveaux de circuits
	- Channel Time : nombre de circuits avec un channel time

> Tous les temps sont exprimés en secondes.

## Éditions de séquences

Ouvrir l'onglet : [Ctrl + T] ou 'Séquences' dans le menu principal.

### Créer un nouveau chenillard :
[Maj + N]

### Sélectionner une séquence :
- Cliquer sur la séquence avec la souris
- [Maj + Q] pour passer à la séquence suivante

### Créer un nouveau pas de séquence et une mémoire vide :
[Maj + R] : créer un pas à la suite de celui sélectionné et une nouvelle mémoire qui lui est associée
Numéro puis [Maj + R] : créer un pas de séquence, la mémoire avec le Numéro et l'insérer dans la séquence

### Sélectionner un pas de séquence :
- Cliquer sur le pas avec la souris
- [W] : passer au pas suivant
- [Q] : passer au pas précédent

### Éditer les temps d'un pas de séquence :
Cliquer sur le temps à modifier, entrer la valeur et valider avec [Entrée]

### Modifier le texte d'un pas de séquence :
Cliquer sur le champ de texte, taper le nouveau texte et valider avec [Entrée]

### Modifier une mémoire :
Sélectionner les circuits désirés.
- Valeur puis [=] : Mettre à la valeur
- [!] : Augmenter la valeur
- [:] : Baisser la valeur
- [Maj + U] : Mettre à jour la mémoire

### Supprimer un pas de séquence :
[Suppr]
> Ne supprime que le pas de séquence, la mémoire associée est conservée.