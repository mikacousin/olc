# Contrôleurs MIDI
Configurer les contrôleurs pour qu'ils envoient :
- des Notes pour les boutons,
- des Control Changes pour les rotatifs et les contrôleurs
- des Control Changes ou des Pitchwheel pour les faders

Le mapping MIDI par défaut correspond au mode Makie Control, les contrôleurs configurés ainsi sont pris en charge directement.

Ouvrir les paramètres MIDI d'olc, activer le(s) contrôleur(s) dans MIDI In et choisir le mode utilisé par le contrôleur pour les rotatifs.
- Mode Relative1 : Rotatifs infinis. Valeurs de 0 à 64 dans un sens, de 127 à 65 dans l'autre.
- Mode Relative2 : Rotatifs infinis. Valeurs de 65 à 127 dans un sens, de 63 à 0 dans l'autre.
- Mode Relative3 (Makie) : Rotatifs infinis. Valeurs de 0 à 64 dans un sens, valeurs de 65 à 127 dans l'autre.
- Mode Absolute : Pour les rotatifs classiques non infinis. Valeurs de 0 à 127. Attention, ce mode ne fonctionne pas pour la roue de le console virtuelle.

> Note:  
> Tous les rotatifs d'un contrôleur doivent être configurés dans le même mode.

Activer également le(s) contrôleur(s) dans MIDI Out pour avoir le retour d'info sur le matériel le supportant (faders motorisés, LED, ...)

Ensuite :
- Ouvrir la console virtuelle, activer le bouton MIDI pour passer en mode apprentissage.
- En mode apprentissage, sélectionner un objet (le bouton Go par exemple) et appuyer sur un bouton d'un contrôleur MIDI.
- Il est possible de configurer autant d'objets que voulu (boutons, faders, ...)
- Appuyer sur le bouton MIDI pour quitter le mode apprentissage
- Utiliser les boutons et les faders des contrôleurs MIDI

> Note:  
> Le mapping MIDI est enregistré par olc dans les fichiers ASCII.
