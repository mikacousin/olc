# Fichiers
Open Lighting Console utilise son propre format de fichier (extension .olc) pour enregistrer les données.

De plus, il peut importer et exporter les fichiers ASCII Light Cue. Ce sont les fichiers que l'on peut enregistrer avec un Congo ou DLight par exemple.

**Afin de ne pas perdre d'informations, il est très fortement conseillé de travailler sur des copies de vos fichiers ASCII originaux. En effet, olc n'enregistrera pas les données qui ne lui sont pas utiles mais qui peuvent l'être sur d'autres systèmes.**

## Nouveau
'Nouveau' dans le menu principal.

Un nouveau projet vide sera créé. Tout est effacé, le patch est remis droit.

**Attention, le travail en cours est définitivement perdu !**

## Ouvrir
[Ctrl + O] ou 'Fichier > Ouvrir' dans le menu principal.

**Attention, le travail en cours est définitivement perdu !**

> Il est également possible d'ouvrir directement un fichier à l'ouverture en le passant en paramètre de la ligne de commande, par exemple :
> ```bash
> $ olc fichier.olc
> ```

## Enregistrer
[Ctrl + S] ou 'Fichier > Enregistrer' dans le menu principal.

Enregistre dans le fichier ouvert.

## Enregistrer sous
[Maj + Ctrl + S] ou 'Fichier > Enregistrer sous' dans le menu principal.

Enregistre dans un nouveau fichier.

## Importer
[Maj + Ctrl + O] ou 'Fichier > Importer' dans le menu principal.

Il est possible d'importer les fichiers au formats olc et ASCII Light Cue.  
De plus, après analyse du fichier, olc propose de remplacer, fusionner ou ignorer les données des éléments importés.

## Exporter ASCII
'Fichier > Exporter ASCII' dans le menu principal

Exporte les données au format ASCII.