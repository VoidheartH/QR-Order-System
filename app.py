import os
from dotenv import load_dotenv

# ── 1) Load .env into os.environ ────────────────────────────────
load_dotenv()

import datetime
import qrcode
import ast
import json
from io import BytesIO

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash, send_file, Response
)
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from markupsafe import Markup
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    current_user, login_required
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import CSRFProtect
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader


# ── 2) Paths & Ensure instance/ Exists ─────────────────────────
BASE_DIR     = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

# ── 3) Compute the DB URI ──────────────────────────────────────
default_path = os.path.join(INSTANCE_DIR, 'restaurant.db')
default_uri  = "sqlite:///" + default_path.replace(os.sep, '/')
env_raw      = os.getenv("SQLALCHEMY_DATABASE_URI", "").strip().strip('"').strip("'")

if env_raw:
    if env_raw.startswith("sqlite:///"):
        rel = env_raw[len("sqlite:///"):]
        abs_p = os.path.abspath(rel) if not os.path.isabs(rel) else rel
        db_uri = "sqlite:///" + abs_p.replace(os.sep, '/')
    else:
        db_uri = env_raw
else:
    db_uri = default_uri

print(f"🔧 Using database URI: {db_uri}")

# ── 4) Flask App & Config ───────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")
csrf = CSRFProtect(app)

app.config['SQLALCHEMY_DATABASE_URI']        = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── 5) Extensions ───────────────────────────────────────────────
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'strong'

# ── 6) Flask-Admin Security ────────────────────────────────────
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

class SecureAdminIndexView(AdminIndexView):
    @expose('/')
    @login_required
    def index(self):
        return self.render('admin_index.html')
    def is_accessible(self):
        return current_user.is_authenticated

admin = Admin(
    app,
    name="Bursa Kebap Evi",
    template_mode='bootstrap4',
    url='/manage',
    index_view=SecureAdminIndexView()
)

# ── Inject the custom style.css into /manage/orders/ Flask-Admin page ─────
@app.after_request
def inject_admin_css(response):
    # only inject into HTML responses under /admin or /manage
    if request.path.startswith(('/manage/orders/')) \
       and response.content_type.startswith('text/html'):
        # only our Special Notes wrap rules, no full stylesheet
        css = """
        <style>
          /* wrap & constrain “Special Notes” column */
          .table-responsive table th:nth-child(7),
          .table-responsive table td:nth-child(7) {
            overflow-wrap: break-word !important;
            word-break: break-word !important;
          }
        </style>
        """
        html = response.get_data(as_text=True)
        head_close = html.lower().find('</head>')
        if head_close != -1:
            html = html[:head_close] + css + html[head_close:]
            response.set_data(html)
    return response

# ── 7) ORM Models ──────────────────────────────────────────────
class Menu(db.Model):
    __tablename__ = 'Menu'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String,  nullable=False)
    price        = db.Column(db.Float,   nullable=False)
    image_url    = db.Column(db.String,  default='')
    description  = db.Column(db.String,  default='')

class Orders(db.Model):
    __tablename__  = 'Orders'
    id             = db.Column(db.Integer, primary_key=True)
    table_id       = db.Column(db.Integer, nullable=False)
    order_date     = db.Column(db.String,  nullable=False)
    items          = db.Column(db.String,  nullable=False)  # JSON list
    status         = db.Column(db.String,  default='Pending')
    special_notes  = db.Column(db.String,  default='')
    archived       = db.Column(db.Boolean, default=False, nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ── 8) Admin Views ─────────────────────────────────────────────
class MenuAdminView(SecureModelView):
    def __init__(self, model, session, **kwargs):
        super().__init__(model, session, name="Menü", **kwargs)

    column_list = ('id', 'name', 'price', 'image_thumb', 'description')
    column_labels = {
        'id':           'ID',
        'name':         'Ad',
        'price':        'Fiyat',
        'image_thumb':  'Önizleme',
        'description':  'Açıklama',
    }
    column_searchable_list = ['name', 'description']
    column_filters         = ['price']
    can_export             = True
    export_types           = ['csv']

    def _image_formatter(self, _, m, name):
        if not m.image_url:
            return ''
        return Markup(
            f'<img src="{m.image_url}" '
            f'style="max-height:80px; border-radius:4px;">'
        )
    column_formatters = {'image_thumb': _image_formatter}


class OrdersAdminView(SecureModelView):
    def __init__(self, model, session, **kwargs):
        super().__init__(model, session, name="Siparişler", **kwargs)

    column_searchable_list = ['items', 'special_notes']
    column_filters         = ['status', 'table_id', 'order_date']
    can_export             = True
    export_types           = ['csv']
    column_labels = {
        'table_id':      'Masa',
        'order_date':    'Sipariş Tarihi',
        'items':         'Ürünler',
        'status':        'Durum',
        'special_notes': 'Notlar',
        'archived':      'Arşivlendi',
    }

    def _format_items(self, _, m, name):
        try:
            arr = ast.literal_eval(m.items)
        except:
            return m.items or ""
        counts = {}
        for it in arr:
            if isinstance(it, dict):
                n, q = it.get('name', str(it)), int(it.get('qty', 1))
            else:
                n, q = it, 1
            counts[n] = counts.get(n, 0) + q
        return Markup(", ").join(f"{qty}× {n}" for n, qty in counts.items())
    column_formatters = {'items': _format_items}

    @action('mark_ready',
            'Hazırlanıyor Olarak İşaretle',
            'Seçilenleri hazırlayan durumuna getirmek ister misiniz?')
    def action_mark_ready(self, ids):
        for o in Orders.query.filter(Orders.id.in_(ids)):
            o.status = 'Preparing'
        db.session.commit()


admin.add_view(MenuAdminView(Menu, db.session))
admin.add_view(OrdersAdminView(Orders, db.session))


# ── 9) Login Manager ───────────────────────────────────────────
@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

# ── 10) Auth Routes ────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_view'))
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user)
            flash('Giriş başarılı.','success')
            return redirect(url_for('admin_view'))
        flash('Geçersiz kullanıcı adı veya şifre.','error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı.','success')
    return redirect(url_for('login'))

# ── 11) Public Pages & APIs ────────────────────────────────────
@app.route('/')
def redirect_to_table1():
    return redirect(url_for('table_view', table_id=1))

@app.route('/table/<int:table_id>')
def table_view(table_id):
    return render_template('menu.html', table_id=table_id)

@app.route('/menu')
def get_menu():
    return jsonify([[m.id,m.name,m.price,m.image_url,m.description] for m in Menu.query.all()])

@app.route('/order', methods=['POST'])
def place_order():
    data = request.get_json()
    t, items = data.get('table_id'), data.get('items',[])
    if t is None or not items:
        return jsonify({'error':'Table and items required'}), 400
    o = Orders(
        table_id      = t,
        order_date    = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        items         = json.dumps(items),
        status        = 'Pending',
        special_notes = data.get('special_notes','')
    )
    db.session.add(o); db.session.commit()
    return jsonify({'message':'Sipariş başarıyla alındı!'}), 201

@app.route('/orders')
@login_required
def get_orders():
    data = Orders.query.filter_by(archived=False).all()
    return jsonify([[o.id,o.table_id,o.order_date,o.items,o.status,o.special_notes]
                    for o in data])

@app.route('/orders/table/<int:tid>')
def get_orders_for_table(tid):
    q = Orders.query.filter_by(table_id=tid, archived=False)\
                     .order_by(Orders.order_date.desc())
    return jsonify([[o.id,o.table_id,o.order_date,o.items,o.status,o.special_notes]
                    for o in q])

@app.route('/order/update/<int:oid>', methods=['PATCH'])
@login_required
def update_order_status(oid):
    d = request.get_json()
    if 'status' not in d:
        return jsonify({'error':'Status required'}), 400
    o = Orders.query.get_or_404(oid)
    o.status = d['status']
    # auto-archive completed orders
    if o.status.lower() == 'completed':
        o.archived = True
    db.session.commit()
    return jsonify({'message':f'Order {oid} updated'})

# ── Archive a single order ─────────────────────────────────────
@app.route('/order/archive/<int:oid>', methods=['PATCH'])
@login_required
def archive_order(oid):
    o = Orders.query.get_or_404(oid)
    o.archived = True
    db.session.commit()
    return jsonify({'message': f'Order {oid} archived'}), 200

@app.route('/orders/export')
@login_required
def export_orders_csv():
    import csv
    from io import StringIO
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['ID','Table','Order Date','Items','Status','Notes'])
    for o in Orders.query.filter_by(archived=False).all():
        cw.writerow([o.id,o.table_id,o.order_date,o.items,o.status,o.special_notes])
    return Response(
        si.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition':'attachment;filename=orders.csv'}
    )

@app.route('/qr_code/<int:table_id>')
@login_required
def qr_code(table_id):
    url = url_for('table_view',table_id=table_id,_external=True)
    img = qrcode.make(url)
    buf = BytesIO(); img.save(buf,'PNG'); buf.seek(0)
    return send_file(buf,mimetype='image/png')

@app.route('/admin')
@login_required
def admin_view():
    return render_template('orders.html')

# ── 12) archive completed orders ─────────────────────────
@app.route('/archive', methods=['POST'])
@login_required
def archive_completed():
    to_archive = Orders.query.filter_by(status='Completed', archived=False).all()
    count = len(to_archive)
    for o in to_archive:
        o.archived = True
    db.session.commit()
    return jsonify({'message': f'{count} sipariş arşivlendi.'}), 200

# ── 13) NEW: show archived list page ─────────────────────────
@app.route('/archived')
@login_required
def archived_orders_page():
    return render_template('archived_orders.html')

# ── 14) JSON for archived data ──────────────────────────
@app.route('/archived/data')
@login_required
def get_archived_orders_data():
    archived = Orders.query.filter_by(archived=True).all()
    return jsonify([[o.id,o.table_id,o.order_date,o.items,o.status,o.special_notes]
                    for o in archived])

# ── 15) CSV export for archived ─────────────────────────
@app.route('/archived/export')
@login_required
def export_archived_csv():
    import csv
    from io import StringIO
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['ID','Table','Order Date','Items','Status','Notes'])
    for o in Orders.query.filter_by(archived=True).all():
        cw.writerow([o.id,o.table_id,o.order_date,o.items,o.status,o.special_notes])
    return Response(
        si.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition':'attachment;filename=archived_orders.csv'}
    )

@app.route('/qrcodes')
@login_required
def qrcodes_page():
    page     = int(request.args.get('page',1))
    per_page = 25    # 50 QR codes per page
    total    = 1000  # total of 1000 QR codes
    total_pg = (total+per_page-1)//per_page
    page     = max(1,min(page,total_pg))
    start    = (page-1)*per_page+1
    end      = min(total,page*per_page)
    return render_template('qrcodes.html',
                           table_ids=range(start,end+1),
                           page=page,
                           total_pages=total_pg)


@app.route('/qrcodes/pdf')
@login_required
def qrcodes_pdf():
    # 1) Compute which 25 tables to include
    page     = int(request.args.get('page', 1))
    per_page = 25
    total    = 1000  # adjust if needed
    start    = (page - 1) * per_page + 1
    end      = min(total, page * per_page)
    table_ids = range(start, end + 1)

    # 2) Create an A4 canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    margin = 15 * mm

    # 3) Grid: 5 columns × 5 rows
    cols, rows = 5, 5
    cell_w = (w - 2 * margin) / cols
    cell_h = (h - 2 * margin) / rows

    for idx, tid in enumerate(table_ids):
        col = idx % cols
        row = idx // cols
        x = margin + col * cell_w
        y = h - margin - (row + 1) * cell_h

        # a) Generate QR as PIL image
        url    = url_for('table_view', table_id=tid, _external=True)
        qr_img = qrcode.make(url)

        # b) Draw the QR, sized to 80% of cell width, centered
        qr_size = cell_w * 0.8
        c.drawInlineImage(
            qr_img,
            x + (cell_w - qr_size) / 2,
            y + (cell_h - qr_size) / 2,
            qr_size,
            qr_size,
            preserveAspectRatio=True
        )

        # c) Draw the "Masa X" label below
        c.setFont("Helvetica", 9)
        c.drawCentredString(
            x + cell_w / 2,
            y + 5,
            f"Masa {tid}"
        )

    # 4) Finalize and return
    c.save()
    buffer.seek(0)
    return send_file(
        buffer,
        download_name=f'qrcodes_{page}.pdf',
        as_attachment=True,
        mimetype='application/pdf'
    )

@app.route('/manage/')
@app.route('/manage')
@login_required
def manage_root():
    return admin.index_view.index()

# ── 16) Bootstrap & Seed Manager ───────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        # create tables if they don't exist
        db.create_all()

        # pull in the credentials you defined in .env
        mgr_user = os.getenv("MANAGER_USER", "manager")
        mgr_pw   = os.getenv("MANAGER_PW", "ChangeMe123!")

        # only seed if that username isn't already there
        if not User.query.filter_by(username=mgr_user).first():
            admin = User(username=mgr_user)
            admin.set_password(mgr_pw)
            db.session.add(admin)
            db.session.commit()
            print(f"🛡️ Seeded manager: {mgr_user}/{mgr_pw}")

    # turn off Flask’s built-in debugger in production
    app.run(debug=False)

