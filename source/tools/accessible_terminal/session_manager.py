import wx
import keyring
import json
import sqlite3
import os
from cryptography.fernet import Fernet
import base64
import secrets


class SessionManager:
    def __init__(self, app_name):
        self.app_name = app_name
        self.db_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_name, "sessions.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._create_table()
        self.encryption_key = self._get_or_create_app_key()

    def _create_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data BLOB
            )
        """)
        conn.commit()
        conn.close()

    def _generate_encryption_key(self):
        key = base64.urlsafe_b64encode(secrets.token_bytes(32))
        return key.decode()

    def _get_or_create_app_key(self):
        key = keyring.get_password(self.app_name, self.app_name)
        if not key:
           key = self._generate_encryption_key()
           keyring.set_password(self.app_name, self.app_name, key)
        return key

    def _encrypt_data(self, key, data, iv=None):
        f = Fernet(key)
        if not iv:
            iv = secrets.token_bytes(16)
        encrypted_data = f.encrypt(iv + json.dumps(data).encode())
        return encrypted_data, iv

    def _decrypt_data(self, key, encrypted_data):
       f = Fernet(key)
       decrypted_data = f.decrypt(encrypted_data)
       iv = decrypted_data[:16]
       data = decrypted_data[16:]
       return json.loads(data.decode()), iv

    def save_session(self, name, host, port, username, password, save_password, key_file_path=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            data = {"name": name, "host": host, "port": port, "username": username}
            if save_password:
                data["password"] = password
            if key_file_path:
                data["key_file_path"] = key_file_path

            encrypted_data, iv = self._encrypt_data(self.encryption_key, data)
            cursor.execute("INSERT INTO sessions (data) VALUES (?)", (base64.b64encode(encrypted_data).decode(),))
            conn.commit()

        except sqlite3.IntegrityError:
             wx.MessageBox(f"A session with the name '{name}' already exists.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error saving session {name}: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            conn.close()

    def load_sessions(self):
        """Loads all saved SSH sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM sessions")
        sessions = [] # List of (name, host, port, username, password, key_file_path)
        for row in cursor.fetchall():
            raw_data_from_db = row[0]
            try:
                # Decode the base64 string from the database
                encrypted_data_bytes = base64.b64decode(raw_data_from_db)
                data, _ = self._decrypt_data(self.encryption_key, encrypted_data_bytes)
                name = data.get("name", "Unknown")
                host = data.get("host", "")
                port = data.get("port", 22)
                username = data.get("username", "root")
                password = data.get("password", "")
                key_file_path = data.get("key_file_path")

                # Ensure port is an integer
                try:
                    port = int(port)
                except (ValueError, TypeError):
                    port = 22

                sessions.append((name, host, port, username, password, key_file_path))
            except Exception as e:
                 wx.MessageBox(f"Error loading session data for a record: {e}. The faulty record will be removed.", "Error", wx.OK | wx.ICON_ERROR)
                 self._remove_faulty_record(raw_data_from_db)

        conn.close()
        return sessions

    def _remove_faulty_record(self, raw_data_b64):
        """Removes a session record based on its raw base64 data string."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE data=?", (raw_data_b64,))
        conn.commit()
        conn.close()

    def remove_session(self, name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT data FROM sessions")
            rows = cursor.fetchall()
            for row in rows:
                encrypted_data = row[0]
                try:
                    data, _ = self._decrypt_data(self.encryption_key, base64.b64decode(encrypted_data))
                    if data.get("name") == name:
                        cursor.execute("DELETE FROM sessions WHERE data=?", (encrypted_data,))
                        conn.commit()
                        break
                except:
                  continue
        except Exception as e:
                wx.MessageBox(f"Error removing session {name}: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            conn.close()
