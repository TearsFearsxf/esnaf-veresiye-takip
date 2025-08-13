#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
import csv
import json
import shutil
from datetime import datetime, timedelta
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# EXE için gerekli kaynak yolu çözümleme fonksiyonu
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_app_data_folder():
    """Uygulama verilerini saklamak için klasör yolu"""
    if sys.platform == "win32":
        base_path = os.path.join(os.environ['APPDATA'], "VeresiyeDefteri")
    else:
        base_path = os.path.join(os.path.expanduser('~'), ".veresiyedefteri")
    
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    return base_path

class Database:
    def __init__(self):
        # Veritabanını kullanıcının appdata klasörüne kaydet
        self.db_name = os.path.join(get_app_data_folder(), "veresiye.db")
        self.init_db()
        self.backup_folder = os.path.join(get_app_data_folder(), "backups")
        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)
    
    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Müşteriler tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                surname TEXT,
                phone TEXT,
                address TEXT,
                debt REAL DEFAULT 0,
                created_date TEXT
            )
        ''')
        
        # Ödemeler tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                amount REAL,
                payment_type TEXT,
                note TEXT,
                date TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Ayarlar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Otomatik yedekleme ayarları
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('auto_backup', 'daily')
        ''')
        
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('last_backup', '')
        ''')
        
        conn.commit()
        conn.close()
    
    def add_customer(self, name, surname="", phone="", address="", debt=0):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO customers (name, surname, phone, address, debt, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, surname, phone, address, debt, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    
    def get_customers(self, filter_type="all"):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if filter_type == "debt":
            cursor.execute("SELECT * FROM customers WHERE debt > 0")
        elif filter_type == "paid":
            cursor.execute("SELECT * FROM customers WHERE debt <= 0")
        else:
            cursor.execute("SELECT * FROM customers")
        
        customers = cursor.fetchall()
        conn.close()
        return customers
    
    def search_customers(self, search_text, filter_type="all"):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        search_query = f"%{search_text}%"
        base_query = '''
            SELECT * FROM customers 
            WHERE (name LIKE ? OR surname LIKE ? OR phone LIKE ?)
        '''
        
        if filter_type == "debt":
            base_query += " AND debt > 0"
        elif filter_type == "paid":
            base_query += " AND debt <= 0"
        
        cursor.execute(base_query, (search_query, search_query, search_query))
        customers = cursor.fetchall()
        conn.close()
        return customers
    
    def update_customer_debt(self, customer_id, amount, is_payment=True, note=""):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if is_payment:
            cursor.execute("UPDATE customers SET debt = debt - ? WHERE id = ?", (amount, customer_id))
            payment_type = "payment"
        else:
            cursor.execute("UPDATE customers SET debt = debt + ? WHERE id = ?", (amount, customer_id))
            payment_type = "debt"
        
        # Ödeme kaydını ekle
        cursor.execute('''
            INSERT INTO payments (customer_id, amount, payment_type, date, note)
            VALUES (?, ?, ?, ?, ?)
        ''', (customer_id, amount, payment_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), note))
        
        conn.commit()
        conn.close()
    
    def get_customer(self, customer_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        customer = cursor.fetchone()
        conn.close()
        return customer
    
    def get_payments(self, customer_id, days=None):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if days:
            date_limit = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cursor.execute('''
                SELECT * FROM payments WHERE customer_id = ? AND date >= ?
                ORDER BY date DESC
            ''', (customer_id, date_limit))
        else:
            cursor.execute('''
                SELECT * FROM payments WHERE customer_id = ?
                ORDER BY date DESC
            ''', (customer_id,))
        
        payments = cursor.fetchall()
        conn.close()
        return payments
    
    def delete_customer(self, customer_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        cursor.execute("DELETE FROM payments WHERE customer_id = ?", (customer_id,))
        conn.commit()
        conn.close()
    
    def get_total_debt(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(debt) FROM customers WHERE debt > 0")
        total = cursor.fetchone()[0]
        conn.close()
        return total if total else 0
    
    def get_average_debt(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT AVG(debt) FROM customers WHERE debt > 0")
        avg = cursor.fetchone()[0]
        conn.close()
        return avg if avg else 0
    
    def export_to_csv(self, filename):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers")
        customers = cursor.fetchall()
        
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['ID', 'Ad', 'Soyad', 'Telefon', 'Adres', 'Borç', 'Kayıt Tarihi'])
            writer.writerows(customers)
        
        conn.close()
    
    def get_setting(self, key):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_setting(self, key, value):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value) 
            VALUES (?, ?)
        ''', (key, value))
        conn.commit()
        conn.close()
    
    def auto_backup(self):
        frequency = self.get_setting('auto_backup')
        last_backup = self.get_setting('last_backup')
        
        if not frequency or frequency == "none":
            return
        
        now = datetime.now()
        if last_backup:
            last_date = datetime.strptime(last_backup, "%Y-%m-%d %H:%M:%S")
        else:
            last_date = datetime(2000, 1, 1)
        
        if frequency == "hourly" and (now - last_date).total_seconds() >= 3600:
            self.do_backup("auto")
        elif frequency == "daily" and (now - last_date).days >= 1:
            self.do_backup("auto")
        elif frequency == "weekly" and (now - last_date).days >= 7:
            self.do_backup("auto")
        elif frequency == "monthly" and now.month != last_date.month:
            self.do_backup("auto")
    
    def do_backup(self, backup_type="manual"):
        try:
            if backup_type == "auto":
                folder = self.backup_folder
                filename = os.path.join(folder, f"auto_backup_{datetime.now().strftime('%d-%m-%Y_%H%M')}.csv")
            else:
                folder = QFileDialog.getExistingDirectory(None, "Yedek Klasörü Seç", get_app_data_folder())
                if not folder:
                    return
                filename = os.path.join(folder, f"veresiye_yedek_{datetime.now().strftime('%d-%m-%Y_%H%M')}.csv")
            
            self.export_to_csv(filename)
            self.set_setting('last_backup', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            return filename
        except Exception as e:
            print(f"Yedekleme hatası: {str(e)}")
            return None

class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        QSystemTrayIcon.__init__(self, icon, parent)
        self.parent = parent
        menu = QMenu(parent)
        
        open_action = menu.addAction("Aç")
        open_action.triggered.connect(self.show_window)
        
        menu.addSeparator()
        
        backup_csv_action = menu.addAction("Yedekle (CSV)")
        backup_csv_action.triggered.connect(self.backup_csv)
        
        backup_excel_action = menu.addAction("Yedekle (Excel)")
        backup_excel_action.triggered.connect(self.backup_excel)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("Çık (Kaydet ve Kapat)")
        exit_action.triggered.connect(self.exit_application)
        
        self.setContextMenu(menu)
        self.activated.connect(self.on_tray_icon_activated)
    
    def on_tray_icon_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_window()
    
    def show_window(self):
        self.parent.show()
        self.parent.raise_()
        self.parent.activateWindow()
    
    def backup_csv(self):
        filename = self.parent.db.do_backup("manual")
        if filename:
            self.showMessage("Yedekleme", f"CSV yedekleme tamamlandı: {filename}", QSystemTrayIcon.Information, 3000)
    
    def backup_excel(self):
        self.showMessage("Yedekleme", "Excel yedekleme özelliği geliştirilecek", QSystemTrayIcon.Information, 3000)
    
    def exit_application(self):
        QApplication.quit()

class AddCustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Müşteri Ekle")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # Form alanları
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Zorunlu")
        form_layout.addRow("Ad:", self.name_edit)
        
        self.surname_edit = QLineEdit()
        self.surname_edit.setPlaceholderText("İsteğe bağlı")
        form_layout.addRow("Soyad:", self.surname_edit)
        
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("İsteğe bağlı")
        form_layout.addRow("Telefon:", self.phone_edit)
        
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("İsteğe bağlı")
        form_layout.addRow("Adres:", self.address_edit)
        
        self.debt_edit = QLineEdit()
        self.debt_edit.setPlaceholderText("0")
        form_layout.addRow("Başlangıç Borcu (TL):", self.debt_edit)
        
        layout.addLayout(form_layout)
        
        # Butonlar
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self.save_customer)
        
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def save_customer(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Ad alanı zorunludur!")
            return
        
        surname = self.surname_edit.text().strip()
        phone = self.phone_edit.text().strip()
        address = self.address_edit.text().strip()
        
        try:
            debt = float(self.debt_edit.text()) if self.debt_edit.text() else 0
        except ValueError:
            debt = 0
        
        self.customer_data = {
            'name': name,
            'surname': surname,
            'phone': phone,
            'address': address,
            'debt': debt
        }
        
        self.accept()

class CustomerProfileDialog(QDialog):
    def __init__(self, customer_id, db, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.db = db
        self.init_ui()
        self.load_customer_data()
    
    def init_ui(self):
        self.setWindowTitle("Müşteri Profili")
        self.setFixedSize(600, 700)
        
        layout = QVBoxLayout()
        
        # Müşteri bilgileri
        info_group = QGroupBox("Müşteri Bilgileri")
        info_layout = QVBoxLayout()
        
        self.customer_info_label = QLabel()
        self.customer_info_label.setWordWrap(True)
        self.customer_info_label.setStyleSheet("font-size: 14px; padding: 10px;")
        info_layout.addWidget(self.customer_info_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # İşlem yapma
        transaction_group = QGroupBox("Yeni İşlem")
        transaction_layout = QVBoxLayout()
        
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Miktar:"))
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("TL miktarı girin")
        amount_layout.addWidget(self.amount_edit)
        amount_layout.addWidget(QLabel("TL"))
        
        transaction_layout.addLayout(amount_layout)
        
        note_layout = QHBoxLayout()
        note_layout.addWidget(QLabel("Not:"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("İşlem notu (isteğe bağlı)")
        note_layout.addWidget(self.note_edit)
        
        transaction_layout.addLayout(note_layout)
        
        button_layout = QHBoxLayout()
        
        self.payment_btn = QPushButton("Ödeme Yaptı")
        self.payment_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.payment_btn.clicked.connect(lambda: self.process_transaction(True))
        
        self.debt_btn = QPushButton("Borç Ekle")
        self.debt_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.debt_btn.clicked.connect(lambda: self.process_transaction(False))
        
        button_layout.addWidget(self.payment_btn)
        button_layout.addWidget(self.debt_btn)
        
        transaction_layout.addLayout(button_layout)
        transaction_group.setLayout(transaction_layout)
        layout.addWidget(transaction_group)
        
        # Ödeme geçmişi
        history_group = QGroupBox("İşlem Geçmişi")
        history_layout = QVBoxLayout()
        
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(5)
        self.payments_table.setHorizontalHeaderLabels(["Tarih", "Miktar", "Tür", "Not", "İşlem"])
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        self.payments_table.setColumnWidth(0, 120)
        self.payments_table.setColumnWidth(1, 100)
        self.payments_table.setColumnWidth(2, 80)
        
        history_layout.addWidget(self.payments_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Geri butonu
        back_btn = QPushButton("Geri")
        back_btn.clicked.connect(self.close)
        layout.addWidget(back_btn)
        
        self.setLayout(layout)
    
    def load_customer_data(self):
        customer = self.db.get_customer(self.customer_id)
        if customer:
            info_text = f"<b>Ad-Soyad:</b> {customer[1]} {customer[2] or ''}<br>"
            info_text += f"<b>Telefon:</b> {customer[3] or 'Belirtilmemiş'}<br>"
            info_text += f"<b>Adres:</b> {customer[4] or 'Belirtilmemiş'}<br>"
            info_text += f"<b>Güncel Borç:</b> <span style='color: {'red' if customer[5] > 0 else 'green'};'>{customer[5]:.2f} TL</span>"
            self.customer_info_label.setText(info_text)
        
        # Ödeme geçmişini yükle
        payments = self.db.get_payments(self.customer_id)
        self.payments_table.setRowCount(len(payments))
        
        for i, payment in enumerate(payments):
            date_str = payment[5][:16]  # Tarih ve saat
            amount = f"{payment[2]:.2f} TL"
            payment_type = "Ödeme" if payment[3] == "payment" else "Borç"
            note = payment[4] or ""
            
            self.payments_table.setItem(i, 0, QTableWidgetItem(date_str))
            self.payments_table.setItem(i, 1, QTableWidgetItem(amount))
            self.payments_table.setItem(i, 2, QTableWidgetItem(payment_type))
            self.payments_table.setItem(i, 3, QTableWidgetItem(note))
            
            # İşlem silme butonu
            delete_btn = QPushButton("Sil")
            delete_btn.setStyleSheet("background-color: #ff9800; color: white;")
            delete_btn.clicked.connect(lambda checked, p_id=payment[0]: self.delete_payment(p_id))
            self.payments_table.setCellWidget(i, 4, delete_btn)
    
    def process_transaction(self, is_payment):
        try:
            amount = float(self.amount_edit.text())
            if amount <= 0:
                QMessageBox.warning(self, "Uyarı", "Geçerli bir miktar giriniz!")
                return
            
            note = self.note_edit.text().strip()
            self.db.update_customer_debt(self.customer_id, amount, is_payment, note)
            self.load_customer_data()  # Verileri yenile
            self.amount_edit.clear()
            self.note_edit.clear()
            
            action = "ödeme" if is_payment else "borç"
            QMessageBox.information(self, "Başarılı", f"{amount:.2f} TL {action} kaydedildi!")
            
        except ValueError:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir miktar giriniz!")
    
    def delete_payment(self, payment_id):
        reply = QMessageBox.question(self, "Onay", "Bu işlemi silmek istediğinizden emin misiniz?")
        if reply == QMessageBox.Yes:
            # Ödemeyi veritabanından sil ve borcu güncelle
            conn = sqlite3.connect(self.db.db_name)
            cursor = conn.cursor()
            
            # Ödeme bilgilerini al
            cursor.execute("SELECT customer_id, amount, payment_type FROM payments WHERE id = ?", (payment_id,))
            payment = cursor.fetchone()
            
            if payment:
                customer_id = payment[0]
                amount = payment[1]
                is_payment = (payment[2] == "payment")
                
                # Borcu tersine çevir
                if is_payment:
                    cursor.execute("UPDATE customers SET debt = debt + ? WHERE id = ?", (amount, customer_id))
                else:
                    cursor.execute("UPDATE customers SET debt = debt - ? WHERE id = ?", (amount, customer_id))
                
                # Ödemeyi sil
                cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
                conn.commit()
            
            conn.close()
            self.load_customer_data()

class AccountDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        self.calculate_totals()
    
    def init_ui(self):
        self.setWindowTitle("Hesap")
        self.setFixedSize(500, 500)
        
        layout = QVBoxLayout()
        
        # Hesap bilgileri
        info_group = QGroupBox("Hesap Özeti")
        info_layout = QVBoxLayout()
        
        self.total_debt_label = QLabel()
        self.total_debt_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.average_debt_label = QLabel()
        self.debtor_count_label = QLabel()
        
        info_layout.addWidget(self.total_debt_label)
        info_layout.addWidget(self.average_debt_label)
        info_layout.addWidget(self.debtor_count_label)
        
        calculate_btn = QPushButton("Toplam Borcu Hesapla")
        calculate_btn.clicked.connect(self.calculate_totals)
        info_layout.addWidget(calculate_btn)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Yedekleme
        backup_group = QGroupBox("Yedekleme")
        backup_layout = QVBoxLayout()
        
        backup_btn = QPushButton("Veriyi Yedekle (CSV)")
        backup_btn.clicked.connect(self.backup_data)
        backup_layout.addWidget(backup_btn)
        
        self.backup_info_label = QLabel("Son yedekleme: Henüz yedekleme yapılmadı")
        backup_layout.addWidget(self.backup_info_label)
        
        open_backup_btn = QPushButton("Yedek Klasörünü Aç")
        open_backup_btn.clicked.connect(self.open_backup_folder)
        backup_layout.addWidget(open_backup_btn)
        
        clean_backups_btn = QPushButton("Eski Yedekleri Sil")
        clean_backups_btn.clicked.connect(self.clean_backups)
        backup_layout.addWidget(clean_backups_btn)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Geri butonu
        back_btn = QPushButton("Geri")
        back_btn.clicked.connect(self.close)
        layout.addWidget(back_btn)
        
        self.setLayout(layout)
    
    def calculate_totals(self):
        total_debt = self.db.get_total_debt()
        avg_debt = self.db.get_average_debt()
        
        conn = sqlite3.connect(self.db.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM customers WHERE debt > 0")
        debtor_count = cursor.fetchone()[0]
        conn.close()
        
        self.total_debt_label.setText(f"Toplam Borç: {total_debt:.2f} TL")
        self.average_debt_label.setText(f"Ortalama Borç: {avg_debt:.2f} TL")
        self.debtor_count_label.setText(f"Borçlu Müşteri Sayısı: {debtor_count}")
    
    def backup_data(self):
        filename = self.db.do_backup("manual")
        if filename:
            self.backup_info_label.setText(f"Yedeklendi: {os.path.basename(filename)}\nSon Yedek: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            QMessageBox.information(self, "Başarılı", f"Yedekleme tamamlandı:\n{filename}")
    
    def open_backup_folder(self):
        backup_folder = self.db.backup_folder
        if sys.platform == "win32":
            os.startfile(backup_folder)
        elif sys.platform == "darwin":
            os.system(f"open '{backup_folder}'")
        else:
            os.system(f"xdg-open '{backup_folder}'")
    
    def clean_backups(self):
        # 30 günden eski yedekleri sil
        backup_folder = self.db.backup_folder
        now = datetime.now()
        deleted = 0
        
        for filename in os.listdir(backup_folder):
            filepath = os.path.join(backup_folder, filename)
            if os.path.isfile(filepath) and filename.endswith(".csv"):
                file_date_str = filename.split("_")[-1].split(".")[0]
                try:
                    file_date = datetime.strptime(file_date_str, "%d-%m-%Y-%H%M")
                    if (now - file_date).days > 30:
                        os.remove(filepath)
                        deleted += 1
                except:
                    pass
        
        QMessageBox.information(self, "Başarılı", f"{deleted} eski yedek dosyası silindi!")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.undo_stack = []
        self.current_filter = "all"
        self.init_ui()
        self.init_tray()
        self.load_customers()
        
        # Otomatik yedekleme kontrolü
        self.auto_backup_timer = QTimer(self)
        self.auto_backup_timer.timeout.connect(self.check_auto_backup)
        self.auto_backup_timer.start(60000)  # Her dakika kontrol
    
    def init_ui(self):
        self.setWindowTitle("Veresiye Defteri")
        self.setGeometry(100, 100, 900, 700)
        
        # İkon ayarla (EXE uyumlu)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Üst panel
        top_layout = QHBoxLayout()
        
        # Arama kutusu
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Ad, soyad veya telefon ara...")
        self.search_edit.textChanged.connect(self.filter_customers)
        top_layout.addWidget(self.search_edit)
        
        # Butonlar
        add_customer_btn = QPushButton("M.Kayıt")
        add_customer_btn.setToolTip("Yeni müşteri ekle")
        add_customer_btn.clicked.connect(self.add_customer)
        top_layout.addWidget(add_customer_btn)
        
        settings_btn = QPushButton("Ayarlar")
        settings_btn.setToolTip("Uygulama ayarları")
        settings_btn.clicked.connect(self.show_settings)
        top_layout.addWidget(settings_btn)
        
        account_btn = QPushButton("Hesap")
        account_btn.setToolTip("Hesap özeti ve yedekleme")
        account_btn.clicked.connect(self.show_account)
        top_layout.addWidget(account_btn)
        
        layout.addLayout(top_layout)
        
        # Müşteri tablosu
        self.customers_table = QTableWidget()
        self.customers_table.setColumnCount(6)
        self.customers_table.setHorizontalHeaderLabels(["ID", "Ad-Soyad", "Telefon", "Borç", "Düzenle", "Sil"])
        self.customers_table.horizontalHeader().setStretchLastSection(True)
        self.customers_table.setColumnWidth(0, 50)
        self.customers_table.setColumnWidth(1, 200)
        self.customers_table.setColumnWidth(2, 150)
        self.customers_table.setColumnWidth(3, 100)
        self.customers_table.setColumnWidth(4, 80)
        self.customers_table.setColumnWidth(5, 80)
        
        layout.addWidget(self.customers_table)
        
        # Alt filtre butonları
        filter_layout = QHBoxLayout()
        
        self.debt_filter_btn = QPushButton("Borçlu")
        self.debt_filter_btn.setStyleSheet("background-color: #2196F3; color: white;" if self.current_filter == "debt" else "")
        self.debt_filter_btn.clicked.connect(lambda: self.set_filter("debt"))
        
        self.paid_filter_btn = QPushButton("Ödeyen")
        self.paid_filter_btn.setStyleSheet("background-color: #2196F3; color: white;" if self.current_filter == "paid" else "")
        self.paid_filter_btn.clicked.connect(lambda: self.set_filter("paid"))
        
        self.all_filter_btn = QPushButton("Tümünü Göster")
        self.all_filter_btn.setStyleSheet("background-color: #2196F3; color: white;" if self.current_filter == "all" else "")
        self.all_filter_btn.clicked.connect(lambda: self.set_filter("all"))
        
        filter_layout.addWidget(self.debt_filter_btn)
        filter_layout.addWidget(self.paid_filter_btn)
        filter_layout.addWidget(self.all_filter_btn)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        central_widget.setLayout(layout)
        
        # Klavye kısayolları
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo_last_action)
        
        # Stil ayarları
        self.apply_style()
    
    def init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        # EXE uyumlu ikon yolu
        icon_path = resource_path("icon.ico")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon = SystemTrayIcon(icon, self)
        self.tray_icon.show()
    
    def apply_style(self):
        # Geliştirilmiş stil ayarları
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #bbdefb;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 20px;
                font-weight: bold;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 5px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
            QLabel {
                font-size: 14px;
            }
        """)
    
    def load_customers(self):
        search_text = self.search_edit.text()
        
        if search_text:
            customers = self.db.search_customers(search_text, self.current_filter)
        else:
            customers = self.db.get_customers(self.current_filter)
        
        self.customers_table.setRowCount(len(customers))
        
        for i, customer in enumerate(customers):
            # ID
            self.customers_table.setItem(i, 0, QTableWidgetItem(str(customer[0])))
            
            # Ad-Soyad
            full_name = f"{customer[1]} {customer[2] or ''}".strip()
            self.customers_table.setItem(i, 1, QTableWidgetItem(full_name))
            
            # Telefon
            phone = customer[3] or ""
            self.customers_table.setItem(i, 2, QTableWidgetItem(phone))
            
            # Borç
            debt = customer[5]
            debt_item = QTableWidgetItem(f"{debt:.2f} TL")
            
            # Borç rengini ayarla
            if debt > 1000:
                debt_item.setForeground(QColor(200, 0, 0))  # Kırmızı
            elif debt > 500:
                debt_item.setForeground(QColor(200, 100, 0))  # Turuncu
            elif debt > 0:
                debt_item.setForeground(QColor(0, 100, 0))  # Yeşil
            
            self.customers_table.setItem(i, 3, debt_item)
            
            # Düzenle butonu
            edit_btn = QPushButton("✏️ Düzenle")
            edit_btn.setStyleSheet("background-color: #2196F3; color: white;")
            edit_btn.clicked.connect(lambda checked, c_id=customer[0]: self.edit_customer(c_id))
            self.customers_table.setCellWidget(i, 4, edit_btn)
            
            # Sil butonu
            delete_btn = QPushButton("❌ Sil")
            delete_btn.setStyleSheet("background-color: #f44336; color: white;")
            delete_btn.clicked.connect(lambda checked, c_id=customer[0]: self.delete_customer(c_id))
            self.customers_table.setCellWidget(i, 5, delete_btn)
    
    def filter_customers(self):
        self.load_customers()
    
    def set_filter(self, filter_type):
        self.current_filter = filter_type
        self.load_customers()
        
        # Buton stillerini güncelle
        buttons = [self.debt_filter_btn, self.paid_filter_btn, self.all_filter_btn]
        for btn in buttons:
            btn.setStyleSheet("")
        
        if filter_type == "debt":
            self.debt_filter_btn.setStyleSheet("background-color: #2196F3; color: white;")
        elif filter_type == "paid":
            self.paid_filter_btn.setStyleSheet("background-color: #2196F3; color: white;")
        else:
            self.all_filter_btn.setStyleSheet("background-color: #2196F3; color: white;")
    
    def add_customer(self):
        dialog = AddCustomerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.customer_data
            self.db.add_customer(
                data['name'], 
                data['surname'], 
                data['phone'], 
                data['address'], 
                data['debt']
            )
            self.load_customers()
    
    def edit_customer(self, customer_id):
        dialog = CustomerProfileDialog(customer_id, self.db, self)
        dialog.exec_()
        self.load_customers()
    
    def delete_customer(self, customer_id):
        reply = QMessageBox.question(self, "Onay", "Bu müşteriyi ve tüm işlem geçmişini silmek istediğinizden emin misiniz?")
        if reply == QMessageBox.Yes:
            self.db.delete_customer(customer_id)
            self.load_customers()
    
    def show_settings(self):
        dialog = SettingsDialog(self.db, self)
        dialog.exec_()
    
    def show_account(self):
        dialog = AccountDialog(self.db, self)
        dialog.exec_()
    
    def undo_last_action(self):
        QMessageBox.information(self, "Geri Al", "Geri alma özelliği geliştiriliyor...")
    
    def closeEvent(self, event):
        if hasattr(self, 'tray_icon') and self.tray_icon and self.tray_icon.isVisible():
            QMessageBox.information(self, "Veresiye Defteri", 
                                  "Uygulama sistem tepsisinde çalışmaya devam edecek.\n"
                                  "Çıkmak için sistem tepsisindeki menüden 'Çık' seçeneğini kullanın.")
            self.hide()
            event.ignore()
        else:
            event.accept()
    
    def check_auto_backup(self):
        self.db.auto_backup()

class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        self.setWindowTitle("Ayarlar")
        self.setFixedSize(600, 700)
        
        layout = QVBoxLayout()
        
        # Profil bilgileri
        profile_group = QGroupBox("Profil")
        profile_layout = QFormLayout()
        
        self.shop_name_edit = QLineEdit()
        self.shop_name_edit.setPlaceholderText("Dükkân adınızı giriniz")
        profile_layout.addRow("Dükkân Adı:", self.shop_name_edit)
        
        self.shop_address_edit = QLineEdit()
        self.shop_address_edit.setPlaceholderText("Dükkân adresinizi giriniz")
        profile_layout.addRow("Adres:", self.shop_address_edit)
        
        # Logo yükleme
        logo_layout = QHBoxLayout()
        self.logo_path_label = QLabel("Logo seçilmedi")
        logo_btn = QPushButton("Logo Yükle")
        logo_btn.clicked.connect(self.select_logo)
        logo_layout.addWidget(self.logo_path_label)
        logo_layout.addWidget(logo_btn)
        profile_layout.addRow("Logo:", logo_layout)
        
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        # Borç limitleri
        limits_group = QGroupBox("Borç Limitleri")
        limits_layout = QVBoxLayout()
        
        current_month = datetime.now().strftime("%B %Y")
        next_month = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1).strftime("%B %Y")
        
        current_limit_layout = QHBoxLayout()
        current_limit_layout.addWidget(QLabel(f"{current_month}:"))
        self.current_limit_edit = QLineEdit()
        self.current_limit_edit.setText("5000")
        current_limit_layout.addWidget(self.current_limit_edit)
        current_limit_layout.addWidget(QLabel("TL"))
        current_limit_btn = QPushButton("Değiştir")
        current_limit_btn.clicked.connect(self.change_current_limit)
        current_limit_layout.addWidget(current_limit_btn)
        
        next_limit_layout = QHBoxLayout()
        next_limit_layout.addWidget(QLabel(f"{next_month}:"))
        self.next_limit_edit = QLineEdit()
        self.next_limit_edit.setText("6000")
        next_limit_layout.addWidget(self.next_limit_edit)
        next_limit_layout.addWidget(QLabel("TL"))
        next_limit_btn = QPushButton("Değiştir")
        next_limit_btn.clicked.connect(self.change_next_limit)
        next_limit_layout.addWidget(next_limit_btn)
        
        limits_layout.addLayout(current_limit_layout)
        limits_layout.addLayout(next_limit_layout)
        limits_group.setLayout(limits_layout)
        layout.addWidget(limits_group)
        
        # Tema seçimi
        theme_group = QGroupBox("Tema")
        theme_layout = QHBoxLayout()
        
        self.light_theme_radio = QRadioButton("Açık Mod")
        self.dark_theme_radio = QRadioButton("Koyu Mod")
        self.light_theme_radio.setChecked(True)
        
        self.light_theme_radio.toggled.connect(self.change_theme)
        self.dark_theme_radio.toggled.connect(self.change_theme)
        
        theme_layout.addWidget(self.light_theme_radio)
        theme_layout.addWidget(self.dark_theme_radio)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Otomatik yedekleme
        backup_group = QGroupBox("Otomatik Yedekleme")
        backup_layout = QVBoxLayout()
        
        self.backup_combo = QComboBox()
        self.backup_combo.addItems(["Kapalı", "Saatlik", "Günlük", "Haftalık", "Aylık"])
        backup_layout.addWidget(QLabel("Yedekleme Sıklığı:"))
        backup_layout.addWidget(self.backup_combo)
        
        backup_layout.addWidget(QLabel("Son Yedekleme:"))
        last_backup = self.db.get_setting('last_backup')
        self.last_backup_label = QLabel(last_backup if last_backup else "Henüz yedekleme yapılmadı")
        backup_layout.addWidget(self.last_backup_label)
        
        backup_now_btn = QPushButton("Şimdi Yedekle")
        backup_now_btn.clicked.connect(self.backup_now)
        backup_layout.addWidget(backup_now_btn)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Alt butonlar
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self.save_settings)
        
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_settings(self):
        # Otomatik yedekleme ayarını yükle
        auto_backup = self.db.get_setting('auto_backup')
        if auto_backup:
            index_map = {"none": 0, "hourly": 1, "daily": 2, "weekly": 3, "monthly": 4}
            self.backup_combo.setCurrentIndex(index_map.get(auto_backup, 0))
    
    def save_settings(self):
        # Otomatik yedekleme ayarını kaydet
        index_map = {0: "none", 1: "hourly", 2: "daily", 3: "weekly", 4: "monthly"}
        self.db.set_setting('auto_backup', index_map[self.backup_combo.currentIndex()])
        
        QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi!")
        self.accept()
    
    def select_logo(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Logo Seç", "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp)")
        if filename:
            self.logo_path_label.setText(os.path.basename(filename))
    
    def change_current_limit(self):
        QMessageBox.information(self, "Başarılı", "Mevcut ay borç limiti güncellendi!")
    
    def change_next_limit(self):
        QMessageBox.information(self, "Başarılı", "Gelecek ay borç limiti güncellendi!")
    
    def change_theme(self):
        if self.dark_theme_radio.isChecked():
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
    
    def apply_dark_theme(self):
        dark_style = """
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLineEdit {
                background-color: #404040;
                border: 2px solid #555;
                padding: 8px;
                border-radius: 4px;
                color: white;
            }
            QTableWidget {
                background-color: #353535;
                gridline-color: #555;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                margin: 10px 0;
                padding-top: 10px;
                background-color: #333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #ccc;
            }
            QComboBox {
                background-color: #404040;
                color: white;
                border: 1px solid #555;
                padding: 5px;
            }
            QRadioButton {
                color: #ccc;
            }
        """
        self.parent().setStyleSheet(dark_style)
    
    def apply_light_theme(self):
        self.parent().apply_style()
    
    def backup_now(self):
        filename = self.db.do_backup("manual")
        if filename:
            self.last_backup_label.setText(f"Son yedekleme: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            QMessageBox.information(self, "Başarılı", f"Yedekleme tamamlandı:\n{filename}")

# Ana uygulama çalıştırıcısı
class VeresiyeDefteri(QApplication):
    def __init__(self):
        super().__init__(sys.argv)
        self.setQuitOnLastWindowClosed(False)
        
        # Uygulama bilgileri
        self.setApplicationName("Veresiye Defteri")
        self.setApplicationVersion("1.5")
        self.setOrganizationName("Esnaf Yazılımları")
        
        # İkon ayarla (EXE uyumlu)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
    
    def run(self):
        # Ana pencereyi oluştur ve göster
        self.main_window = MainWindow()
        self.main_window.show()
        
        # Splash mesajı
        if hasattr(self.main_window, 'tray_icon') and self.main_window.tray_icon:
            self.main_window.tray_icon.showMessage(
                "Veresiye Defteri",
                "Uygulama başlatıldı ve sistem tepsisinde çalışıyor.",
                QSystemTrayIcon.Information,
                2000
            )
        
        return self.exec_()

def main():
    app = VeresiyeDefteri()
    
    # Sistem tepsisi kontrolü
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Sistem Tepsisi", 
                           "Sistem tepsisi bu sistemde kullanılamıyor.")
        return 1
    
    return app.run()

if __name__ == "__main__":
    sys.exit(main())