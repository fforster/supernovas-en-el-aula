"""Qué había vivo en la Tierra cuando la supernova explotó.

La luz de las supernovas del catálogo tardó entre 200 y 1000 millones de años en
llegar. Ese número, así solo, no le dice nada a nadie: "hace 380 millones de
años" no se imagina. En cambio "cuando en la Tierra los peces recién estaban
saliendo del agua" sí.

Los límites son los de la Escala Cronoestratigráfica Internacional (ICS/IUGS,
v2023), en millones de años. Los ejemplos están elegidos para 10-15 años:
bichos y plantas que se puedan dibujar.

Fuentes: International Commission on Stratigraphy; British Geological Survey,
"Geological timechart"; U.S. National Park Service, "Geologic Time Scale".
"""

from __future__ import annotations

#: (inicio, fin) en millones de años atrás, más el texto para cada idioma.
#: Ordenadas de la más reciente a la más antigua.
ERAS = [
    (0.0, 2.58, {
        "es": ("el Cuaternario", "ya existían los seres humanos, junto con mamuts, "
               "tigres dientes de sable y bosques parecidos a los de hoy"),
        "en": ("the Quaternary", "humans already existed, alongside mammoths, "
               "sabre-toothed cats and forests much like today's"),
    }),
    (2.58, 23.03, {
        "es": ("el Neógeno", "aparecían los primeros antepasados de los humanos, y el "
               "mundo se llenaba de praderas con caballos, elefantes y rinocerontes"),
        "en": ("the Neogene", "the first human ancestors were appearing, and the world "
               "was filling up with grasslands, horses, elephants and rhinos"),
    }),
    (23.03, 66.0, {
        "es": ("el Paleógeno", "los dinosaurios ya se habían extinguido y los mamíferos "
               "tomaban el control: había primates primitivos y las primeras ballenas"),
        "en": ("the Paleogene", "the dinosaurs had already died out and mammals were "
               "taking over: there were early primates and the first whales"),
    }),
    (66.0, 145.0, {
        "es": ("el Cretácico", "andaban por ahí el Tyrannosaurus rex y el Triceratops, y "
               "aparecían las primeras flores"),
        "en": ("the Cretaceous", "Tyrannosaurus rex and Triceratops were around, and the "
               "first flowers were appearing"),
    }),
    (145.0, 201.4, {
        "es": ("el Jurásico", "era la época de los grandes dinosaurios como el Diplodocus "
               "y el Stegosaurus, entre helechos y coníferas; volaba el Archaeopteryx, "
               "mitad dinosaurio y mitad ave"),
        "en": ("the Jurassic", "it was the age of the big dinosaurs like Diplodocus and "
               "Stegosaurus, among ferns and conifers; Archaeopteryx, half dinosaur and "
               "half bird, was flying about"),
    }),
    (201.4, 251.9, {
        "es": ("el Triásico", "recién aparecían los primeros dinosaurios y también los "
               "primeros mamíferos, del tamaño de un ratón"),
        "en": ("the Triassic", "the first dinosaurs were only just appearing, and so were "
               "the first mammals, about the size of a mouse"),
    }),
    (251.9, 298.9, {
        "es": ("el Pérmico", "dominaban reptiles raros como el Dimetrodon, el de la vela "
               "en la espalda, y crecían los primeros bosques de coníferas"),
        "en": ("the Permian", "strange reptiles like Dimetrodon, the one with the sail on "
               "its back, were in charge, and the first conifer forests were growing"),
    }),
    (298.9, 358.9, {
        "es": ("el Carbonífero", "la Tierra estaba cubierta de pantanos con helechos "
               "gigantes, volaban libélulas de casi un metro de envergadura y aparecían "
               "los primeros reptiles"),
        "en": ("the Carboniferous", "Earth was covered in swamps of giant ferns, "
               "dragonflies with almost one-metre wingspans were flying around, and the "
               "first reptiles were appearing"),
    }),
    (358.9, 419.2, {
        "es": ("el Devónico", "lo llaman la edad de los peces: crecían los primeros "
               "bosques y algunos peces empezaban a salir del agua y a convertirse en "
               "los primeros anfibios"),
        "en": ("the Devonian", "they call it the age of fishes: the first forests were "
               "growing and some fish were starting to crawl out of the water and become "
               "the first amphibians"),
    }),
    (419.2, 443.8, {
        "es": ("el Silúrico", "las plantas recién colonizaban la tierra firme, y en el mar "
               "cazaban escorpiones marinos de dos metros"),
        "en": ("the Silurian", "plants were only just colonising dry land, and two-metre "
               "sea scorpions were hunting in the ocean"),
    }),
    (443.8, 485.4, {
        "es": ("el Ordovícico", "casi toda la vida estaba en el mar —trilobites, corales y "
               "moluscos con conchas en punta— y en tierra sólo había musgos"),
        "en": ("the Ordovician", "almost all life was in the sea — trilobites, corals and "
               "molluscs with cone-shaped shells — and on land there were only mosses"),
    }),
    (485.4, 538.8, {
        "es": ("el Cámbrico", "la vida entera vivía en el mar: trilobites y animales tan "
               "extraños como el Anomalocaris. En tierra firme no había absolutamente nada"),
        "en": ("the Cambrian", "all life lived in the sea: trilobites and creatures as odd "
               "as Anomalocaris. On dry land there was nothing at all"),
    }),
    (538.8, 635.0, {
        "es": ("el Ediacárico", "los primeros animales eran cuerpos blandos y planos "
               "pegados al fondo del mar, sin huesos ni conchas"),
        "en": ("the Ediacaran", "the first animals were soft, flat bodies stuck to the "
               "sea floor, with no bones and no shells"),
    }),
    (635.0, 720.0, {
        "es": ("el Criogénico", "la Tierra era casi una bola de nieve, congelada casi de "
               "polo a polo, y la única vida eran microbios y algas: no existía ni un "
               "solo animal"),
        "en": ("the Cryogenian", "Earth was almost a snowball, frozen nearly from pole to "
               "pole, and the only life was microbes and algae: not a single animal "
               "existed"),
    }),
    (720.0, 1000.0, {
        "es": ("el Tónico", "no había plantas ni animales de ningún tipo: sólo microbios "
               "y algas verdes flotando en el mar"),
        "en": ("the Tonian", "there were no plants and no animals of any kind: just "
               "microbes and green algae floating in the sea"),
    }),
]

#: Antes de eso no arriesgamos detalle.
MAS_ANTIGUO = {
    "es": ("una época sin nombre fácil", "la vida apenas empezaba y sólo había "
           "microbios en el agua"),
    "en": ("a time with no easy name", "life was only just beginning and there were "
           "only microbes in the water"),
}


def epoca(millones_de_anios: float, idioma: str = "es") -> tuple[str, str]:
    """Nombre del período y qué vivía entonces.

    ``millones_de_anios`` es cuánto tardó la luz en llegar, que para estas
    distancias es prácticamente lo mismo que "hace cuánto ocurrió".
    """
    for inicio, fin, textos in ERAS:
        if inicio <= millones_de_anios < fin:
            return textos.get(idioma, textos["es"])
    return MAS_ANTIGUO.get(idioma, MAS_ANTIGUO["es"])
