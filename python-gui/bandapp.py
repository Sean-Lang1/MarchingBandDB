import sys
import os
import csv
import sqlite3
from datetime import date

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox, QFormLayout,
    QTabWidget, QFileDialog, QHeaderView, QInputDialog, QCheckBox,
    QSplitter, QToolButton, QButtonGroup, QDialog, QAbstractItemView,
    QGraphicsDropShadowEffect, QCompleter, QStyle, QFrame
)

DB_PATH = "band.db"

SECTIONS = ["WOODWIND", "BRASS", "PERCUSSION", "FLAG CORP", "DRUM MAJOR", "OTHER"]
CLASSIFICATIONS = ["", "Freshman", "Sophomore", "Junior", "Senior", "Graduate"]
SHIRT_SIZES = ["", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
SHOE_SIZES = [""] + [str(x) for x in [
    5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15
]]

INSTRUMENT_CATALOG = [
    ("PICCOLO", "WOODWIND"),
    ("FLUTE", "WOODWIND"),
    ("CLARINET", "WOODWIND"),
    ("ALTO SAXOPHONE", "WOODWIND"),
    ("TENOR SAXOPHONE", "WOODWIND"),
    ("BARITONE SAXOPHONE", "WOODWIND"),
    ("TRUMPET", "BRASS"),
    ("MELLOPHONE", "BRASS"),
    ("TROMBONE", "BRASS"),
    ("EUPHONIUM / BARITONE", "BRASS"),
    ("SOUSAPHONE", "BRASS"),
    ("SNARE DRUM", "PERCUSSION"),
    ("TENOR DRUMS", "PERCUSSION"),
    ("BASS DRUM", "PERCUSSION"),
    ("CYMBALS", "PERCUSSION"),
]

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def table_info(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return cur.fetchall()

def table_has_column(conn, table, col):
    return any(r[1] == col for r in table_info(conn, table))

def current_school_year_label():
    today = date.today()
    y = today.year
    start = y if today.month >= 8 else y - 1
    return f"{start}-{start+1}"

def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS STUDENTS (
            STUDENT_ID INTEGER PRIMARY KEY,
            FNAME TEXT NOT NULL,
            LNAME TEXT NOT NULL,
            CLASSIFICATION TEXT,
            SECTION TEXT NOT NULL,
            PRIMARY_ROLE TEXT,
            SHIRT_SIZE TEXT,
            SHOE_SIZE TEXT,
            ACTIVE INTEGER NOT NULL DEFAULT 1,
            UPDATED_AT TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS COMPLIANCE (
            STUDENT_ID INTEGER PRIMARY KEY,
            CREDIT_HOURS INTEGER NOT NULL DEFAULT 0,
            GPA REAL NOT NULL DEFAULT 0.0,
            DUES_PAID INTEGER NOT NULL DEFAULT 0,
            LAST_VERIFIED_DATE TEXT,
            FOREIGN KEY (STUDENT_ID) REFERENCES STUDENTS(STUDENT_ID) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS INSTRUMENT_TYPES (
            TYPE_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            TYPE_NAME TEXT UNIQUE NOT NULL,
            SECTION TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS INSTRUMENTS (
            INSTRUMENT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            TYPE_ID INTEGER NOT NULL,
            SERIAL TEXT,
            CONDITION_NOTES TEXT,
            CHECKED_OUT_TO INTEGER UNIQUE,
            CHECKED_OUT_DATE TEXT,
            FOREIGN KEY (TYPE_ID) REFERENCES INSTRUMENT_TYPES(TYPE_ID) ON DELETE RESTRICT,
            FOREIGN KEY (CHECKED_OUT_TO) REFERENCES STUDENTS(STUDENT_ID) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS UNIFORMS (
            UNIFORM_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            COAT_SIZE TEXT,
            PANT_SIZE TEXT,
            COAT_NUMBER TEXT,
            PANT_NUMBER TEXT,
            CONDITION_NOTES TEXT,
            CHECKED_OUT_TO INTEGER UNIQUE,
            CHECKED_OUT_DATE TEXT,
            FOREIGN KEY (CHECKED_OUT_TO) REFERENCES STUDENTS(STUDENT_ID) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS SHAKOS (
            SHAKO_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            SIZE TEXT,
            CONDITION_NOTES TEXT,
            CHECKED_OUT_TO INTEGER UNIQUE,
            CHECKED_OUT_DATE TEXT,
            FOREIGN KEY (CHECKED_OUT_TO) REFERENCES STUDENTS(STUDENT_ID) ON DELETE SET NULL
        )
    """)

    # Backwards-safe schema upgrades
    if not table_has_column(conn, "STUDENTS", "PRIMARY_ROLE"):
        conn.execute("ALTER TABLE STUDENTS ADD COLUMN PRIMARY_ROLE TEXT")
    if not table_has_column(conn, "STUDENTS", "ACTIVE"):
        conn.execute("ALTER TABLE STUDENTS ADD COLUMN ACTIVE INTEGER NOT NULL DEFAULT 1")
    if not table_has_column(conn, "STUDENTS", "UPDATED_AT"):
        conn.execute("ALTER TABLE STUDENTS ADD COLUMN UPDATED_AT TEXT")

    # Seed instrument types
    for name, sec in INSTRUMENT_CATALOG:
        conn.execute(
            "INSERT OR IGNORE INTO INSTRUMENT_TYPES (TYPE_NAME, SECTION) VALUES (?, ?)",
            (name, sec)
        )

    conn.commit()

def make_table_item(text, align_right=False, align_center=False):
    item = QTableWidgetItem("" if text is None else str(text))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    if align_center:
        item.setTextAlignment(Qt.AlignCenter)
    elif align_right:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    return item

def is_eligible(credit_hours, gpa, dues_paid):
    return credit_hours >= 12 and gpa >= 3.0 and dues_paid == 1

def check_student_exists(conn, student_id):
    cur = conn.execute("SELECT 1 FROM STUDENTS WHERE STUDENT_ID=?", (student_id,))
    return cur.fetchone() is not None

def get_student_name(conn, student_id):
    cur = conn.execute("SELECT FNAME, LNAME FROM STUDENTS WHERE STUDENT_ID=?", (student_id,))
    r = cur.fetchone()
    return f"{r[0]} {r[1]}" if r else ""

def get_student_section(conn, student_id):
    cur = conn.execute("SELECT COALESCE(SECTION,'') FROM STUDENTS WHERE STUDENT_ID=?", (student_id,))
    r = cur.fetchone()
    return (r[0] if r else "") or ""

def get_instrument_section_by_id(conn, instrument_id):
    cur = conn.execute("""
        SELECT t.SECTION
        FROM INSTRUMENTS i
        JOIN INSTRUMENT_TYPES t ON i.TYPE_ID=t.TYPE_ID
        WHERE i.INSTRUMENT_ID=?
    """, (instrument_id,))
    r = cur.fetchone()
    return (r[0] if r else "") or ""

class ComplianceDialog(QDialog):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.setWindowTitle("Compliance Manager")
        self.conn = conn
        self.undo_push = parent.push_undo_ops
        self.refresh_all = parent.refresh_all
        self.show_error = parent.show_error
        self.show_message = parent.show_message
        self.apply_shadow = parent.apply_shadow
        self.resize(950, 620)
        self.setup_ui()
        self.load()

    def setup_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by ID or name…")
        self.search.textChanged.connect(self.load)
        top.addWidget(self.search)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load)
        top.addWidget(refresh_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)
        top.addWidget(export_btn)

        root.addLayout(top)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Credits", "GPA", "Dues", "Eligible", "Last Verified", "Active"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.on_select)
        self.table.setShowGrid(True)
        root.addWidget(self.table)

        bottom = QHBoxLayout()

        edit_group = QGroupBox("Edit Selected")
        form = QFormLayout(edit_group)

        self.sel = QLabel("No student selected")
        self.sel.setObjectName("highlight")
        form.addRow("Selected:", self.sel)

        self.credits = QSpinBox()
        self.credits.setRange(0, 30)
        form.addRow("Credit Hours:", self.credits)

        self.gpa = QDoubleSpinBox()
        self.gpa.setRange(0.0, 4.0)
        self.gpa.setDecimals(2)
        form.addRow("GPA:", self.gpa)

        self.dues = QComboBox()
        self.dues.addItems(["No", "Yes"])
        form.addRow("Dues Paid:", self.dues)

        self.save_btn = QPushButton("Save")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        form.addRow(self.save_btn)

        bottom.addWidget(edit_group)
        root.addLayout(bottom)

        self.apply_shadow(edit_group)

    def load(self):
        q = self.search.text().strip()
        where = ""
        params = []
        if q:
            where = "WHERE s.STUDENT_ID LIKE ? OR (s.FNAME || ' ' || s.LNAME) LIKE ?"
            params = [f"%{q}%", f"%{q}%"]

        cur = self.conn.execute(f"""
            SELECT s.STUDENT_ID,
                   s.FNAME || ' ' || s.LNAME,
                   COALESCE(c.CREDIT_HOURS, 0),
                   COALESCE(c.GPA, 0.0),
                   COALESCE(c.DUES_PAID, 0),
                   COALESCE(c.LAST_VERIFIED_DATE, ''),
                   COALESCE(s.ACTIVE, 1)
            FROM STUDENTS s
            LEFT JOIN COMPLIANCE c ON s.STUDENT_ID = c.STUDENT_ID
            {where}
            ORDER BY s.LNAME, s.FNAME
        """, params)

        rows = cur.fetchall()
        self.table.setRowCount(0)
        for r in rows:
            sid, name, credits, gpa, dues, last, active = r
            row = self.table.rowCount()
            self.table.insertRow(row)
            eligible = is_eligible(credits, gpa, dues)
            self.table.setItem(row, 0, make_table_item(sid, True))
            self.table.setItem(row, 1, make_table_item(name))
            self.table.setItem(row, 2, make_table_item(credits, True))
            self.table.setItem(row, 3, make_table_item(f"{gpa:.2f}", True))
            self.table.setItem(row, 4, make_table_item("Yes" if dues == 1 else "No"))
            self.table.setItem(row, 5, make_table_item("YES" if eligible else "NO"))
            self.table.setItem(row, 6, make_table_item(last))
            self.table.setItem(row, 7, make_table_item("Yes" if active == 1 else "No"))

        self.table.resizeColumnsToContents()

    def on_select(self):
        row = self.table.currentRow()
        if row < 0:
            self.sel.setText("No student selected")
            self.save_btn.setEnabled(False)
            return

        sid = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()

        self.sel.setText(f"{sid} - {name}")
        self.save_btn.setEnabled(True)

        credits = int(self.table.item(row, 2).text())
        gpa = float(self.table.item(row, 3).text())
        dues = 1 if self.table.item(row, 4).text() == "Yes" else 0

        self.credits.setValue(credits)
        self.gpa.setValue(gpa)
        self.dues.setCurrentIndex(1 if dues == 1 else 0)

    def save(self):
        row = self.table.currentRow()
        if row < 0:
            return
        sid = int(self.table.item(row, 0).text())

        cur = self.conn.execute("""
            SELECT COALESCE(CREDIT_HOURS, 0), COALESCE(GPA, 0.0), COALESCE(DUES_PAID, 0), COALESCE(LAST_VERIFIED_DATE, '')
            FROM COMPLIANCE WHERE STUDENT_ID=?
        """, (sid,))
        old = cur.fetchone() or (0, 0.0, 0, "")

        new_credits = self.credits.value()
        new_gpa = self.gpa.value()
        new_dues = 1 if self.dues.currentIndex() == 1 else 0
        new_date = date.today().isoformat()

        ops = [
            ("INSERT INTO COMPLIANCE (STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE) VALUES (?, ?, ?, ?, ?) "
             "ON CONFLICT(STUDENT_ID) DO UPDATE SET CREDIT_HOURS=excluded.CREDIT_HOURS, GPA=excluded.GPA, DUES_PAID=excluded.DUES_PAID, LAST_VERIFIED_DATE=excluded.LAST_VERIFIED_DATE",
             (sid, new_credits, new_gpa, new_dues, new_date))
        ]

        undo_ops = [
            ("INSERT INTO COMPLIANCE (STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE) VALUES (?, ?, ?, ?, ?) "
             "ON CONFLICT(STUDENT_ID) DO UPDATE SET CREDIT_HOURS=excluded.CREDIT_HOURS, GPA=excluded.GPA, DUES_PAID=excluded.DUES_PAID, LAST_VERIFIED_DATE=excluded.LAST_VERIFIED_DATE",
             (sid, old[0], old[1], old[2], old[3]))
        ]

        try:
            self.conn.execute("BEGIN")
            for sql, params in ops:
                self.conn.execute(sql, params)
            self.conn.commit()
            self.undo_push("Edit Compliance", undo_ops)
            self.load()
            self.refresh_all()
        except Exception as e:
            self.conn.rollback()
            self.show_error(f"Error: {str(e)}")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Compliance Report", "compliance_report.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            cur = self.conn.execute("""
                SELECT s.STUDENT_ID, s.FNAME, s.LNAME, COALESCE(s.CLASSIFICATION, ''), COALESCE(s.SECTION, ''),
                       COALESCE(c.CREDIT_HOURS, 0), COALESCE(c.GPA, 0.0), COALESCE(c.DUES_PAID, 0), COALESCE(c.LAST_VERIFIED_DATE, '')
                FROM STUDENTS s
                LEFT JOIN COMPLIANCE c ON s.STUDENT_ID = c.STUDENT_ID
                ORDER BY s.SECTION, s.LNAME, s.FNAME
            """)
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Student ID", "First", "Last", "Class", "Section", "Credits", "GPA", "Dues Paid", "Eligible", "Last Verified"])
                for r in cur.fetchall():
                    eligible = is_eligible(r[5], r[6], r[7])
                    w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], f"{r[6]:.2f}", "Yes" if r[7] == 1 else "No", "Yes" if eligible else "No", r[8]])
            self.show_message("Saved", f"Saved to:\n{path}")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

class InventoryDialog(QDialog):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.setWindowTitle("Inventory Viewer")
        self.conn = conn
        self.apply_shadow = parent.apply_shadow
        self.show_error = parent.show_error
        self.show_message = parent.show_message
        self.refresh_all = parent.refresh_all
        self.undo_push = parent.push_undo_ops
        self.resize(1100, 680)
        self.setup_ui()
        self.load_all()

    def setup_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search inventory… (type, serial, size, assigned ID)")
        self.search.textChanged.connect(self.load_all)
        top.addWidget(self.search)

        self.section_filter = QComboBox()
        self.section_filter.addItems(["All Sections"] + SECTIONS)
        self.section_filter.currentIndexChanged.connect(self.load_all)
        top.addWidget(self.section_filter)

        export_btn = QPushButton("Export Inventory CSV")
        export_btn.clicked.connect(self.export_csv)
        top.addWidget(export_btn)

        root.addLayout(top)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.instr = QTableWidget(0, 8)
        self.instr.setHorizontalHeaderLabels(["ID", "Type", "Section", "Serial", "Condition", "Assigned To", "Date", "Available"])
        self._prep_table(self.instr)
        self.tabs.addTab(self.instr, "Instruments")

        self.uni = QTableWidget(0, 10)
        self.uni.setHorizontalHeaderLabels(["ID", "Coat", "Pant", "Coat #", "Pant #", "Condition", "Assigned To", "Date", "Available", "Size Key"])
        self._prep_table(self.uni)
        self.tabs.addTab(self.uni, "Uniforms")

        self.sha = QTableWidget(0, 7)
        self.sha.setHorizontalHeaderLabels(["ID", "Size", "Condition", "Assigned To", "Date", "Available", "Size Key"])
        self._prep_table(self.sha)
        self.tabs.addTab(self.sha, "Shakos")

        footer = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_all)
        footer.addWidget(refresh_btn)

        footer.addStretch()
        root.addLayout(footer)

    def _prep_table(self, t):
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.setWordWrap(False)
        t.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        t.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        t.setShowGrid(True)

    def load_all(self):
        q = self.search.text().strip()
        sec = self.section_filter.currentText()

        instr_where = []
        params = []

        if sec != "All Sections":
            instr_where.append("t.SECTION=?")
            params.append(sec)

        if q:
            instr_where.append("(t.TYPE_NAME LIKE ? OR COALESCE(i.SERIAL,'') LIKE ? OR COALESCE(i.CONDITION_NOTES,'') LIKE ? OR COALESCE(i.CHECKED_OUT_TO,'') LIKE ?)")
            params.extend([f"%{q}%"] * 4)

        instr_where_sql = ("WHERE " + " AND ".join(instr_where)) if instr_where else ""

        cur = self.conn.execute(f"""
            SELECT i.INSTRUMENT_ID, t.TYPE_NAME, t.SECTION,
                   COALESCE(i.SERIAL,''), COALESCE(i.CONDITION_NOTES,''),
                   COALESCE(i.CHECKED_OUT_TO,''), COALESCE(i.CHECKED_OUT_DATE,''),
                   CASE WHEN i.CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
            FROM INSTRUMENTS i
            JOIN INSTRUMENT_TYPES t ON i.TYPE_ID=t.TYPE_ID
            {instr_where_sql}
            ORDER BY t.SECTION, t.TYPE_NAME, i.INSTRUMENT_ID
        """, params)

        rows = cur.fetchall()
        self.instr.setRowCount(0)
        for r in rows:
            row = self.instr.rowCount()
            self.instr.insertRow(row)
            for c in range(8):
                self.instr.setItem(row, c, make_table_item(r[c]))
        self.instr.resizeColumnsToContents()

        u_where = []
        u_params = []

        if q:
            u_where.append("(COALESCE(COAT_SIZE,'') LIKE ? OR COALESCE(PANT_SIZE,'') LIKE ? OR COALESCE(COAT_NUMBER,'') LIKE ? OR COALESCE(PANT_NUMBER,'') LIKE ? OR COALESCE(CONDITION_NOTES,'') LIKE ? OR COALESCE(CHECKED_OUT_TO,'') LIKE ?)")
            u_params.extend([f"%{q}%"] * 6)
        u_where_sql = ("WHERE " + " AND ".join(u_where)) if u_where else ""

        cur = self.conn.execute(f"""
            SELECT UNIFORM_ID, COALESCE(COAT_SIZE,''), COALESCE(PANT_SIZE,''),
                   COALESCE(COAT_NUMBER,''), COALESCE(PANT_NUMBER,''),
                   COALESCE(CONDITION_NOTES,''),
                   COALESCE(CHECKED_OUT_TO,''), COALESCE(CHECKED_OUT_DATE,''),
                   CASE WHEN CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END,
                   (COALESCE(COAT_SIZE,'') || '/' || COALESCE(PANT_SIZE,''))
            FROM UNIFORMS
            {u_where_sql}
            ORDER BY (CHECKED_OUT_TO IS NULL) DESC, UNIFORM_ID
        """, u_params)

        rows = cur.fetchall()
        self.uni.setRowCount(0)
        for r in rows:
            row = self.uni.rowCount()
            self.uni.insertRow(row)
            for c in range(10):
                self.uni.setItem(row, c, make_table_item(r[c]))
        self.uni.resizeColumnsToContents()

        s_where = []
        s_params = []
        if q:
            s_where.append("(COALESCE(SIZE,'') LIKE ? OR COALESCE(CONDITION_NOTES,'') LIKE ? OR COALESCE(CHECKED_OUT_TO,'') LIKE ?)")
            s_params.extend([f"%{q}%"] * 3)
        s_where_sql = ("WHERE " + " AND ".join(s_where)) if s_where else ""

        cur = self.conn.execute(f"""
            SELECT SHAKO_ID, COALESCE(SIZE,''), COALESCE(CONDITION_NOTES,''),
                   COALESCE(CHECKED_OUT_TO,''), COALESCE(CHECKED_OUT_DATE,''),
                   CASE WHEN CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END,
                   COALESCE(SIZE,'')
            FROM SHAKOS
            {s_where_sql}
            ORDER BY (CHECKED_OUT_TO IS NULL) DESC, SHAKO_ID
        """, s_params)

        rows = cur.fetchall()
        self.sha.setRowCount(0)
        for r in rows:
            row = self.sha.rowCount()
            self.sha.insertRow(row)
            for c in range(7):
                self.sha.setItem(row, c, make_table_item(r[c]))
        self.sha.resizeColumnsToContents()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Inventory", "inventory.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["INSTRUMENTS"])
                w.writerow(["ID", "Type", "Section", "Serial", "Condition", "Assigned To", "Date", "Available"])
                cur = self.conn.execute("""
                    SELECT i.INSTRUMENT_ID, t.TYPE_NAME, t.SECTION, COALESCE(i.SERIAL,''), COALESCE(i.CONDITION_NOTES,''),
                           COALESCE(i.CHECKED_OUT_TO,''), COALESCE(i.CHECKED_OUT_DATE,''),
                           CASE WHEN i.CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
                    FROM INSTRUMENTS i
                    JOIN INSTRUMENT_TYPES t ON i.TYPE_ID=t.TYPE_ID
                    ORDER BY t.SECTION, t.TYPE_NAME, i.INSTRUMENT_ID
                """)
                for r in cur.fetchall():
                    w.writerow(list(r))

                w.writerow([])
                w.writerow(["UNIFORMS"])
                w.writerow(["ID", "Coat", "Pant", "Coat #", "Pant #", "Condition", "Assigned To", "Date", "Available"])
                cur = self.conn.execute("""
                    SELECT UNIFORM_ID, COALESCE(COAT_SIZE,''), COALESCE(PANT_SIZE,''), COALESCE(COAT_NUMBER,''), COALESCE(PANT_NUMBER,''),
                           COALESCE(CONDITION_NOTES,''), COALESCE(CHECKED_OUT_TO,''), COALESCE(CHECKED_OUT_DATE,''),
                           CASE WHEN CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
                    FROM UNIFORMS
                    ORDER BY (CHECKED_OUT_TO IS NULL) DESC, UNIFORM_ID
                """)
                for r in cur.fetchall():
                    w.writerow(list(r))

                w.writerow([])
                w.writerow(["SHAKOS"])
                w.writerow(["ID", "Size", "Condition", "Assigned To", "Date", "Available"])
                cur = self.conn.execute("""
                    SELECT SHAKO_ID, COALESCE(SIZE,''), COALESCE(CONDITION_NOTES,''), COALESCE(CHECKED_OUT_TO,''), COALESCE(CHECKED_OUT_DATE,''),
                           CASE WHEN CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
                    FROM SHAKOS
                    ORDER BY (CHECKED_OUT_TO IS NULL) DESC, SHAKO_ID
                """)
                for r in cur.fetchall():
                    w.writerow(list(r))
            self.show_message("Saved", f"Saved to:\n{path}")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

class BandDatabaseApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marching Band Database")

        self.conn = connect_db()
        create_tables(self.conn)
        seed_sample_data(self.conn)

        self.students_requires_school_year = (
            table_has_column(self.conn, "STUDENTS", "SCHOOL_YEAR") and
            any(r[1] == "SCHOOL_YEAR" and bool(r[3]) for r in table_info(self.conn, "STUDENTS"))
        )

        self.undo_stack = []

        self.current_zoom = 100
        self.current_font_size = 12
        self.high_contrast_mode = False

        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.root_layout = QVBoxLayout(main_widget)

        self.setup_menu_bar()

        self.tabs = QTabWidget()
        self.root_layout.addWidget(self.tabs)

        self.create_students_tab()
        self.create_uniforms_tab()
        self.create_shakos_tab()
        self.create_instruments_tab()

        self.status_bar = QLabel("Ready | Zoom: 100% | Normal Mode")
        self.status_bar.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                color: white;
                padding: 8px;
                border-top: 2px solid #cd7b00;
                font-weight: bold;
            }
        """)
        self.root_layout.addWidget(self.status_bar)

        self.setup_colors()
        self.refresh_all()
        self.rebuild_completers()

    def setup_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        inv_action = file_menu.addAction("Inventory Viewer")
        inv_action.setShortcut("Ctrl+I")
        inv_action.triggered.connect(self.open_inventory_viewer)

        comp_action = file_menu.addAction("Compliance Manager")
        comp_action.setShortcut("Ctrl+M")
        comp_action.triggered.connect(self.open_compliance_manager)

        file_menu.addSeparator()

        export_students = file_menu.addAction("Export Students CSV")
        export_students.triggered.connect(self.export_students_csv)

        export_inventory = file_menu.addAction("Export Inventory CSV")
        export_inventory.triggered.connect(self.export_inventory_csv)

        export_compliance = file_menu.addAction("Export Compliance CSV")
        export_compliance.triggered.connect(self.export_compliance_csv)

        file_menu.addSeparator()

        reset_db = file_menu.addAction("Reset Database (Wipe)")
        reset_db.setShortcut("Ctrl+Shift+R")
        reset_db.triggered.connect(self.reset_database)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)

        edit_menu = menubar.addMenu("&Edit")
        undo_action = edit_menu.addAction("&Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.undo_last)

        view_menu = menubar.addMenu("&View")
        self.students_columns_menu = view_menu.addMenu("Students Columns")
        self.students_col_actions = {}

        accessibility_menu = menubar.addMenu("&Accessibility")

        zoom_menu = accessibility_menu.addMenu("&Zoom")
        zoom_in_action = zoom_menu.addAction("Zoom In (+10%)")
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_in_action.setShortcut("Ctrl+=")

        zoom_out_action = zoom_menu.addAction("Zoom Out (-10%)")
        zoom_out_action.triggered.connect(self.zoom_out)
        zoom_out_action.setShortcut("Ctrl+-")

        reset_zoom_action = zoom_menu.addAction("Reset Zoom (100%)")
        reset_zoom_action.triggered.connect(self.reset_zoom)
        reset_zoom_action.setShortcut("Ctrl+0")

        accessibility_menu.addSeparator()

        fullscreen_action = accessibility_menu.addAction("Fullscreen")
        fullscreen_action.setCheckable(True)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)

        accessibility_menu.addSeparator()

        contrast_menu = accessibility_menu.addMenu("Contrast")
        normal_action = contrast_menu.addAction("Normal Contrast")
        normal_action.triggered.connect(lambda: self.enable_high_contrast_mode(False))
        high_action = contrast_menu.addAction("High Contrast Mode")
        high_action.triggered.connect(lambda: self.enable_high_contrast_mode(True))

        accessibility_menu.addSeparator()

        keyboard_action = accessibility_menu.addAction("Keyboard Navigation Help")
        keyboard_action.triggered.connect(self.show_keyboard_help)
        keyboard_action.setShortcut("F1")

    def setup_colors(self):
        if self.high_contrast_mode:
            self.setStyleSheet(self.get_high_contrast_stylesheet())
        else:
            self.setStyleSheet(self.get_normal_stylesheet())

    def set_button_icon_safe(self, btn, preferred_sp, fallback_text):
        try:
            btn.setIcon(self.style().standardIcon(preferred_sp))
        except Exception:
            btn.setText(fallback_text)

    def get_normal_stylesheet(self):
        return f"""
            QMainWindow {{
                background-color: #f5f7fa;
            }}
            QWidget {{
                font-family: Segoe UI, Arial, sans-serif;
                font-size: {self.current_font_size}px;
            }}
            QFrame#card {{
                background-color: white;
                border: 2px solid #d1d8e0;
                border-radius: 12px;
            }}
            QGroupBox {{
                border: 2px solid #d1d8e0;
                border-radius: 10px;
                margin-top: 22px;
                padding: 12px;
                padding-top: 18px;
                font-weight: bold;
                color: #2c3e50;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 2px;
                padding: 2px 8px;
                color: #cd7b00;
                background-color: white;
            }}
            QPushButton {{
                background-color: #cd7b00;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: bold;
                font-size: {self.current_font_size}px;
            }}
            QPushButton:hover {{
                background-color: #b36b00;
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #7f8c8d;
            }}
            QToolButton {{
                background-color: #d1d8e0;
                border: none;
                border-radius: 8px;
                padding: 6px;
            }}
            QToolButton:checked {{
                background-color: #cd7b00;
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                padding: 7px;
                background-color: white;
                color: #2c3e50;
                font-size: {self.current_font_size}px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 2px solid #cd7b00;
            }}

            QComboBox QAbstractItemView {{
                max-height: 160px;
            }}

            QTableWidget {{
                background-color: white;
                border: 1px solid #d1d8e0;
                gridline-color: rgba(44, 62, 80, 35);
                selection-background-color: #cd7b00;
                selection-color: white;
                font-size: {self.current_font_size}px;
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: #006600;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }}
            QTabWidget::pane {{
                border: 1px solid #d1d8e0;
                background-color: white;
                border-radius: 10px;
            }}
            QTabBar::tab {{
                background-color: #d1d8e0;
                color: #2c3e50;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: bold;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QTabBar::tab:selected {{
                background-color: #cd7b00;
                color: white;
            }}
            QLabel#highlight {{
                font-weight: bold;
                color: #e74c3c;
                font-size: {self.current_font_size + 1}px;
            }}
        """

    def get_high_contrast_stylesheet(self):
        return f"""
            QMainWindow {{
                background-color: #000000;
            }}
            QWidget {{
                font-family: Segoe UI, Arial, sans-serif;
                font-size: {max(self.current_font_size, 13)}px;
                color: #FFFFFF;
            }}
            QFrame#card {{
                background-color: white;
                border: 2px solid #d1d8e0;
                border-radius: 12px;
            }}
            QGroupBox {{
                border: 3px solid #FFFFFF;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                color: #FFFFFF;
                background-color: #000000;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #FFFF00;
                background-color: #000000;
            }}
            QPushButton {{
                background-color: #000000;
                color: #FFFFFF;
                border: 2px solid #FFFFFF;
                padding: 10px 18px;
                border-radius: 8px;
                font-weight: bold;
                font-size: {max(self.current_font_size, 13)}px;
            }}
            QPushButton:hover {{
                background-color: #333333;
                border: 3px solid #FFFF00;
            }}
            QToolButton {{
                background-color: #333333;
                border: 2px solid #FFFFFF;
                border-radius: 8px;
                padding: 6px;
            }}
            QToolButton:checked {{
                background-color: #0000FF;
                border-bottom: 3px solid #FFFF00;
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                border: 2px solid #FFFFFF;
                border-radius: 6px;
                padding: 8px;
                background-color: #000000;
                color: #FFFFFF;
                font-size: {max(self.current_font_size, 13)}px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 3px solid #00FFFF;
                background-color: #111111;
            }}

            QComboBox QAbstractItemView {{
                max-height: 160px;
            }}

            QTableWidget {{
                background-color: #000000;
                border: 2px solid #FFFFFF;
                gridline-color: rgba(255,255,255,80);
                selection-background-color: #0000FF;
                selection-color: #FFFFFF;
                alternate-background-color: #111111;
                font-size: {max(self.current_font_size, 13)}px;
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: #000000;
                color: #FFFFFF;
                padding: 10px;
                border: 1px solid #FFFFFF;
                font-weight: bold;
            }}
            QTabWidget::pane {{
                border: 2px solid #FFFFFF;
                background-color: #000000;
                border-radius: 10px;
            }}
            QTabBar::tab {{
                background-color: #333333;
                color: #FFFFFF;
                padding: 10px 18px;
                margin-right: 2px;
                font-weight: bold;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QTabBar::tab:selected {{
                background-color: #0000FF;
                color: #FFFFFF;
                border-bottom: 3px solid #FFFF00;
            }}
            QLabel#highlight {{
                font-weight: bold;
                color: #FFFF00;
                font-size: {max(self.current_font_size + 1, 14)}px;
                border: 1px solid #FFFF00;
                padding: 2px;
            }}
        """

    def apply_shadow(self, widget, blur=22, x=0, y=6):
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(blur)
        eff.setOffset(x, y)
        eff.setColor(Qt.black)
        widget.setGraphicsEffect(eff)

    def push_undo_ops(self, label, undo_ops):
        self.undo_stack.append((label, undo_ops))
        self.update_status(f"{label} | Undo ready")

    def undo_last(self):
        if not self.undo_stack:
            self.show_error("Nothing to undo")
            return
        label, ops = self.undo_stack.pop()
        try:
            self.conn.execute("BEGIN")
            for sql, params in ops:
                self.conn.execute(sql, params)
            self.conn.commit()
            self.refresh_all()
            self.update_status(f"Undid: {label}")
        except Exception as e:
            self.conn.rollback()
            self.show_error(f"Undo failed: {str(e)}")

    def update_status(self, message):
        mode = "High Contrast" if self.high_contrast_mode else "Normal"
        self.status_bar.setText(f"{message} | Zoom: {self.current_zoom}% | {mode} Mode")

    def show_message(self, title, message):
        QMessageBox.information(self, title, message)

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)

    def ask_yes_no(self, title, question):
        reply = QMessageBox.question(self, title, question, QMessageBox.Yes | QMessageBox.No)
        return reply == QMessageBox.Yes

    def validate_required(self, field: QLineEdit):
        ok = bool(field.text().strip())
        field.setStyleSheet("" if ok else "border: 2px solid #e74c3c;")
        return ok

    def rebuild_completers(self):
        cur = self.conn.execute("SELECT STUDENT_ID FROM STUDENTS ORDER BY STUDENT_ID")
        ids = [str(r[0]) for r in cur.fetchall()]
        completer = QCompleter(ids)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        for le in [self.add_id, self.edit_id_readonly, self.assign_instr_student, self.assign_uni_student, self.assign_shako_student]:
            le.setCompleter(completer)

    def toggle_fullscreen(self, checked):
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def open_compliance_manager(self):
        dlg = ComplianceDialog(self, self.conn)
        dlg.exec()

    def open_inventory_viewer(self):
        dlg = InventoryDialog(self, self.conn)
        dlg.exec()

    def export_students_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Students", "students.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            cur = self.conn.execute("""
                SELECT STUDENT_ID, FNAME, LNAME, COALESCE(CLASSIFICATION,''), COALESCE(SECTION,''),
                       COALESCE(PRIMARY_ROLE,''), COALESCE(SHIRT_SIZE,''), COALESCE(SHOE_SIZE,''), COALESCE(ACTIVE,1), COALESCE(UPDATED_AT,'')
                FROM STUDENTS
                ORDER BY SECTION, LNAME, FNAME
            """)
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Student ID", "First", "Last", "Class", "Section", "Instrument", "Shirt", "Shoe", "Active", "Updated"])
                for r in cur.fetchall():
                    w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], "Yes" if r[8] == 1 else "No", r[9]])
            self.show_message("Saved", f"Saved to:\n{path}")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def export_inventory_csv(self):
        dlg = InventoryDialog(self, self.conn)
        dlg.export_csv()

    def export_compliance_csv(self):
        dlg = ComplianceDialog(self, self.conn)
        dlg.export_csv()

    def reset_database(self):
        if not self.ask_yes_no("Reset Database", "Wipe EVERYTHING and start fresh? This cannot be undone."):
            return
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
        except Exception as e:
            self.show_error(f"Could not remove database file: {str(e)}")
            self.conn = connect_db()
            create_tables(self.conn)
            return

        self.conn = connect_db()
        create_tables(self.conn)
        self.undo_stack.clear()
        self.refresh_all()
        self.rebuild_completers()
        self.update_status("Database reset")

    def zoom_in(self):
        self.current_zoom = min(200, self.current_zoom + 10)
        self.current_font_size = int(12 * (self.current_zoom / 100))
        self.setup_colors()
        self.update_status("Zoom updated")

    def zoom_out(self):
        self.current_zoom = max(50, self.current_zoom - 10)
        self.current_font_size = int(12 * (self.current_zoom / 100))
        self.setup_colors()
        self.update_status("Zoom updated")

    def reset_zoom(self):
        self.current_zoom = 100
        self.current_font_size = 12
        self.setup_colors()
        self.update_status("Zoom reset")

    def enable_high_contrast_mode(self, enable):
        self.high_contrast_mode = enable
        self.setup_colors()
        mode = "High Contrast" if enable else "Normal"
        self.update_status(f"{mode} Mode enabled")

    def show_keyboard_help(self):
        help_text = """
KEYBOARD SHORTCUTS

General:
• Tab / Shift+Tab: Move focus
• Enter: Activate button / confirm
• Ctrl+Z: Undo
• Ctrl+I: Inventory Viewer
• Ctrl+M: Compliance Manager
• F11: Fullscreen

Accessibility:
• Ctrl+= : Zoom in
• Ctrl+- : Zoom out
• Ctrl+0 : Reset zoom
"""
        QMessageBox.information(self, "Keyboard Help", help_text)

    # STUDENTS MENU
    def create_students_tab(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Students")
        layout = QVBoxLayout(tab)

        header = QHBoxLayout()
        title = QLabel("Roster")
        title.setStyleSheet("font-weight: bold; padding: 0px; margin: 0px;")
        header.addWidget(title)
        header.addStretch()
        header.setSpacing(4)
        header.setContentsMargins(0, 0, 0, 0)

        layout.addLayout(header)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        search_row.setContentsMargins(0, 0, 0, 0)

        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Search roster… (ID, name, section, instrument)")
        self.student_search.textChanged.connect(self.load_students)
        search_row.addWidget(self.student_search)

        self.active_only = QCheckBox("Active only")
        self.active_only.setChecked(True)
        self.active_only.stateChanged.connect(self.load_students)
        search_row.addWidget(self.active_only)

        layout.addLayout(search_row)

        self.students_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.students_splitter)

        roster_wrap = QWidget()
        roster_layout = QVBoxLayout(roster_wrap)
        roster_layout.setContentsMargins(0, 0, 0, 0)

        self.students_table = QTableWidget(0, 10)
        self.students_table.setHorizontalHeaderLabels([
            "ID", "First", "Last", "Class", "Section", "Instrument", "Shirt", "Shoe", "Active", "Eligible"
        ])
        self.students_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.students_table.setAlternatingRowColors(True)
        self.students_table.verticalHeader().setVisible(False)
        self.students_table.horizontalHeader().setStretchLastSection(True)
        self.students_table.setWordWrap(False)
        self.students_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.students_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.students_table.itemSelectionChanged.connect(self.on_student_selected)
        self.students_table.setShowGrid(True)
        roster_layout.addWidget(self.students_table)

        roster_controls = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_students)
        roster_controls.addWidget(refresh_btn)

        self.find_id = QLineEdit()
        self.find_id.setPlaceholderText("Type ID to jump…")
        self.find_id.returnPressed.connect(self.jump_to_student)
        roster_controls.addWidget(self.find_id)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_student)
        roster_controls.addWidget(delete_btn)

        roster_controls.addStretch()
        roster_layout.addLayout(roster_controls)

        forms_wrap = QWidget()
        forms_layout = QVBoxLayout(forms_wrap)
        forms_layout.setContentsMargins(0, 0, 0, 0)

        self.student_forms_tabs = QTabWidget()
        forms_layout.addWidget(self.student_forms_tabs)

        add_tab = QWidget()
        add_layout = QHBoxLayout(add_tab)

        add_group = QGroupBox("Add Student")
        add_form = QFormLayout(add_group)

        self.add_id = QLineEdit()
        self.add_id.setPlaceholderText("Student ID")
        self.add_id.textChanged.connect(lambda: self.validate_required(self.add_id))
        add_form.addRow("Student ID*:", self.add_id)

        self.add_first = QLineEdit()
        add_form.addRow("First Name*:", self.add_first)

        self.add_last = QLineEdit()
        add_form.addRow("Last Name*:", self.add_last)

        self.add_class = QComboBox()
        self.add_class.addItems(CLASSIFICATIONS)
        add_form.addRow("Class:", self.add_class)

        self.add_section = QComboBox()
        self.add_section.addItems(SECTIONS)
        add_form.addRow("Section*:", self.add_section)

        self.add_role = QComboBox()
        self.add_role.addItems([""] + [x[0] for x in INSTRUMENT_CATALOG] + ["DRUM MAJOR", "OTHER"])
        add_form.addRow("Instrument:", self.add_role)

        self.add_shirt = QComboBox()
        self.add_shirt.addItems(SHIRT_SIZES)
        add_form.addRow("Shirt Size:", self.add_shirt)

        self.add_shoe = QComboBox()
        self.add_shoe.addItems(SHOE_SIZES)
        add_form.addRow("Shoe Size:", self.add_shoe)

        self.add_active = QCheckBox("Active")
        self.add_active.setChecked(True)
        add_form.addRow("", self.add_active)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_student)
        add_form.addRow(add_btn)

        add_layout.addWidget(add_group)
        add_layout.addStretch()
        self.student_forms_tabs.addTab(add_tab, "Add")

        edit_tab = QWidget()
        edit_layout = QHBoxLayout(edit_tab)

        edit_group = QGroupBox("Edit Selected Student")
        edit_form = QFormLayout(edit_group)

        self.edit_id_readonly = QLineEdit()
        self.edit_id_readonly.setReadOnly(True)
        edit_form.addRow("Student ID:", self.edit_id_readonly)

        self.edit_first = QLineEdit()
        edit_form.addRow("First Name*:", self.edit_first)

        self.edit_last = QLineEdit()
        edit_form.addRow("Last Name*:", self.edit_last)

        self.edit_class = QComboBox()
        self.edit_class.addItems(CLASSIFICATIONS)
        edit_form.addRow("Class:", self.edit_class)

        self.edit_section = QComboBox()
        self.edit_section.addItems(SECTIONS)
        edit_form.addRow("Section*:", self.edit_section)

        self.edit_role = QComboBox()
        self.edit_role.addItems([""] + [x[0] for x in INSTRUMENT_CATALOG] + ["DRUM MAJOR", "OTHER"])
        edit_form.addRow("Instrument:", self.edit_role)

        self.edit_shirt = QComboBox()
        self.edit_shirt.addItems(SHIRT_SIZES)
        edit_form.addRow("Shirt Size:", self.edit_shirt)

        self.edit_shoe = QComboBox()
        self.edit_shoe.addItems(SHOE_SIZES)
        edit_form.addRow("Shoe Size:", self.edit_shoe)

        self.edit_active = QCheckBox("Active")
        edit_form.addRow("", self.edit_active)

        self.edit_save = QPushButton("Save Changes")
        self.edit_save.setEnabled(False)
        self.edit_save.clicked.connect(self.save_student_edits)
        edit_form.addRow(self.edit_save)

        edit_layout.addWidget(edit_group)
        edit_layout.addStretch()
        self.student_forms_tabs.addTab(edit_tab, "Edit")

        self.students_splitter.addWidget(roster_wrap)
        self.students_splitter.addWidget(forms_wrap)
        self.students_splitter.setSizes([850, 450])

        self.students_splitter.setHandleWidth(10)
        self.students_splitter.setChildrenCollapsible(True)
        self.students_splitter.setSizes([500, 250])

        self.students_splitter.setStretchFactor(0, 4)
        self.students_splitter.setStretchFactor(1, 2)

        self.apply_shadow(add_group)
        self.apply_shadow(edit_group)

        self.build_students_columns_menu()

    def build_students_columns_menu(self):
        self.students_columns_menu.clear()
        self.students_col_actions.clear()

        names = [self.students_table.horizontalHeaderItem(i).text() for i in range(self.students_table.columnCount())]
        for idx, name in enumerate(names):
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(True)
            act.toggled.connect(lambda checked, c=idx: self.students_table.setColumnHidden(c, not checked))
            self.students_columns_menu.addAction(act)
            self.students_col_actions[idx] = act

        default_hide = ["Shirt", "Shoe"]
        for idx, act in self.students_col_actions.items():
            if act.text() in default_hide:
                act.setChecked(False)

    def load_students(self):
        q = self.student_search.text().strip()
        active_only = self.active_only.isChecked()

        where = []
        params = []

        if active_only:
            where.append("COALESCE(s.ACTIVE, 1) = 1")

        if q:
            where.append("(s.STUDENT_ID LIKE ? OR s.FNAME LIKE ? OR s.LNAME LIKE ? OR COALESCE(s.SECTION,'') LIKE ? OR COALESCE(s.PRIMARY_ROLE,'') LIKE ?)")
            params.extend([f"%{q}%"] * 5)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cur = self.conn.execute(f"""
            SELECT s.STUDENT_ID, s.FNAME, s.LNAME,
                   COALESCE(s.CLASSIFICATION,''), COALESCE(s.SECTION,''),
                   COALESCE(s.PRIMARY_ROLE,''), COALESCE(s.SHIRT_SIZE,''), COALESCE(s.SHOE_SIZE,''),
                   COALESCE(s.ACTIVE,1),
                   COALESCE(c.CREDIT_HOURS, 0), COALESCE(c.GPA, 0.0), COALESCE(c.DUES_PAID, 0)
            FROM STUDENTS s
            LEFT JOIN COMPLIANCE c ON s.STUDENT_ID = c.STUDENT_ID
            {where_sql}
            ORDER BY s.SECTION, s.LNAME, s.FNAME
        """, params)

        rows = cur.fetchall()
        self.students_table.setRowCount(0)
        for r in rows:
            sid, fn, ln, cl, sec, role, shirt, shoe, active, credits, gpa, dues = r
            eligible = is_eligible(credits, gpa, dues)

            row = self.students_table.rowCount()
            self.students_table.insertRow(row)
            self.students_table.setItem(row, 0, make_table_item(sid, True))
            self.students_table.setItem(row, 1, make_table_item(fn))
            self.students_table.setItem(row, 2, make_table_item(ln))
            self.students_table.setItem(row, 3, make_table_item(cl))
            self.students_table.setItem(row, 4, make_table_item(sec))
            self.students_table.setItem(row, 5, make_table_item(role))
            self.students_table.setItem(row, 6, make_table_item(shirt))
            self.students_table.setItem(row, 7, make_table_item(shoe))
            self.students_table.setItem(row, 8, make_table_item("Yes" if active == 1 else "No"))
            self.students_table.setItem(row, 9, make_table_item("YES" if eligible else "NO", align_center=True))

        self.students_table.resizeColumnsToContents()
        self.update_status(f"Loaded {len(rows)} students")
        self.rebuild_completers()

    def jump_to_student(self):
        sid = self.find_id.text().strip()
        if not sid.isdigit():
            self.show_error("Enter a valid numeric ID")
            return
        for r in range(self.students_table.rowCount()):
            if self.students_table.item(r, 0).text() == sid:
                self.students_table.selectRow(r)
                self.students_table.scrollToItem(self.students_table.item(r, 0), QAbstractItemView.PositionAtCenter)
                return
        self.show_error("Student not found in current view")

    def on_student_selected(self):
        row = self.students_table.currentRow()
        if row < 0:
            self.edit_id_readonly.clear()
            self.edit_save.setEnabled(False)
            return

        sid = int(self.students_table.item(row, 0).text())
        cur = self.conn.execute("""
            SELECT STUDENT_ID, FNAME, LNAME, COALESCE(CLASSIFICATION,''), COALESCE(SECTION,''), COALESCE(PRIMARY_ROLE,''),
                   COALESCE(SHIRT_SIZE,''), COALESCE(SHOE_SIZE,''), COALESCE(ACTIVE,1)
            FROM STUDENTS
            WHERE STUDENT_ID=?
        """, (sid,))
        s = cur.fetchone()
        if not s:
            return

        self.edit_id_readonly.setText(str(s[0]))
        self.edit_first.setText(s[1])
        self.edit_last.setText(s[2])

        self.edit_class.setCurrentText(s[3] if s[3] in CLASSIFICATIONS else "")
        self.edit_section.setCurrentText(s[4] if s[4] in SECTIONS else "OTHER")

        role_texts = [self.edit_role.itemText(i) for i in range(self.edit_role.count())]
        self.edit_role.setCurrentText(s[5] if s[5] in role_texts else "")

        self.edit_shirt.setCurrentText(s[6] if s[6] in SHIRT_SIZES else "")
        self.edit_shoe.setCurrentText(s[7] if s[7] in SHOE_SIZES else "")
        self.edit_active.setChecked(True if s[8] == 1 else False)

        self.edit_save.setEnabled(True)

    def add_student(self):
        ok_id = self.validate_required(self.add_id)
        ok_fn = bool(self.add_first.text().strip())
        ok_ln = bool(self.add_last.text().strip())

        if not ok_id:
            self.show_error("Student ID is required")
            return
        if not ok_fn or not ok_ln:
            self.show_error("First and Last name are required")
            return

        sid_txt = self.add_id.text().strip()
        if not sid_txt.isdigit():
            self.show_error("Student ID must be numeric")
            self.add_id.setStyleSheet("border: 2px solid #e74c3c;")
            return

        sid = int(sid_txt)

        if check_student_exists(self.conn, sid):
            self.show_error("Student ID already exists")
            self.add_id.setStyleSheet("border: 2px solid #e74c3c;")
            return

        fn = self.add_first.text().strip()
        ln = self.add_last.text().strip()
        cl = self.add_class.currentText()
        sec = self.add_section.currentText()
        role = self.add_role.currentText().strip() or None
        shirt = self.add_shirt.currentText().strip() or None
        shoe = self.add_shoe.currentText().strip() or None
        active = 1 if self.add_active.isChecked() else 0
        updated = date.today().isoformat()

        ops = [
            ("INSERT INTO STUDENTS (STUDENT_ID, FNAME, LNAME, CLASSIFICATION, SECTION, PRIMARY_ROLE, SHIRT_SIZE, SHOE_SIZE, ACTIVE, UPDATED_AT) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
             (sid, fn, ln, cl, sec, role, shirt, shoe, active, updated)),
            ("INSERT OR IGNORE INTO COMPLIANCE (STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE) VALUES (?, 0, 0.0, 0, ?)",
             (sid, updated))
        ]
        undo_ops = [
            ("DELETE FROM STUDENTS WHERE STUDENT_ID=?", (sid,))
        ]

        try:
            self.conn.execute("BEGIN")
            for sql, params in ops:
                self.conn.execute(sql, params)
            self.conn.commit()
            self.push_undo_ops("Add Student", undo_ops)

            self.add_id.clear()
            self.add_first.clear()
            self.add_last.clear()
            self.add_class.setCurrentIndex(0)
            self.add_section.setCurrentIndex(0)
            self.add_role.setCurrentIndex(0)
            self.add_shirt.setCurrentIndex(0)
            self.add_shoe.setCurrentIndex(0)
            self.add_active.setChecked(True)

            self.refresh_all()
            self.update_status("Student added")
        except Exception as e:
            self.conn.rollback()
            self.show_error(f"Error: {str(e)}")

    def save_student_edits(self):
        sid_txt = self.edit_id_readonly.text().strip()
        if not sid_txt.isdigit():
            return
        sid = int(sid_txt)

        fn = self.edit_first.text().strip()
        ln = self.edit_last.text().strip()
        if not fn or not ln:
            self.show_error("First and Last name are required")
            return

        cl = self.edit_class.currentText()
        sec = self.edit_section.currentText()
        role = self.edit_role.currentText().strip() or None
        shirt = self.edit_shirt.currentText().strip() or None
        shoe = self.edit_shoe.currentText().strip() or None
        active = 1 if self.edit_active.isChecked() else 0
        updated = date.today().isoformat()

        cur = self.conn.execute("""
            SELECT FNAME, LNAME, COALESCE(CLASSIFICATION,''), COALESCE(SECTION,''), COALESCE(PRIMARY_ROLE,''),
                   COALESCE(SHIRT_SIZE,''), COALESCE(SHOE_SIZE,''), COALESCE(ACTIVE,1), COALESCE(UPDATED_AT,'')
            FROM STUDENTS WHERE STUDENT_ID=?
        """, (sid,))
        old = cur.fetchone()
        if not old:
            return

        ops = [
            ("UPDATE STUDENTS SET FNAME=?, LNAME=?, CLASSIFICATION=?, SECTION=?, PRIMARY_ROLE=?, SHIRT_SIZE=?, SHOE_SIZE=?, ACTIVE=?, UPDATED_AT=? WHERE STUDENT_ID=?",
             (fn, ln, cl, sec, role, shirt, shoe, active, updated, sid))
        ]
        undo_ops = [
            ("UPDATE STUDENTS SET FNAME=?, LNAME=?, CLASSIFICATION=?, SECTION=?, PRIMARY_ROLE=?, SHIRT_SIZE=?, SHOE_SIZE=?, ACTIVE=?, UPDATED_AT=? WHERE STUDENT_ID=?",
             (old[0], old[1], old[2], old[3], old[4] or None, old[5] or None, old[6] or None, old[7], old[8], sid))
        ]

        try:
            self.conn.execute("BEGIN")
            for sql, params in ops:
                self.conn.execute(sql, params)
            self.conn.commit()
            self.push_undo_ops("Edit Student", undo_ops)
            self.refresh_all()
            self.update_status("Student updated")
        except Exception as e:
            self.conn.rollback()
            self.show_error(f"Error: {str(e)}")

    def delete_student(self):
        row = self.students_table.currentRow()
        if row < 0:
            self.show_error("Select a student first")
            return

        sid = int(self.students_table.item(row, 0).text())
        name = f"{self.students_table.item(row, 1).text()} {self.students_table.item(row, 2).text()}"

        if not self.ask_yes_no("Confirm Delete", f"Delete {name} (ID: {sid})?"):
            return

        cur = self.conn.execute("""
            SELECT STUDENT_ID, FNAME, LNAME, COALESCE(CLASSIFICATION,''), COALESCE(SECTION,''), COALESCE(PRIMARY_ROLE,''),
                   COALESCE(SHIRT_SIZE,''), COALESCE(SHOE_SIZE,''), COALESCE(ACTIVE,1), COALESCE(UPDATED_AT,'')
            FROM STUDENTS WHERE STUDENT_ID=?
        """, (sid,))
        student = cur.fetchone()

        cur = self.conn.execute("""
            SELECT STUDENT_ID, COALESCE(CREDIT_HOURS,0), COALESCE(GPA,0.0), COALESCE(DUES_PAID,0), COALESCE(LAST_VERIFIED_DATE,'')
            FROM COMPLIANCE WHERE STUDENT_ID=?
        """, (sid,))
        compliance = cur.fetchone()

        cur = self.conn.execute("SELECT INSTRUMENT_ID, COALESCE(CHECKED_OUT_DATE,''), COALESCE(CONDITION_NOTES,'') FROM INSTRUMENTS WHERE CHECKED_OUT_TO=?", (sid,))
        instr_hold = cur.fetchone()

        cur = self.conn.execute("SELECT UNIFORM_ID, COALESCE(CHECKED_OUT_DATE,''), COALESCE(CONDITION_NOTES,'') FROM UNIFORMS WHERE CHECKED_OUT_TO=?", (sid,))
        uni_hold = cur.fetchone()

        cur = self.conn.execute("SELECT SHAKO_ID, COALESCE(CHECKED_OUT_DATE,''), COALESCE(CONDITION_NOTES,'') FROM SHAKOS WHERE CHECKED_OUT_TO=?", (sid,))
        shako_hold = cur.fetchone()

        undo_ops = []

        if student:
            undo_ops.append((
                "INSERT INTO STUDENTS (STUDENT_ID, FNAME, LNAME, CLASSIFICATION, SECTION, PRIMARY_ROLE, SHIRT_SIZE, SHOE_SIZE, ACTIVE, UPDATED_AT) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(STUDENT_ID) DO UPDATE SET FNAME=excluded.FNAME, LNAME=excluded.LNAME, CLASSIFICATION=excluded.CLASSIFICATION, SECTION=excluded.SECTION, PRIMARY_ROLE=excluded.PRIMARY_ROLE, SHIRT_SIZE=excluded.SHIRT_SIZE, SHOE_SIZE=excluded.SHOE_SIZE, ACTIVE=excluded.ACTIVE, UPDATED_AT=excluded.UPDATED_AT",
                (student[0], student[1], student[2], student[3], student[4], student[5] or None, student[6] or None, student[7] or None, student[8], student[9])
            ))

        if compliance:
            undo_ops.append((
                "INSERT INTO COMPLIANCE (STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(STUDENT_ID) DO UPDATE SET CREDIT_HOURS=excluded.CREDIT_HOURS, GPA=excluded.GPA, DUES_PAID=excluded.DUES_PAID, LAST_VERIFIED_DATE=excluded.LAST_VERIFIED_DATE",
                (compliance[0], compliance[1], compliance[2], compliance[3], compliance[4])
            ))

        if instr_hold:
            undo_ops.append((
                "UPDATE INSTRUMENTS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE INSTRUMENT_ID=?",
                (sid, instr_hold[1] or None, instr_hold[2] or None, instr_hold[0])
            ))

        if uni_hold:
            undo_ops.append((
                "UPDATE UNIFORMS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE UNIFORM_ID=?",
                (sid, uni_hold[1] or None, uni_hold[2] or None, uni_hold[0])
            ))

        if shako_hold:
            undo_ops.append((
                "UPDATE SHAKOS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE SHAKO_ID=?",
                (sid, shako_hold[1] or None, shako_hold[2] or None, shako_hold[0])
            ))

        try:
            self.conn.execute("DELETE FROM STUDENTS WHERE STUDENT_ID=?", (sid,))
            self.conn.commit()
            self.push_undo_ops("Delete Student", undo_ops)
            self.refresh_all()
            self.update_status("Student deleted")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    # UNIFORM MENU
    def create_uniforms_tab(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Uniforms")
        layout = QVBoxLayout(tab)

        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        top = QHBoxLayout()
        self.uniform_search = QLineEdit()
        self.uniform_search.setPlaceholderText("Search uniforms…")
        self.uniform_search.textChanged.connect(self.load_uniforms)
        top.addWidget(self.uniform_search)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_uniforms)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

       
        self.uniforms_table = QTableWidget(0, 9)
        self.uniforms_table.setHorizontalHeaderLabels([
            "ID", "Coat Size", "Pant Size", "Coat #", "Pant #",
            "Condition", "Assigned To", "Date", "Available"
        ])
        self.uniforms_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.uniforms_table.setAlternatingRowColors(True)
        self.uniforms_table.verticalHeader().setVisible(False)
        self.uniforms_table.horizontalHeader().setStretchLastSection(True)
        self.uniforms_table.setWordWrap(False)
        self.uniforms_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.uniforms_table.setShowGrid(True)
        layout.addWidget(self.uniforms_table)

        forms_row = QHBoxLayout()
        forms_row.setSpacing(12)

        add_card = QFrame()
        add_card.setObjectName("card")
        add_card_layout = QVBoxLayout(add_card)
        add_card_layout.setContentsMargins(12, 12, 12, 12)

        add_group = QGroupBox("Add Uniform")
        add_group.setStyleSheet("border: none;")  
        add_form = QFormLayout(add_group)

        self.coat_size = QLineEdit()
        add_form.addRow("Coat Size:", self.coat_size)

        self.pant_size = QLineEdit()
        add_form.addRow("Pant Size:", self.pant_size)

        self.coat_number = QLineEdit()
        add_form.addRow("Coat #:", self.coat_number)

        self.pant_number = QLineEdit()
        add_form.addRow("Pant #:", self.pant_number)

        self.uniform_condition = QLineEdit()
        add_form.addRow("Condition:", self.uniform_condition)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_uniform)
        add_form.addRow(add_btn)

        add_card_layout.addWidget(add_group)
        self.apply_shadow(add_card)

        assign_card = QFrame()
        assign_card.setObjectName("card")
        assign_card_layout = QVBoxLayout(assign_card)
        assign_card_layout.setContentsMargins(12, 12, 12, 12)

        assign_group = QGroupBox("Assign / Unassign")
        assign_group.setStyleSheet("border: none;")
        assign_form = QFormLayout(assign_group)

        self.assign_uni_student = QLineEdit()
        self.assign_uni_student.setPlaceholderText("Student ID")
        self.assign_uni_student.textChanged.connect(
            lambda: self.show_student_preview(self.assign_uni_student, self.uni_preview)
        )
        assign_form.addRow("Student ID*:", self.assign_uni_student)

        self.uni_preview = QLabel("")
        assign_form.addRow("Student:", self.uni_preview)

        assign_btn = QPushButton("Assign")
        assign_btn.clicked.connect(self.assign_uniform)
        assign_form.addRow(assign_btn)

        unassign_btn = QPushButton("Unassign")
        unassign_btn.clicked.connect(self.unassign_uniform)
        assign_form.addRow(unassign_btn)

        assign_card_layout.addWidget(assign_group)
        self.apply_shadow(assign_card)

        forms_row.addWidget(add_card)
        forms_row.addWidget(assign_card)
        layout.addLayout(forms_row)

    def load_uniforms(self):
        q = self.uniform_search.text().strip()
        where = ""
        params = []
        if q:
            where = """WHERE COALESCE(COAT_SIZE,'') LIKE ? OR COALESCE(PANT_SIZE,'') LIKE ?
                       OR COALESCE(COAT_NUMBER,'') LIKE ? OR COALESCE(PANT_NUMBER,'') LIKE ?
                       OR COALESCE(CONDITION_NOTES,'') LIKE ? OR COALESCE(CHECKED_OUT_TO,'') LIKE ?"""
            params = [f"%{q}%"] * 6

        cur = self.conn.execute(f"""
            SELECT UNIFORM_ID, COALESCE(COAT_SIZE,''), COALESCE(PANT_SIZE,''),
                   COALESCE(COAT_NUMBER,''), COALESCE(PANT_NUMBER,''),
                   COALESCE(CONDITION_NOTES,''),
                   COALESCE(CHECKED_OUT_TO,''), COALESCE(CHECKED_OUT_DATE,''),
                   CASE WHEN CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
            FROM UNIFORMS
            {where}
            ORDER BY (CHECKED_OUT_TO IS NULL) DESC, UNIFORM_ID
        """, params)

        self.uniforms_table.setRowCount(0)
        for r in cur.fetchall():
            row = self.uniforms_table.rowCount()
            self.uniforms_table.insertRow(row)
            for c in range(9):
                self.uniforms_table.setItem(row, c, make_table_item(r[c]))

        self.uniforms_table.resizeColumnsToContents()
        self.update_status(f"Loaded {self.uniforms_table.rowCount()} uniforms")

    def add_uniform(self):
        coat = self.coat_size.text().strip() or None
        pant = self.pant_size.text().strip() or None
        coatn = self.coat_number.text().strip() or None
        pantn = self.pant_number.text().strip() or None
        cond = self.uniform_condition.text().strip() or None

        try:
            self.conn.execute(
                "INSERT INTO UNIFORMS (COAT_SIZE, PANT_SIZE, COAT_NUMBER, PANT_NUMBER, CONDITION_NOTES) VALUES (?, ?, ?, ?, ?)",
                (coat, pant, coatn, pantn, cond)
            )
            uid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self.conn.commit()
            self.push_undo_ops("Add Uniform", [("DELETE FROM UNIFORMS WHERE UNIFORM_ID=?", (uid,))])

            self.coat_size.clear()
            self.pant_size.clear()
            self.coat_number.clear()
            self.pant_number.clear()
            self.uniform_condition.clear()

            self.refresh_all()
            self.update_status("Uniform added")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def get_selected_uniform_id(self):
        row = self.uniforms_table.currentRow()
        if row < 0:
            return None
        return int(self.uniforms_table.item(row, 0).text())

    def show_student_preview(self, field, label):
        txt = field.text().strip()
        if txt.isdigit() and check_student_exists(self.conn, int(txt)):
            label.setText(get_student_name(self.conn, int(txt)))
        else:
            label.setText("")

    def assign_uniform(self):
        uid = self.get_selected_uniform_id()
        if not uid:
            self.show_error("Select a uniform first")
            return

        if not self.validate_required(self.assign_uni_student):
            self.show_error("Student ID is required")
            return

        sid_txt = self.assign_uni_student.text().strip()
        if not sid_txt.isdigit():
            self.show_error("Student ID must be numeric")
            return
        sid = int(sid_txt)

        if not check_student_exists(self.conn, sid):
            self.show_error("Student not found")
            return

        cur = self.conn.execute("SELECT CHECKED_OUT_TO, CHECKED_OUT_DATE, COALESCE(CONDITION_NOTES,'') FROM UNIFORMS WHERE UNIFORM_ID=?", (uid,))
        old_to, old_date, old_cond = cur.fetchone()

        if old_to:
            self.show_error("That uniform is already assigned")
            return

        cond, ok = QInputDialog.getText(self, "Condition", "Condition notes (optional):")
        if not ok:
            return

        try:
            self.conn.execute("""
                UPDATE UNIFORMS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=?
                WHERE UNIFORM_ID=? AND CHECKED_OUT_TO IS NULL
            """, (sid, date.today().isoformat(), cond.strip() or old_cond or None, uid))
            self.conn.commit()

            undo_ops = [("UPDATE UNIFORMS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE UNIFORM_ID=?",
                         (old_to, old_date, old_cond or None, uid))]
            self.push_undo_ops("Assign Uniform", undo_ops)

            self.assign_uni_student.clear()
            self.uni_preview.setText("")
            self.refresh_all()
            self.update_status("Uniform assigned")
        except sqlite3.IntegrityError:
            self.show_error("Student can only hold one uniform")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def unassign_uniform(self):
        uid = self.get_selected_uniform_id()
        if not uid:
            self.show_error("Select a uniform first")
            return

        cur = self.conn.execute("SELECT CHECKED_OUT_TO, CHECKED_OUT_DATE, COALESCE(CONDITION_NOTES,'') FROM UNIFORMS WHERE UNIFORM_ID=?", (uid,))
        old_to, old_date, old_cond = cur.fetchone()

        if not old_to:
            self.show_error("That uniform is not assigned")
            return

        cond, ok = QInputDialog.getText(self, "Condition Update", "Condition notes after return (optional):")
        if not ok:
            return

        new_cond = cond.strip() or old_cond or None

        try:
            self.conn.execute("""
                UPDATE UNIFORMS SET CHECKED_OUT_TO=NULL, CHECKED_OUT_DATE=NULL, CONDITION_NOTES=?
                WHERE UNIFORM_ID=?
            """, (new_cond, uid))
            self.conn.commit()

            undo_ops = [("UPDATE UNIFORMS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE UNIFORM_ID=?",
                         (old_to, old_date, old_cond or None, uid))]
            self.push_undo_ops("Unassign Uniform", undo_ops)

            self.refresh_all()
            self.update_status("Uniform unassigned")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    # SHAKO MENU
    def create_shakos_tab(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Shakos")
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        self.shako_search = QLineEdit()
        self.shako_search.setPlaceholderText("Search shakos…")
        self.shako_search.textChanged.connect(self.load_shakos)
        top.addWidget(self.shako_search)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_shakos)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        self.shakos_table = QTableWidget(0, 6)
        self.shakos_table.setHorizontalHeaderLabels([
            "ID", "Size", "Condition", "Assigned To", "Date", "Available"
        ])
        self.shakos_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.shakos_table.setAlternatingRowColors(True)
        self.shakos_table.verticalHeader().setVisible(False)
        self.shakos_table.horizontalHeader().setStretchLastSection(True)
        self.shakos_table.setWordWrap(False)
        self.shakos_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.shakos_table.setShowGrid(True)
        layout.addWidget(self.shakos_table)

        forms_row = QHBoxLayout()

        add_group = QGroupBox("Add Shako")
        add_form = QFormLayout(add_group)

        self.shako_size = QLineEdit()
        add_form.addRow("Size:", self.shako_size)

        self.shako_condition = QLineEdit()
        add_form.addRow("Condition:", self.shako_condition)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_shako)
        add_form.addRow(add_btn)

        assign_group = QGroupBox("Assign / Unassign")
        assign_form = QFormLayout(assign_group)

        self.assign_shako_student = QLineEdit()
        self.assign_shako_student.setPlaceholderText("Student ID")
        self.assign_shako_student.textChanged.connect(lambda: self.show_student_preview(self.assign_shako_student, self.shako_preview))
        assign_form.addRow("Student ID*:", self.assign_shako_student)

        self.shako_preview = QLabel("")
        assign_form.addRow("Student:", self.shako_preview)

        assign_btn = QPushButton("Assign")
        assign_btn.clicked.connect(self.assign_shako)
        assign_form.addRow(assign_btn)

        unassign_btn = QPushButton("Unassign")
        unassign_btn.clicked.connect(self.unassign_shako)
        assign_form.addRow(unassign_btn)

        forms_row.addWidget(add_group)
        forms_row.addWidget(assign_group)
        layout.addLayout(forms_row)

        self.apply_shadow(add_group)
        self.apply_shadow(assign_group)

    def load_shakos(self):
        q = self.shako_search.text().strip()
        where = ""
        params = []
        if q:
            where = "WHERE COALESCE(SIZE,'') LIKE ? OR COALESCE(CONDITION_NOTES,'') LIKE ? OR COALESCE(CHECKED_OUT_TO,'') LIKE ?"
            params = [f"%{q}%"] * 3

        cur = self.conn.execute(f"""
            SELECT SHAKO_ID, COALESCE(SIZE,''), COALESCE(CONDITION_NOTES,''),
                   COALESCE(CHECKED_OUT_TO,''), COALESCE(CHECKED_OUT_DATE,''),
                   CASE WHEN CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
            FROM SHAKOS
            {where}
            ORDER BY (CHECKED_OUT_TO IS NULL) DESC, SHAKO_ID
        """, params)

        self.shakos_table.setRowCount(0)
        for r in cur.fetchall():
            row = self.shakos_table.rowCount()
            self.shakos_table.insertRow(row)
            for c in range(6):
                self.shakos_table.setItem(row, c, make_table_item(r[c]))

        self.shakos_table.resizeColumnsToContents()
        self.update_status(f"Loaded {self.shakos_table.rowCount()} shakos")

    def add_shako(self):
        size = self.shako_size.text().strip() or None
        cond = self.shako_condition.text().strip() or None
        try:
            self.conn.execute("INSERT INTO SHAKOS (SIZE, CONDITION_NOTES) VALUES (?, ?)", (size, cond))
            sid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self.conn.commit()
            self.push_undo_ops("Add Shako", [("DELETE FROM SHAKOS WHERE SHAKO_ID=?", (sid,))])

            self.shako_size.clear()
            self.shako_condition.clear()

            self.refresh_all()
            self.update_status("Shako added")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def get_selected_shako_id(self):
        row = self.shakos_table.currentRow()
        if row < 0:
            return None
        return int(self.shakos_table.item(row, 0).text())

    def assign_shako(self):
        shako_id = self.get_selected_shako_id()
        if not shako_id:
            self.show_error("Select a shako first")
            return

        if not self.validate_required(self.assign_shako_student):
            self.show_error("Student ID is required")
            return

        sid_txt = self.assign_shako_student.text().strip()
        if not sid_txt.isdigit():
            self.show_error("Student ID must be numeric")
            return
        sid = int(sid_txt)

        if not check_student_exists(self.conn, sid):
            self.show_error("Student not found")
            return

        cur = self.conn.execute("SELECT CHECKED_OUT_TO, CHECKED_OUT_DATE, COALESCE(CONDITION_NOTES,'') FROM SHAKOS WHERE SHAKO_ID=?", (shako_id,))
        old_to, old_date, old_cond = cur.fetchone()

        if old_to:
            self.show_error("That shako is already assigned")
            return

        cond, ok = QInputDialog.getText(self, "Condition", "Condition notes (optional):")
        if not ok:
            return

        try:
            self.conn.execute("""
                UPDATE SHAKOS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=?
                WHERE SHAKO_ID=? AND CHECKED_OUT_TO IS NULL
            """, (sid, date.today().isoformat(), cond.strip() or old_cond or None, shako_id))
            self.conn.commit()

            undo_ops = [("UPDATE SHAKOS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE SHAKO_ID=?",
                         (old_to, old_date, old_cond or None, shako_id))]
            self.push_undo_ops("Assign Shako", undo_ops)

            self.assign_shako_student.clear()
            self.shako_preview.setText("")
            self.refresh_all()
            self.update_status("Shako assigned")
        except sqlite3.IntegrityError:
            self.show_error("Student can only hold one shako")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def unassign_shako(self):
        shako_id = self.get_selected_shako_id()
        if not shako_id:
            self.show_error("Select a shako first")
            return

        cur = self.conn.execute("SELECT CHECKED_OUT_TO, CHECKED_OUT_DATE, COALESCE(CONDITION_NOTES,'') FROM SHAKOS WHERE SHAKO_ID=?", (shako_id,))
        old_to, old_date, old_cond = cur.fetchone()

        if not old_to:
            self.show_error("That shako is not assigned")
            return

        cond, ok = QInputDialog.getText(self, "Condition Update", "Condition notes after return (optional):")
        if not ok:
            return

        new_cond = cond.strip() or old_cond or None

        try:
            self.conn.execute("""
                UPDATE SHAKOS SET CHECKED_OUT_TO=NULL, CHECKED_OUT_DATE=NULL, CONDITION_NOTES=?
                WHERE SHAKO_ID=?
            """, (new_cond, shako_id))
            self.conn.commit()

            undo_ops = [("UPDATE SHAKOS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE SHAKO_ID=?",
                         (old_to, old_date, old_cond or None, shako_id))]
            self.push_undo_ops("Unassign Shako", undo_ops)

            self.refresh_all()
            self.update_status("Shako unassigned")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    # INSTRUMENT MENU
    def create_instruments_tab(self):
        tab = QWidget()
        self.tabs.addTab(tab, "Instruments")
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        self.instrument_search = QLineEdit()
        self.instrument_search.setPlaceholderText("Search instruments… (type, serial, condition, assigned ID)")
        self.instrument_search.textChanged.connect(self.load_instruments)
        top.addWidget(self.instrument_search)

        self.section_filter = QComboBox()
        self.section_filter.addItems(["All Sections", "WOODWIND", "BRASS", "PERCUSSION"])
        self.section_filter.currentIndexChanged.connect(self.load_instruments)
        top.addWidget(self.section_filter)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_instruments)
        top.addWidget(refresh_btn)

        layout.addLayout(top)

        self.instruments_table = QTableWidget(0, 8)
        self.instruments_table.setHorizontalHeaderLabels([
            "ID", "Type", "Section", "Serial", "Condition", "Assigned To", "Date", "Available"
        ])
        self.instruments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.instruments_table.setAlternatingRowColors(True)
        self.instruments_table.verticalHeader().setVisible(False)
        self.instruments_table.horizontalHeader().setStretchLastSection(True)
        self.instruments_table.setWordWrap(False)
        self.instruments_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.instruments_table.setShowGrid(True)
        layout.addWidget(self.instruments_table)

        forms_row = QHBoxLayout()

        add_group = QGroupBox("Add Instrument")
        add_form = QFormLayout(add_group)

        self.instrument_type_combo = QComboBox()
        self.load_instrument_types()
        add_form.addRow("Type*:", self.instrument_type_combo)

        self.instrument_serial = QLineEdit()
        add_form.addRow("Serial #:", self.instrument_serial)

        self.instrument_notes = QLineEdit()
        add_form.addRow("Condition:", self.instrument_notes)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_instrument)
        add_form.addRow(add_btn)

        assign_group = QGroupBox("Assign / Unassign")
        assign_form = QFormLayout(assign_group)

        self.assign_instr_student = QLineEdit()
        self.assign_instr_student.setPlaceholderText("Student ID")
        self.assign_instr_student.textChanged.connect(lambda: self.show_student_preview(self.assign_instr_student, self.instr_preview))
        assign_form.addRow("Student ID*:", self.assign_instr_student)

        self.instr_preview = QLabel("")
        assign_form.addRow("Student:", self.instr_preview)

        assign_btn = QPushButton("Assign")
        assign_btn.clicked.connect(self.assign_instrument)
        assign_form.addRow(assign_btn)

        unassign_btn = QPushButton("Unassign")
        unassign_btn.clicked.connect(self.unassign_instrument)
        assign_form.addRow(unassign_btn)

        forms_row.addWidget(add_group)
        forms_row.addWidget(assign_group)
        layout.addLayout(forms_row)

        self.apply_shadow(add_group)
        self.apply_shadow(assign_group)

    def load_instrument_types(self):
        self.instrument_type_combo.clear()
        cur = self.conn.execute("SELECT TYPE_ID, TYPE_NAME, SECTION FROM INSTRUMENT_TYPES ORDER BY SECTION, TYPE_NAME")
        for tid, name, sec in cur.fetchall():
            self.instrument_type_combo.addItem(f"{name} ({sec})", tid)

    def load_instruments(self):
        q = self.instrument_search.text().strip()
        sec = self.section_filter.currentText()

        where = []
        params = []

        if sec != "All Sections":
            where.append("t.SECTION=?")
            params.append(sec)

        if q:
            where.append("(t.TYPE_NAME LIKE ? OR COALESCE(i.SERIAL,'') LIKE ? OR COALESCE(i.CONDITION_NOTES,'') LIKE ? OR COALESCE(i.CHECKED_OUT_TO,'') LIKE ?)")
            params.extend([f"%{q}%"] * 4)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cur = self.conn.execute(f"""
            SELECT i.INSTRUMENT_ID, t.TYPE_NAME, t.SECTION,
                   COALESCE(i.SERIAL,''), COALESCE(i.CONDITION_NOTES,''),
                   COALESCE(i.CHECKED_OUT_TO,''), COALESCE(i.CHECKED_OUT_DATE,''),
                   CASE WHEN i.CHECKED_OUT_TO IS NULL THEN 'Yes' ELSE 'No' END
            FROM INSTRUMENTS i
            JOIN INSTRUMENT_TYPES t ON i.TYPE_ID=t.TYPE_ID
            {where_sql}
            ORDER BY t.SECTION, t.TYPE_NAME, i.INSTRUMENT_ID
        """, params)

        self.instruments_table.setRowCount(0)
        for r in cur.fetchall():
            row = self.instruments_table.rowCount()
            self.instruments_table.insertRow(row)
            for c in range(8):
                self.instruments_table.setItem(row, c, make_table_item(r[c]))

        self.instruments_table.resizeColumnsToContents()
        self.update_status(f"Loaded {self.instruments_table.rowCount()} instruments")

    def add_instrument(self):
        tid = self.instrument_type_combo.currentData()
        if not tid:
            self.show_error("Select a type")
            return

        serial = self.instrument_serial.text().strip() or None
        cond = self.instrument_notes.text().strip() or None

        try:
            self.conn.execute("INSERT INTO INSTRUMENTS (TYPE_ID, SERIAL, CONDITION_NOTES) VALUES (?, ?, ?)", (tid, serial, cond))
            iid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self.conn.commit()
            self.push_undo_ops("Add Instrument", [("DELETE FROM INSTRUMENTS WHERE INSTRUMENT_ID=?", (iid,))])

            self.instrument_serial.clear()
            self.instrument_notes.clear()

            self.refresh_all()
            self.update_status("Instrument added")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def get_selected_instrument_id(self):
        row = self.instruments_table.currentRow()
        if row < 0:
            return None
        return int(self.instruments_table.item(row, 0).text())

    def assign_instrument(self):
        iid = self.get_selected_instrument_id()
        if not iid:
            self.show_error("Select an instrument first")
            return

        if not self.validate_required(self.assign_instr_student):
            self.show_error("Student ID is required")
            return

        sid_txt = self.assign_instr_student.text().strip()
        if not sid_txt.isdigit():
            self.show_error("Student ID must be numeric")
            return
        sid = int(sid_txt)

        if not check_student_exists(self.conn, sid):
            self.show_error("Student not found")
            return

        instr_section = get_instrument_section_by_id(self.conn, iid)
        student_section = get_student_section(self.conn, sid)
        if instr_section and student_section and instr_section != student_section:
            if not self.ask_yes_no("Section mismatch", f"Instrument section is {instr_section} but student section is {student_section}. Assign anyway?"):
                return

        cur = self.conn.execute("SELECT CHECKED_OUT_TO, CHECKED_OUT_DATE, COALESCE(CONDITION_NOTES,'') FROM INSTRUMENTS WHERE INSTRUMENT_ID=?", (iid,))
        old_to, old_date, old_cond = cur.fetchone()

        if old_to:
            self.show_error("That instrument is already assigned")
            return

        cond, ok = QInputDialog.getText(self, "Condition", "Condition notes (optional):")
        if not ok:
            return

        try:
            self.conn.execute("""
                UPDATE INSTRUMENTS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=?
                WHERE INSTRUMENT_ID=? AND CHECKED_OUT_TO IS NULL
            """, (sid, date.today().isoformat(), cond.strip() or old_cond or None, iid))
            self.conn.commit()

            undo_ops = [("UPDATE INSTRUMENTS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE INSTRUMENT_ID=?",
                         (old_to, old_date, old_cond or None, iid))]
            self.push_undo_ops("Assign Instrument", undo_ops)

            self.assign_instr_student.clear()
            self.instr_preview.setText("")
            self.refresh_all()
            self.update_status("Instrument assigned")
        except sqlite3.IntegrityError:
            self.show_error("Student can only hold one instrument")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def unassign_instrument(self):
        iid = self.get_selected_instrument_id()
        if not iid:
            self.show_error("Select an instrument first")
            return

        cur = self.conn.execute("SELECT CHECKED_OUT_TO, CHECKED_OUT_DATE, COALESCE(CONDITION_NOTES,'') FROM INSTRUMENTS WHERE INSTRUMENT_ID=?", (iid,))
        old_to, old_date, old_cond = cur.fetchone()

        if not old_to:
            self.show_error("That instrument is not assigned")
            return

        cond, ok = QInputDialog.getText(self, "Condition Update", "Condition notes after return (optional):")
        if not ok:
            return

        new_cond = cond.strip() or old_cond or None

        try:
            self.conn.execute("""
                UPDATE INSTRUMENTS SET CHECKED_OUT_TO=NULL, CHECKED_OUT_DATE=NULL, CONDITION_NOTES=?
                WHERE INSTRUMENT_ID=?
            """, (new_cond, iid))
            self.conn.commit()

            undo_ops = [("UPDATE INSTRUMENTS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=?, CONDITION_NOTES=? WHERE INSTRUMENT_ID=?",
                         (old_to, old_date, old_cond or None, iid))]
            self.push_undo_ops("Unassign Instrument", undo_ops)

            self.refresh_all()
            self.update_status("Instrument unassigned")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def refresh_all(self):
        self.load_students()
        self.load_uniforms()
        self.load_shakos()
        self.load_instruments()

def seed_sample_data(conn):
        """
        Inserts sample data ONLY if the database is empty.
        """
        cur = conn.execute("SELECT COUNT(*) FROM STUDENTS")
        if cur.fetchone()[0] > 0:
            return  

        # Students 
        students = [
            (300819037, "Jordan", "Reed", "Freshman", "WOODWIND", "CLARINET", "M", "9",   1),
            (300612467, "Ava",    "Lopez","Sophomore","BRASS",   "TRUMPET",  "S", "7.5", 1),
            (300395193, "Miles",  "King", "Junior",   "PERCUSSION","SNARE DRUM","L","11",1),
            (300518905, "Nia",    "Carter","Senior",  "FLAG CORP","OTHER",   "M", "8",   1),
            (300135890, "Ethan",  "Park", "Junior",   "BRASS",   "TROMBONE", "XL","12",  1),
            (300131935, "Zoe",    "Smith","Freshman", "WOODWIND","FLUTE",    "XS","6.5", 0),  
        ]

        today = date.today().isoformat()

        conn.execute("BEGIN")

        # Insert students
        for sid, fn, ln, cl, sec, role, shirt, shoe, active in students:
            conn.execute(
                """INSERT INTO STUDENTS
                (STUDENT_ID, FNAME, LNAME, CLASSIFICATION, SECTION, PRIMARY_ROLE, SHIRT_SIZE, SHOE_SIZE, ACTIVE, UPDATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, fn, ln, cl, sec, role, shirt, shoe, active, today)
            )

        # Compliance
        compliance = [
            (300819037, 14, 3.20, 1, today),  # eligible
            (300612467, 12, 2.85, 1, today),  # not eligible (gpa)
            (300395193, 10, 3.50, 1, today),  # not eligible (credits)
            (300518905, 15, 3.10, 0, today),  # not eligible (dues)
            (300135890, 16, 3.70, 1, today),  # eligible
            (300131935, 0,  0.00, 0, today),
        ]
        for row in compliance:
            conn.execute(
                """INSERT INTO COMPLIANCE (STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE)
                VALUES (?, ?, ?, ?, ?)""",
                row
            )

        # Instruments
        type_id = {name: tid for tid, name in conn.execute("SELECT TYPE_ID, TYPE_NAME FROM INSTRUMENT_TYPES")}
        instruments = [
            (type_id["CLARINET"], "CL-44321", "Good pads"),
            (type_id["TRUMPET"], "TR-88210", "Valve 2 sticky"),
            (type_id["SNARE DRUM"], "SD-11007", "New head"),
            (type_id["TROMBONE"], "TB-23001", "Slide a bit tight"),
        ]
        for tid, serial, notes in instruments:
            conn.execute(
                "INSERT INTO INSTRUMENTS (TYPE_ID, SERIAL, CONDITION_NOTES) VALUES (?, ?, ?)",
                (tid, serial, notes)
            )

        
        instr_ids = [r[0] for r in conn.execute("SELECT INSTRUMENT_ID FROM INSTRUMENTS ORDER BY INSTRUMENT_ID").fetchall()]
    
        conn.execute("UPDATE INSTRUMENTS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=? WHERE INSTRUMENT_ID=?",
                    (300819037, today, instr_ids[0]))
        conn.execute("UPDATE INSTRUMENTS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=? WHERE INSTRUMENT_ID=?",
                    (300612467, today, instr_ids[1]))

        # Uniforms
        uniforms = [
            ("40R", "32", "C-101", "P-101", "Clean"),
            ("38R", "30", "C-102", "P-102", "Minor tear"),
            ("42L", "34", "C-103", "P-103", "Needs dry clean"),
        ]
        for coat, pant, coatn, pantn, notes in uniforms:
            conn.execute(
                "INSERT INTO UNIFORMS (COAT_SIZE, PANT_SIZE, COAT_NUMBER, PANT_NUMBER, CONDITION_NOTES) VALUES (?, ?, ?, ?, ?)",
                (coat, pant, coatn, pantn, notes)
            )

        uni_id = conn.execute("SELECT UNIFORM_ID FROM UNIFORMS ORDER BY UNIFORM_ID LIMIT 1").fetchone()[0]
        conn.execute("UPDATE UNIFORMS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=? WHERE UNIFORM_ID=?",
                    (300395193, today, uni_id))

        # Shakos
        shakos = [
            ("7 1/4", "Good"),
            ("7 3/8", "Needs plume"),
            ("7 1/2", "Scuffed brim"),
        ]
        for size, notes in shakos:
            conn.execute("INSERT INTO SHAKOS (SIZE, CONDITION_NOTES) VALUES (?, ?)", (size, notes))

        shako_id = conn.execute("SELECT SHAKO_ID FROM SHAKOS ORDER BY SHAKO_ID LIMIT 1").fetchone()[0]
        conn.execute("UPDATE SHAKOS SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=? WHERE SHAKO_ID=?",
                    (300518905, today, shako_id))

        conn.commit()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = BandDatabaseApp()
    window.resize(1280, 780)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
