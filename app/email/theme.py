"""Arcane palette, type, hero image, and fixed quote for the digest email."""

ARCANE = {
    "bg": "#300610",
    "bg_2": "#431D26",
    "bg_3": "#F9F9ED",
    "fg": "#FCF3ED",
    "fg_2": "#EFE1D8",
    "fg_3": "#B09996",
    "fg_inverted": "#300610",
    "stroke": "#3D151D",
    "brand": "#614500",
    "font_sans": "Inter, Arial, sans-serif",
    "font_serif": "'Instrument Serif', Georgia, 'Times New Roman', serif",
    "font_href": (
        "https://fonts.googleapis.com/css2?"
        "family=Instrument+Serif&family=Inter:wght@400;500&display=swap"
    ),
}

HERO_IMAGE = {
    "src": (
        "https://images.unsplash.com/photo-1761233138981-50a88922c852"
        "?auto=format&fit=crop&w=1280&h=720&q=80"
    ),
    "alt": "New York Stock Exchange facade",
}

MARKS_QUOTE = {
    "text": (
        "Success in investing doesn't come from buying good things, "
        "but from buying things well."
    ),
    "attribution": "-Howard Marks",
}

FOOTER = {
    "blurb": "The week's paper, ranked. The hot takes can wait.",
    "address_lines": (
        "124 Mercantile Row, Studio 3",
        "Los Angeles, CA, 90013",
    ),
    "socials": (
        {
            "label": "LinkedIn",
            "url": "https://www.linkedin.com/in/juliangriffin11/",
            "filename": "linkedin.png",
            "content_id": "social-linkedin",
        },
        {
            "label": "GitHub",
            "url": "https://github.com/JulianGriffin11",
            "filename": "github.png",
            "content_id": "social-github",
        },
    ),
}
