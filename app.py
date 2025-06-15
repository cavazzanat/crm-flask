from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file
import sqlite3
from datetime import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = 'secret_key_here'

def get_db_connection():
    conn = sqlite3.connect('crm.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()

    nb_clients = conn.execute("SELECT COUNT(*) FROM clients WHERE archive = 0").fetchone()[0]
    ca_total = conn.execute("SELECT IFNULL(SUM(montant), 0) FROM operations").fetchone()[0]
    derniere_operation = conn.execute("SELECT MAX(date_operation) FROM operations").fetchone()[0]

    ville = request.args.get('ville', '')
    recherche = request.args.get('recherche', '')
    tri = request.args.get('tri', 'recent')

    query = """
        SELECT c.*, MAX(o.date_operation) as derniere_visite
        FROM clients c
        LEFT JOIN operations o ON o.client_id = c.id
        WHERE c.archive = 0
    """
    params = []
    if ville:
        query += " AND c.ville LIKE ?"
        params.append(f"%{ville}%")
    if recherche:
        query += " AND (c.nom LIKE ? OR c.adresse LIKE ? OR c.telephone LIKE ?)"
        params.extend([f"%{recherche}%"] * 3)

    query += " GROUP BY c.id"
    query += " ORDER BY derniere_visite DESC" if tri == 'recent' else " ORDER BY derniere_visite ASC"

    clients = conn.execute(query, params).fetchall()
    archives = conn.execute("SELECT * FROM clients WHERE archive = 1").fetchall()

    villes = [row['ville'] for row in conn.execute("SELECT DISTINCT ville FROM clients WHERE archive = 0 AND ville != ''").fetchall()]

    conn.close()
    return render_template('index.html', clients=clients, archives=archives, nb_clients=nb_clients, ca_total=ca_total, derniere_operation=derniere_operation, ville=ville, recherche=recherche, tri=tri, villes=villes)

@app.route('/export-clients')
def export_clients():
    conn = get_db_connection()
    clients = conn.execute("SELECT * FROM clients WHERE archive = 0").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nom', 'Prénom', 'Adresse', 'Code postal', 'Ville', 'Téléphone'])

    for c in clients:
        writer.writerow([c['id'], c['nom'], c['prenom'], c['adresse'], c['code_postal'], c['ville'], c['telephone']])

    output.seek(0)
    return send_file(io.BytesIO(output.read().encode()), mimetype='text/csv', as_attachment=True, download_name='clients.csv')

@app.route('/export-client/<int:id>')
def export_single_client(id):
    conn = get_db_connection()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (id,)).fetchone()
    operations = conn.execute("SELECT * FROM operations WHERE client_id = ? ORDER BY date_operation DESC", (id,)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Client'])
    writer.writerow(['ID', 'Nom', 'Prénom', 'Adresse', 'Code postal', 'Ville', 'Téléphone'])
    writer.writerow([client['id'], client['nom'], client['prenom'], client['adresse'], client['code_postal'], client['ville'], client['telephone']])

    writer.writerow([])
    writer.writerow(['Opérations'])
    writer.writerow(['Date', 'Type', 'Montant', 'Remarque'])
    for op in operations:
        writer.writerow([op['date_operation'], op['type'], op['montant'], op['remarque']])

    output.seek(0)
    return send_file(io.BytesIO(output.read().encode()), mimetype='text/csv', as_attachment=True, download_name=f'client_{id}.csv')

@app.route('/api/villes')
def api_villes():
    conn = get_db_connection()
    villes = [row['ville'] for row in conn.execute("SELECT DISTINCT ville FROM clients WHERE archive = 0 AND ville != ''").fetchall()]
    conn.close()
    return jsonify(villes)

@app.route('/add-client', methods=['POST'])
def add_client():
    data = (request.form['nom'], request.form['prenom'], request.form['adresse'], request.form['code_postal'], request.form['ville'], request.form['telephone'])
    conn = get_db_connection()
    conn.execute("INSERT INTO clients (nom, prenom, adresse, code_postal, ville, telephone) VALUES (?, ?, ?, ?, ?, ?)", data)
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/archive-client/<int:id>', methods=['POST'])
def archive_client(id):
    conn = get_db_connection()
    conn.execute("UPDATE clients SET archive = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Le client a été archivé avec succès.")
    return redirect('/')

@app.route('/restore-client/<int:id>', methods=['POST'])
def restore_client(id):
    conn = get_db_connection()
    conn.execute("UPDATE clients SET archive = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Le client a été restauré.")
    return redirect('/')

@app.route('/delete-client/<int:id>', methods=['POST'])
def delete_client(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM clients WHERE id = ?", (id,))
    conn.execute("DELETE FROM operations WHERE client_id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Le client a été supprimé définitivement.")
    return redirect('/')

@app.route('/client/<int:id>')
def client_detail(id):
    conn = get_db_connection()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (id,)).fetchone()
    operations = conn.execute("SELECT * FROM operations WHERE client_id = ? ORDER BY date_operation DESC", (id,)).fetchall()
    ca_total = conn.execute("SELECT IFNULL(SUM(montant), 0) FROM operations WHERE client_id = ?", (id,)).fetchone()[0]
    conn.close()
    return render_template('client.html', client=client, operations=operations, ca_total=ca_total)

@app.route('/client/<int:id>/update', methods=['POST'])
def update_client(id):
    data = (
        request.form['adresse'], request.form['code_postal'], request.form['ville'],
        request.form['telephone'], request.form.get('profession', ''), request.form.get('remarque', ''), id
    )
    conn = get_db_connection()
    conn.execute("""
        UPDATE clients SET adresse=?, code_postal=?, ville=?, telephone=?, profession=?, remarque=?
        WHERE id=?
    """, data)
    conn.commit()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/client/<int:id>/update-piano', methods=['POST'])
def update_piano(id):
    data = (request.form.get('modele', ''), request.form.get('remarques_piano', ''), id)
    conn = get_db_connection()
    conn.execute("UPDATE clients SET modele=?, remarques_piano=? WHERE id=?", data)
    conn.commit()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/client/<int:id>/add-operation', methods=['POST'])
def add_operation(id):
    data = (
        id, request.form['type'], float(request.form['montant']),
        request.form['date_operation'], request.form.get('remarque', '')
    )
    conn = get_db_connection()
    conn.execute("INSERT INTO operations (client_id, type, montant, date_operation, remarque) VALUES (?, ?, ?, ?, ?)", data)
    conn.commit()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/client/<int:id>/delete-operation/<int:op_id>', methods=['POST'])
def delete_operation(id, op_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM operations WHERE id = ?", (op_id,))
    conn.commit()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/reset-filters')
def reset_filters():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
