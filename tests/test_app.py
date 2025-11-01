import unittest
from app import create_app

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Bienvenido a la aplicación de cine', response.data.decode('utf-8'))

    # Aquí puedes agregar más pruebas unitarias según sea necesario

if __name__ == '__main__':
    unittest.main()