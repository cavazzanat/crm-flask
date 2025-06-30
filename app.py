from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import psycopg2
import psycopg2.extras
import os
from datetime import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = 'secret_key_here'

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        port=os.environ.get("DB_PORT"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM clients WHERE archive = false")
    nb_clients = cur.fetchone()['count']

    cur.execute("SELECT COALESCE(SUM(montant), 0) FROM operations")
    ca_total = cur.fetchone()['coalesce']

    cur.execute("SELECT MAX(date_operation) FROM operations")
    derniere_operation = cur.fetchone()['max']

    cur.execute("SELECT * FROM operations_futures WHERE date_prevue >= CURRENT_DATE ORDER BY date_prevue ASC")
    operations_futures = cur.fetchall()

    ville = request.args.get('ville', '')
    recherche = request.args.get('recherche', '')
    tri = request.args.get('tri', 'recent')

    query = """
        SELECT c.*, MAX(o.date_operation) as derniere_visite
        FROM clients c
        LEFT JOIN operations o ON o.client_id = c.id
        WHERE c.archive = false
    """
    params = []
    if ville:
        query += " AND c.ville ILIKE %s"
        params.append(f"%{ville}%")
    if recherche:
        query += " AND (c.nom ILIKE %s OR c.adresse ILIKE %s OR c.telephone ILIKE %s)"
        params.extend([f"%{recherche}%"] * 3)

    query += " GROUP BY c.id"
    query += " ORDER BY derniere_visite DESC" if tri == 'recent' else " ORDER BY derniere_visite ASC"

    cur.execute(query, params)
    clients = cur.fetchall()

    cur.execute("SELECT * FROM clients WHERE archive = true")
    archives = cur.fetchall()

    cur.execute("SELECT DISTINCT ville FROM clients WHERE archive = false AND ville != ''")
    villes = [row['ville'] for row in cur.fetchall()]

    cur.execute("""
        SELECT o.date_prevue, o.type, o.montant, c.nom, c.id AS client_id
        FROM operations_futures o
        JOIN clients c ON c.id = o.client_id
        WHERE c.archive = false
        ORDER BY o.date_prevue ASC
        LIMIT 10
    """)
    prochaines_operations = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('index.html', clients=clients, archives=archives,
                           nb_clients=nb_clients, ca_total=ca_total,
                           derniere_operation=derniere_operation, ville=ville,
                           recherche=recherche, tri=tri, villes=villes,
                           operations_futures=operations_futures,
                           prochaines_operations=prochaines_operations)

@app.route('/export-clients')
def export_clients():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE archive = false")
    clients = cur.fetchall()
    cur.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nom', 'Prénom', 'Adresse', 'Code postal', 'Ville', 'Téléphone'])

    for c in clients:
        writer.writerow([c['id'], c['nom'], c['prenom'], c['adresse'], c['code_postal'], c['ville'], c['telephone']])

    output.seek(0)
    return send_file(io.BytesIO(output.read().encode()), mimetype='text/csv',
                     as_attachment=True, download_name='clients.csv')

@app.route('/export-client/<int:id>')
def export_single_client(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE id = %s", (id,))
    client = cur.fetchone()

    cur.execute("SELECT * FROM operations WHERE client_id = %s ORDER BY date_operation DESC", (id,))
    operations = cur.fetchall()
    cur.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Client'])
    writer.writerow(['ID', 'Nom', 'Prénom', 'Adresse', 'Code postal', 'Ville', 'Téléphone'])
    writer.writerow([client['id'], client['nom'], client['prenom'], client['adresse'],
                     client['code_postal'], client['ville'], client['telephone']])
    writer.writerow([])
    writer.writerow(['Opérations'])
    writer.writerow(['Date', 'Type', 'Montant', 'Remarque'])
    for op in operations:
        writer.writerow([op['date_operation'], op['type'], op['montant'], op['remarque']])

    output.seek(0)
    return send_file(io.BytesIO(output.read().encode()), mimetype='text/csv',
                     as_attachment=True, download_name=f'client_{id}.csv')

@app.route('/add-client', methods=['POST'])
def add_client():
    data = (
        request.form['nom'], request.form['prenom'], request.form['adresse'],
        request.form['code_postal'], request.form['ville'], request.form['telephone']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO clients (nom, prenom, adresse, code_postal, ville, telephone, archive)
        VALUES (%s, %s, %s, %s, %s, %s, false)
    """, data)
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/archive-client/<int:id>', methods=['POST'])
def archive_client(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE clients SET archive = true WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/restore-client/<int:id>', methods=['POST'])
def restore_client(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE clients SET archive = false WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/delete-client/<int:id>', methods=['POST'])
def delete_client(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM operations WHERE client_id = %s", (id,))
    cur.execute("DELETE FROM clients WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/client/<int:id>')
def client_detail(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE id = %s", (id,))
    client = cur.fetchone()

    cur.execute("SELECT * FROM operations WHERE client_id = %s ORDER BY date_operation DESC", (id,))
    operations = cur.fetchall()

    cur.execute("SELECT COALESCE(SUM(montant), 0) FROM operations WHERE client_id = %s", (id,))
    ca_total = cur.fetchone()['coalesce']

    cur.execute("SELECT * FROM operations_futures WHERE client_id = %s ORDER BY date_prevue ASC", (id,))
    operations_futures = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('client.html', client=client, operations=operations,
                           ca_total=ca_total, operations_futures=operations_futures)

@app.route('/client/<int:id>/update', methods=['POST'])
def update_client(id):
    data = (
        request.form['adresse'], request.form['code_postal'], request.form['ville'],
        request.form['telephone'], request.form.get('profession', ''), request.form.get('remarque', ''), id
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE clients SET adresse=%s, code_postal=%s, ville=%s,
        telephone=%s, profession=%s, remarque=%s WHERE id=%s
    """, data)
    conn.commit()
    cur.close()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/client/<int:id>/update-piano', methods=['POST'])
def update_piano(id):
    data = (
        request.form.get('modele', ''),
        request.form.get('remarques_piano', ''),
        id
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE clients SET modele=%s, remarques_piano=%s WHERE id=%s", data)
    conn.commit()
    cur.close()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/client/<int:id>/add-operation', methods=['POST'])
def add_operation(id):
    type_op = request.form['type']
    montant = float(request.form['montant'])
    date_op_str = request.form['date_operation']
    remarque = request.form.get('remarque', '')

    date_op = datetime.strptime(date_op_str, "%Y-%m-%d").date()
    today = datetime.today().date()

    conn = get_db_connection()
    cur = conn.cursor()

    if date_op > today:
        # Ajouter en tant qu'opération future
        cur.execute("""
            INSERT INTO operations_futures (client_id, type, montant, date_prevue, remarque)
            VALUES (%s, %s, %s, %s, %s)
        """, (id, type_op, montant, date_op_str, remarque))
    else:
        # Ajouter en tant qu'opération passée
        cur.execute("""
            INSERT INTO operations (client_id, type, montant, date_operation, remarque)
            VALUES (%s, %s, %s, %s, %s)
        """, (id, type_op, montant, date_op_str, remarque))

    conn.commit()
    cur.close()
    conn.close()
    return redirect(f'/client/{id}')


@app.route('/client/<int:id>/delete-operation/<int:op_id>', methods=['POST'])
def delete_operation(id, op_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM operations WHERE id = %s", (op_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/client/<int:id>/add-operation-future', methods=['POST'])
def add_operation_future(id):
    data = (
        id,
        request.form['type'],
        float(request.form['montant']),
        request.form['date_prevue'],
        request.form.get('remarque', '')
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO operations_futures (client_id, type, montant, date_prevue, remarque)
        VALUES (%s, %s, %s, %s, %s)
    """, data)
    conn.commit()
    cur.close()
    conn.close()
    return redirect(f'/client/{id}')

@app.route('/reset-filters')
def reset_filters():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
