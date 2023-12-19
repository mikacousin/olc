# Open Sound Control
Par défaut, olc écoute sur le port 7000 et envoie les infos à l'adresse IP 127.0.0.1, port 9000.  
Ceci peut être modifié dans les Paramètres.

Vous pouvez [télécharger une télécommande](https://github.com/mikacousin/olc/raw/assets/olc.tosc) basée sur [TouchOSC](https://hexler.net/touchosc).

<style>
.tablelines table, .tablelines td, .tablelines th {
        border: 1px solid black;
        }
</style>
Chemin OSC | Valeur | Commande
---------- | ------ | --------
/olc/key/go | | Go
/olc/key/seq+ | | Seq+
/olc/key/seq- | | Seq-
/olc/key/pause | | Pause
/olc/key/goback | | Go Back
/olc/key/1 | | 1
/olc/key/2 | | 2
/olc/key/3 | | 3
/olc/key/4 | | 4
/olc/key/5 | | 5
/olc/key/6 | | 6
/olc/key/7 | | 7
/olc/key/8 | | 8
/olc/key/9 | | 9
/olc/key/0 | | 0
/olc/key/. | | .
/olc/key/clear | | Efface la ligne de commande
/olc/key/channel | | Channel
/olc/key/thru | | Thru
/olc/key/+ | | +
/olc/key/- | | -
/olc/key/all | | All
/olc/key/level | | @
/pad/+% | | +%
/pad/-% | | -%
/olc/key/full | | Full
/olc/fader/pageupdate | | Envoie les infos de la page de faders
/olc/fader/page | int (de 1 à 10) | Envoie le numéro de la page de faders
/olc/fader/1/x/label | str | Envoie le nom du fader n°x (de 1 à 10)
/olc/fader/page+ | | Passe à la page de faders suivante
/olc/fader/page- | | Passe à la page de faders précédente
/olc/fader/1/x/level | int (de 0 à 255) | Niveau du fader n°x
/olc/fader/1/x/flash | int (0 ou 1) | Flash le fader n°x
/olc/patch/output | | Sélectionne un Output à patcher
/olc/patch/thru | | Output Thru à patcher
/olc/patch/+ | | Ajoute un Output à patcher
/olc/patch/- | | Enlève un Output à patcher
/olc/patch/channel | | Patch les Outputs sélectionnés au circuit entré dans la ligne de commande
/olc/patch/selected_outputs | | Envoie la liste des outputs sélectionnés
