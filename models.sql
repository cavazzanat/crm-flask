DROP TABLE IF EXISTS clients;

CREATE TABLE clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT,
    adresse TEXT,
    code_postal TEXT,
    ville TEXT,
    telephone TEXT,
    profession TEXT,
    remarque TEXT,
    modele TEXT,
    remarques_piano TEXT,
    archive INTEGER DEFAULT 0
);

CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    type TEXT,
    montant REAL,
    date_operation TEXT,
    remarque TEXT,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);
