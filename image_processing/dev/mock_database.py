# ===== dev/mock_database.py =====
"""
Mock FileMaker Database Server for Development Testing
Provides a SQLite-based mock of the Crown FileMaker database
"""

import sqlite3
import socket
import threading
import json
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockFileMakerServer:
    """Mock FileMaker server using SQLite backend."""

    def __init__(self, db_path="/app/data/mock_crown.db", port=5432):
        self.db_path = Path(db_path)
        self.port = port
        self.setup_database()

    def setup_database(self):
        """Initialize SQLite database with sample Crown data."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create Master table (parts database)
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS Master
                       (
                           AS400_NumberStripped
                           TEXT
                           PRIMARY
                           KEY,
                           PartBrand
                           TEXT,
                           PartDescription
                           TEXT,
                           SDC_DescriptionShort
                           TEXT,
                           SDC_PartDescriptionExtended
                           TEXT,
                           SDC_KeySearchWords
                           TEXT,
                           SDC_SlangDescription
                           TEXT,
                           ToggleActive
                           TEXT
                           DEFAULT
                           'Yes'
                       )
                       ''')

        # Create interchange table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS as400_ininter
                       (
                           ICPCD
                           TEXT,
                           ICPNO
                           TEXT,
                           IPTNO
                           TEXT
                       )
                       ''')

        # Insert sample parts data
        sample_parts = [
            ('J1234567', 'Crown Automotive', 'Fuel Tank Skid Plate', 'Skid Plate - Fuel Tank',
             'Heavy duty steel construction fuel tank protection skid plate',
             'fuel tank, skid plate, protection, steel', 'tank guard'),
            ('A5551234', 'Crown Automotive', 'Air Filter', 'Air Filter Element',
             'High flow air filter element for improved performance', 'air filter, element, performance',
             'air cleaner'),
            ('12345', 'Crown Automotive', 'Oil Pan', 'Engine Oil Pan', 'Cast aluminum oil pan with drain plug',
             'oil pan, engine, aluminum, drain', 'oil sump'),
            ('67890', 'Crown Automotive', 'Water Pump', 'Water Pump Assembly',
             'Complete water pump assembly with gasket', 'water pump, cooling, gasket', 'coolant pump'),
            ('J9876543', 'Crown Automotive', 'Transmission Mount', 'Transmission Mount Bracket',
             'Heavy duty transmission mount with rubber isolator', 'transmission, mount, bracket, rubber',
             'trans mount'),
            ('A1111111', 'Crown Automotive', 'Brake Pad Set', 'Front Brake Pad Set',
             'Ceramic brake pads for front axle', 'brake pads, ceramic, front', 'brake shoes'),
            ('B2222222', 'Crown Automotive', 'Shock Absorber', 'Rear Shock Absorber', 'Gas charged rear shock absorber',
             'shock absorber, rear, gas', 'damper'),
            ('C3333333', 'Crown Automotive', 'CV Joint', 'Constant Velocity Joint',
             'Rebuilt CV joint with boot and grease', 'cv joint, constant velocity, boot', 'drive joint'),
        ]

        cursor.executemany('''
            INSERT OR REPLACE INTO Master 
            (AS400_NumberStripped, PartBrand, PartDescription, SDC_DescriptionShort, 
             SDC_PartDescriptionExtended, SDC_KeySearchWords, SDC_SlangDescription)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_parts)

        # Insert sample interchange data
        sample_interchanges = [
            ('IC', 'OLD12345', '12345'),  # Old part mapped to new
            ('IC', 'LEGACY67890', '67890'),  # Legacy part mapped to current
            ('IC', 'J1234567A', 'J1234567'),  # Revision mapping
            ('IC', '12345_OLD', '12345'),  # Old suffix mapping
            ('IC', 'A555OLD', 'A5551234'),  # Old style to new style
        ]

        cursor.executemany('''
            INSERT OR REPLACE INTO as400_ininter (ICPCD, ICPNO, IPTNO)
            VALUES (?, ?, ?)
        ''', sample_interchanges)

        conn.commit()
        conn.close()

        logger.info(f"Mock database initialized at {self.db_path}")

    def query_parts(self, part_number):
        """Query parts database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT AS400_NumberStripped,
                              PartBrand,
                              PartDescription,
                              SDC_DescriptionShort,
                              SDC_PartDescriptionExtended,
                              SDC_KeySearchWords,
                              SDC_SlangDescription
                       FROM Master
                       WHERE AS400_NumberStripped = ?
                         AND ToggleActive = 'Yes'
                       ''', (part_number,))

        result = cursor.fetchone()
        conn.close()
        return result

    def query_interchange(self):
        """Query interchange mappings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT ICPCD, ICPNO, IPTNO
                       FROM as400_ininter
                       ORDER BY IPTNO, ICPCD
                       ''')

        results = cursor.fetchall()
        conn.close()
        return results

    def search_parts(self, search_term, limit=10):
        """Search parts by partial match."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT AS400_NumberStripped,
                              PartBrand,
                              PartDescription,
                              SDC_DescriptionShort,
                              SDC_PartDescriptionExtended,
                              SDC_KeySearchWords,
                              SDC_SlangDescription
                       FROM Master
                       WHERE AS400_NumberStripped LIKE ?
                         AND ToggleActive = 'Yes'
                       ORDER BY AS400_NumberStripped LIMIT ?
                       ''', (f"{search_term}%", limit))

        results = cursor.fetchall()
        conn.close()
        return results

    def handle_connection(self, client_socket):
        """Handle incoming database connections."""
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                try:
                    query = json.loads(data)
                    query_type = query.get('type')

                    if query_type == 'part_lookup':
                        result = self.query_parts(query['part_number'])
                        response = {'success': True, 'data': result}
                    elif query_type == 'interchange':
                        result = self.query_interchange()
                        response = {'success': True, 'data': result}
                    elif query_type == 'search':
                        result = self.search_parts(query['search_term'], query.get('limit', 10))
                        response = {'success': True, 'data': result}
                    else:
                        response = {'success': False, 'error': 'Unknown query type'}

                except json.JSONDecodeError:
                    response = {'success': False, 'error': 'Invalid JSON'}
                except Exception as e:
                    response = {'success': False, 'error': str(e)}

                client_socket.send(json.dumps(response).encode('utf-8'))

        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            client_socket.close()

    def start_server(self):
        """Start the mock database server."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)

        logger.info(f"Mock FileMaker server listening on port {self.port}")

        try:
            while True:
                client_socket, address = server_socket.accept()
                logger.info(f"Connection from {address}")

                client_thread = threading.Thread(
                    target=self.handle_connection,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()

        except KeyboardInterrupt:
            logger.info("Shutting down mock database server")
        finally:
            server_socket.close()


if __name__ == '__main__':
    server = MockFileMakerServer()
    server.start_server()