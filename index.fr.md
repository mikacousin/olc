[English](index.md)

![Window](https://raw.githubusercontent.com/mikacousin/olc/assets/olc.png)

## Fonctionnalités
- Utilise [Open Lighting Architecture](https://www.openlighting.org/ola/) pour la prise en charge DMX
- Syntaxe de type Notation polonaise inverse [NPI](https://fr.wikipedia.org/wiki/Notation_polonaise_inverse)
- Ouvre / Enregistre les fichier ASCII (Congo/Cobalt et DLight par exemple)
- Patch / Dépatch par circuits ou par adresses
- Une séquence principale
- Chasers (comme Séquences supplémentaires)
- Groupes
- Masters
- Suivit de circuits
- Console virtuelle avec configuration simple des contrôleurs MIDI
- [Open Sound Control](https://fr.wikipedia.org/wiki/Open_Sound_Control)

## Documentation 
> Note:  
> `Boutons` sont les boutons de la console. Ce sont ceux présents sur la console virtuelle.  
> [touche] sont les raccourcis clavier. Les combinaisons de touches sont représentés ainsi [touche1 + touche2].  
> Par exemple, le bouton `Ch` s'active avec la touche [C] du clavier, `Thru` avec [>]... Pour connaître les raccourcis clavier, ouvrez le menu correspondant directement d	ans l'application.

### Console virtuelle
Vous pouvez l'ouvrir avec le menu Burger ou avec [Shift + Ctrl + C]
![VirtualConsole](https://raw.githubusercontent.com/mikacousin/olc/assets/virtual_console.png)

### Fenêtre principale
#### Sélectionner des circuits
- Sélectionner le circuit 1 : `1 Ch`
- Sélectionner les circuits de 1 à 10 : `1 Ch 10 Thru`
- Sélectionner les circuits 1, 3 et 5 : `1 Ch 3 + 5 +`
- Sélectionner les circuits de 1 à 5 et de 7 à 10 : `1 Ch 10 Thru 6 -`

#### Donner un niveau à des circuits
- Circuit 1 à Full : `1 Ch 100 @`
- Circuits de 1 à 5 à 50% : `1 Ch 5 Thru 50 @`
- Ajouter 5% aux circuits sélectionnés : `+%`
- Retirer 5% aux circuits sélectionnés : `-%`
> les valeurs de `+%` et `-%` peuvent être modifiées dans les Paramètres

#### Modifier des Pas et des Mémoires
Une mémoire stocke les niveaux des circuits
- Enregistrer une mémoire avec le prochain numéro de libre :  `Record`
- Enregistrer la mémoire 10 :  `10 Record`
- Mettre à jour la mémoire active : `Update`  
Un pas contient une mémoire et les temps
- Définir un temps de montée de 3s : [3], [Shift + I]
- Définir un temps de descente de 2s : [2], [Shift + O]
- Définir un temps de montée et de descente de 10s : [10], [Shift + T]
- Définir un délai sur la montée de 1s : [1], [Shift + K]
- Définir un délai sur la descente de 2s : [2], [Shift + L]
- Définir un délai sur la montée et la descente de 3s : [3], [Shift + D]
- Définir un wait de 0.5s : [0.5], [Shift + W]

#### Se déplacer dans la séquence principale
- Go: `Go`
- Sauter au prochain pas : `Seq+`
- Sauter au pas précédent : `Seq-`
- Aller à la mémoire 2.0: `2 Goto`
- Revenir au pas précédent :  `Go Back`
> Le temps du Go Back Time peut être modifié dans les Paramêtres

### Open Lighting Architecture
Au démarrage, Open Lighting Console lancera automatiquement olad, si il ne tourne pas déjà.  
Pour configurer OLA, utiliser l'interface web en suivant le lien [http://localhost:9090](http://localhost:9090) une fois olad lancé.

### Contrôleurs MIDI
Configurer ses contrôleurs pour qu'ils envoient des Notes MIDI pour les boutons et des Control Changes MIDI pour les faders, les rotatifs et les contrôleurs.

- Activer les contrôleurs MIDI dans les Paramètres.
- Ouvrir la console virtuelle, activer le bouton MIDI pour passer en mode apprentissage.
- En mode apprentissage, sélectionner un objet (le bouton Go par exemple) et appuyer sur un bouton d'un contrôleur MIDI.
- Il est possible de configurer autant d'objets que voulu (boutons, faders, ...)
- Appuyer sur le bouton MIDI pour quitter le mode apprentissage
- Utiliser les boutons et les faders des contrôleurs MIDI
> Note:  
> Le mapping MIDI est enregistré par olc dans les fichiers ASCII.

### Open Sound Control
Par défaut, olc écoute le port 7000 et envoie les infos à l'adresse IP 10.0.0.3, port 9000.  
Ceci peut être modifié dans les Paramètres.
<style>
.tablelines table, .tablelines td, .tablelines th {
        border: 1px solid black;
        }
</style>
Chemin OSC | Valeur | Commande
---------- | ------ | --------
/seq/go | 1 | Go
/seq/plus | 1 | Seq+
/seq/moins | 1 | Seq-
/pad/1 | | 1
/pad/2 | | 2
/pad/3 | | 3
/pad/4 | | 4
/pad/5 | | 5
/pad/6 | | 6
/pad/7 | | 7
/pad/8 | | 8
/pad/9 | | 9
/pad/9 | | 0
/pad/dot | | .
/pad/clear | | C
/pad/channel | | Ch
/pad/thru | | Thru
/pad/plus | | +
/pad/moins | | -
/pad/all | | All
/pad/level | | @
/pad/pluspourcent | | +%
/pad/moinspourcent | | -%
/pad/ff | | Full
/subStick/flash | master(1-40), niveau(0-255) | Flash du Master
/subStick/level | master(1-40), niveau(0-255) | Master au niveau
