-- Table clients
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
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
    archive BOOLEAN DEFAULT FALSE
);

-- Table opérations
CREATE TABLE IF NOT EXISTS operations (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT,
    montant NUMERIC,
    date_operation DATE,
    remarque TEXT
);
